"""A private, single-owner URL-to-APK builder for Cloud in a Bottle."""
from __future__ import annotations

import hashlib
import io
import json
import logging
import os
import secrets
import shutil
import sqlite3
import subprocess
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from xml.sax.saxutils import escape

from flask import Flask, abort, jsonify, render_template, request, send_file, url_for
from PIL import Image, ImageDraw, ImageFont
from werkzeug.middleware.proxy_fix import ProxyFix

ROOT = Path(__file__).resolve().parent
DATA = Path(os.environ.get("BOTTLE_APP_DATA_DIR", os.environ.get("WEB_APK_DATA_DIR", str(ROOT / "data"))))
TEMP = Path(os.environ.get("BOTTLE_APP_TEMP_DIR", str(DATA / "temporary")))
ENGINE = "159.0.20261102144711"
GRADLE = os.environ.get("GRADLE_BIN", "/opt/gradle/bin/gradle")
SDK = os.environ.get("ANDROID_HOME", "/opt/android-sdk")
for directory in (DATA, TEMP, DATA / "keys", DATA / "builds"):
    directory.mkdir(parents=True, exist_ok=True)
os.chmod(DATA / "keys", 0o700)
app = Flask(__name__)
app.logger.setLevel(logging.INFO)
app.config["MAX_CONTENT_LENGTH"] = 16384
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="apk-build")
lock = threading.Lock()


def database():
    connection = sqlite3.connect(DATA / "jobs.sqlite", timeout=30)
    connection.row_factory = sqlite3.Row
    return connection


with database() as db:
    db.executescript("""
        CREATE TABLE IF NOT EXISTS sites (url TEXT PRIMARY KEY, revision INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS jobs (
          id TEXT PRIMARY KEY, url TEXT NOT NULL, name TEXT NOT NULL,
          package TEXT NOT NULL, version INTEGER NOT NULL, state TEXT NOT NULL,
          created REAL NOT NULL, error TEXT, sha256 TEXT, size INTEGER,
          engine TEXT NOT NULL
        );
    """)
    db.execute("UPDATE jobs SET state='interrupted',error='The server restarted. Build again to continue.' WHERE state IN ('queued','building')")


def normalize_url(value: str) -> str:
    if not isinstance(value, str) or len(value) > 2048 or any(ord(c) < 32 for c in value):
        raise ValueError("Enter a valid website address.")
    value = value.strip()
    if "://" not in value:
        value = "https://" + value
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Use an HTTPS address without a username or password in the URL.")
    if parsed.port and parsed.port != 443:
        raise ValueError("This first version supports standard HTTPS addresses.")
    host = parsed.hostname.encode("idna").decode("ascii")
    if len(host) > 253 or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789.-" for c in host.lower()):
        raise ValueError("Enter a valid website host name.")
    return urlunsplit(("https", host.lower(), parsed.path or "/", parsed.query, parsed.fragment))


def update_job(job_id: str, **values):
    with database() as db:
        db.execute("UPDATE jobs SET " + ",".join(k + "=?" for k in values) + " WHERE id=?", [*values.values(), job_id])


def get_job(job_id: str):
    with database() as db:
        row = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    if row is None:
        abort(404)
    return dict(row)


def signing_environment() -> dict[str, str]:
    """Keep a persistent signing key; pass passwords only in process environment."""
    env = os.environ.copy()
    password_file = DATA / "keys" / "password"
    if not password_file.exists():
        descriptor = os.open(password_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(descriptor, "w") as stream:
            stream.write(secrets.token_urlsafe(40))
    env["APK_KEYSTORE_PASSWORD"] = password_file.read_text()
    env["APK_KEYSTORE"] = str((DATA / "keys" / "release.jks").resolve())
    if not Path(env["APK_KEYSTORE"]).exists():
        subprocess.run([
            "keytool", "-genkeypair", "-keystore", env["APK_KEYSTORE"],
            "-storepass:env", "APK_KEYSTORE_PASSWORD", "-keypass:env", "APK_KEYSTORE_PASSWORD",
            "-alias", "webapps", "-keyalg", "RSA", "-keysize", "3072", "-validity", "10000",
            "-dname", "CN=Personal Web Apps", "-noprompt",
        ], env=env, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        os.chmod(env["APK_KEYSTORE"], 0o600)
    env["ANDROID_HOME"] = SDK
    env["GRADLE_USER_HOME"] = str(DATA / "gradle-cache")
    return env


def make_icon(name: str) -> bytes:
    image = Image.new("RGB", (512, 512), "#243a68")
    draw = ImageDraw.Draw(image)
    path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    font = ImageFont.truetype(path, 240) if Path(path).exists() else ImageFont.load_default(size=240)
    glyph = next((c.upper() for c in name if c.isascii() and c.isalnum()), "W")
    draw.text((256, 248), glyph, fill="#f2f5ff", font=font, anchor="mm")
    output = io.BytesIO()
    image.save(output, "PNG")
    return output.getvalue()


def build(job_id: str):
    job = get_job(job_id)
    output = DATA / "builds" / job_id
    output.mkdir(exist_ok=True)
    work = TEMP / job_id
    try:
        update_job(job_id, state="building")
        shutil.copytree(ROOT / "android", work, ignore=shutil.ignore_patterns("build", ".gradle", "local.properties"))
        assets = work / "app/src/main/assets"
        assets.mkdir(parents=True, exist_ok=True)
        (assets / "site.json").write_text(json.dumps({"url": job["url"], "name": job["name"]}))
        (work / "app/src/main/res/values/strings.xml").write_text(
            '<resources><string name="app_name" formatted="false">' + escape(job["name"]).replace("'", "\\'").replace('"', '\\"') + '</string></resources>'
        )
        icons = work / "app/src/main/res/mipmap-xxxhdpi"
        icons.mkdir(parents=True, exist_ok=True)
        (icons / "ic_launcher.png").write_bytes(make_icon(job["name"]))
        (work / "local.properties").write_text("sdk.dir=" + SDK + "\n")
        env = signing_environment()
        with (output / "build.log").open("w") as log:
            result = subprocess.run([
                GRADLE, "--no-daemon", "--console=plain", "assembleRelease",
                "-PsitePackage=" + job["package"], "-PsiteVersion=" + str(job["version"]),
            ], cwd=work, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=1800)
        if result.returncode:
            app.logger.error("ANDROID_BUILD_FAILED id=%s\n%s", job_id, (output / "build.log").read_text()[-10000:])
            raise RuntimeError("The Android build failed. Its build log is available below.")
        apk = work / "app/build/outputs/apk/release/app-release.apk"
        if not apk.is_file():
            raise RuntimeError("The Android build did not produce an APK.")
        verification = subprocess.run([
            str(Path(SDK) / "build-tools/36.0.0/apksigner"), "verify", "--verbose", str(apk),
        ], env=env, capture_output=True, text=True, timeout=60)
        (output / "signature.txt").write_text(verification.stdout + verification.stderr)
        if verification.returncode:
            raise RuntimeError("The APK failed Android's signature verification.")
        shutil.copyfile(apk, output / "app.apk")
        with (output / "app.apk").open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        manifest = {**job, "state": "ready", "engine": ENGINE, "sha256": digest}
        (output / "source.json").write_text(json.dumps(manifest, indent=2))
        update_job(job_id, state="ready", sha256=digest, size=apk.stat().st_size)
        app.logger.info("APK_READY id=%s size=%s sha256=%s", job_id, apk.stat().st_size, digest)
    except Exception as error:
        app.logger.exception("Build %s failed", job_id)
        update_job(job_id, state="failed", error=str(error)[:500])
    finally:
        if work.exists():
            shutil.rmtree(work)


@app.after_request
def security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Cache-Control"] = "no-store"
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; base-uri 'none'; frame-ancestors 'self'; form-action 'self'"
    return response


@app.get("/health")
def health():
    """Report readiness of the packager."""
    return jsonify(status="ok", engine=ENGINE)


@app.get("/")
def index():
    """Show the website packager and previous builds."""
    return render_template("index.html", engine=ENGINE)


@app.get("/api/builds")
def list_builds():
    """List recent builds, retaining their original website addresses."""
    with database() as db:
        jobs = [dict(row) for row in db.execute("SELECT * FROM jobs ORDER BY created DESC LIMIT 50")]
    return jsonify(jobs)


@app.post("/api/builds")
def create_build():
    """Generate a separately installable Android APK for an HTTPS website."""
    origin = request.headers.get("Origin")
    if origin and urlsplit(origin).netloc != request.host:
        abort(403)
    payload = request.get_json()
    if not isinstance(payload, dict):
        return jsonify(error="Send a website address and optional app name."), 400
    try:
        url = normalize_url(payload.get("url", ""))
        name = str(payload.get("name", "")).strip() or urlsplit(url).hostname
        if not name or len(name) > 60 or any(ord(c) < 32 for c in name):
            raise ValueError("Use an app name of 1–60 characters.")
    except (ValueError, UnicodeError) as error:
        return jsonify(error=str(error)), 400
    try:
        return jsonify(enqueue_build(url, name)), 202
    except OverflowError as error:
        return jsonify(error=str(error)), 429


def enqueue_build(url: str, name: str):
    """Persist original inputs and queue one build with a stable update identity."""
    with lock, database() as db:
        if db.execute("SELECT count(*) FROM jobs WHERE state IN ('queued','building')").fetchone()[0] >= 4:
            raise OverflowError("Four apps are already waiting. Try again after a build finishes.")
        row = db.execute("SELECT revision FROM sites WHERE url=?", (url,)).fetchone()
        version = row[0] + 1 if row else 1
        db.execute("INSERT INTO sites VALUES (?,?) ON CONFLICT(url) DO UPDATE SET revision=excluded.revision", (url, version))
        job_id = uuid.uuid4().hex
        package = "in.bowei.webapps.a" + hashlib.sha256(url.encode()).hexdigest()[:20]
        db.execute("INSERT INTO jobs VALUES (?,?,?,?,?,?,?,NULL,NULL,NULL,?)", (job_id, url, name, package, version, "queued", time.time(), ENGINE))
    executor.submit(build, job_id)
    return get_job(job_id)


@app.get("/api/builds/<job_id>")
def job_status(job_id):
    """Read the state and original inputs of a build."""
    return jsonify(get_job(job_id))


@app.get("/builds/<job_id>/app.apk")
def download(job_id):
    """Download a signed Android package."""
    job = get_job(job_id)
    if job["state"] != "ready":
        abort(409)
    return send_file(DATA / "builds" / job_id / "app.apk", mimetype="application/vnd.android.package-archive", as_attachment=True, download_name="website-app.apk")


@app.get("/builds/<job_id>/source")
def source(job_id):
    """Show the unprocessed configuration and source website for a build."""
    return render_template("source.html", job=get_job(job_id))


@app.get("/builds/<job_id>/log")
def build_log(job_id):
    """Read the build output without exposing signing keys."""
    get_job(job_id)
    path = DATA / "builds" / job_id / "build.log"
    if not path.exists():
        return "The build has not begun yet.", 200, {"Content-Type": "text/plain"}
    return send_file(path, mimetype="text/plain")


if os.environ.get("BOTTLE_APP_NAME"):
    # A first-install sample lets the owner check installation before creating
    # an app for a signed-in site. It is created once and stays owner-private.
    with database() as db:
        empty = db.execute("SELECT count(*) FROM jobs").fetchone()[0] == 0
    if empty:
        enqueue_build("https://example.com/", "Example")


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "8080")))
