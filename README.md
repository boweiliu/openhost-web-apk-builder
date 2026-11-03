# Web APK Builder

A private server-side website-to-Android-app builder, packaged for Cloud in a Bottle.

Enter an HTTPS URL and an optional app name. The server builds a signed ARM64 APK
with an independent Android app identity, private browser profile, and Firefox's
GeckoView engine. No website ownership, Chrome installation, or Google build
service is required. The website loads live from its original URL; the APK is not
an offline copy of it.

The initial engine pin is GeckoView 159.0.20261102144711, Mozilla's stable release
on November 3, 2026. Check Mozilla's Maven metadata before updating the pin.

## Deploy

Deploy this repository using the Cloud in a Bottle dashboard. All routes remain
owner-only, including APK downloads. The container builds one app at a time and
keeps its signing key, build history, artifacts, and Gradle cache in the app's
persistent data directory. Back that directory up: losing the signing key means
existing apps cannot receive compatible updates.

An identical normalized URL produces the same package ID; successive builds use
increasing version codes. Page changes need no rebuild. GeckoView security
updates require updating the engine pin and rebuilding installed apps.

## First-version boundaries

- Android 8+ ARM64 phones only; no emulator or 32-bit build is advertised.
- Separate app-drawer entry and site data; no inherited Firefox session or Sync.
- HTTPS navigation, JavaScript dialogs, and HTTP Basic authentication.
- No background web push, passkeys, Firefox extensions, camera/microphone, or
  file uploads in this first version. Content permissions default to denied.
- Google FIDO dependencies are excluded, and WebAuthn is disabled in Gecko's
  runtime configuration. This path must be verified on a physical phone.
- Android's install confirmation and its unknown-app-source permission still apply.

The current origin stays visible in a small native strip. Tap it for reload,
home, the external browser, or app information. A simple generated letter icon
is used instead of fetching potentially untrusted site metadata on the server.
The builder never fetches a submitted site's URL; only the Android app does.

## Local development

Install JDK 17+, Android SDK platform 37/build-tools 36, and Gradle 9.3.1. Install
requirements, set ANDROID_HOME and GRADLE_BIN, then run server.py. Keep this
development process on loopback; Cloud in a Bottle handles production owner
authentication. Do not expose an unauthenticated development server.

The first cloud deployment creates an Example APK for https://example.com/ so
you can check installation without entering a site's login. Every output APK is
verified with Android's signature verifier before its download becomes ready.

## License

The packager and shell are available under MPL-2.0. GeckoView and dependencies
retain their own licenses. Source: https://github.com/boweiliu/openhost-web-apk-builder

[agent:host-6315db80f4ec41e48d0aafc05a123cf2/minds/workspace=webapk/harness=claude:mngr=agent-4b1c32138415425ca82e04be2c3aaf0c:unknown]
