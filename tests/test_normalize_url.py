"""Which website addresses the builder accepts.

Run with: WEB_APK_DATA_DIR=$(mktemp -d) python -m pytest tests
"""
import os
import sys
import tempfile
from pathlib import Path

import pytest

os.environ.setdefault("WEB_APK_DATA_DIR", tempfile.mkdtemp())
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from server import normalize_url  # noqa: E402

STUDIO_SHARE = ("https://system_interface-nj2jy4yq.06da50437af5785c59d154db7f0b530c"
                ".d614ca37b19c752b08032764976c2d97.us1.personal-imbue.com/")


@pytest.mark.parametrize("value, expected", [
    (STUDIO_SHARE, STUDIO_SHARE),
    ("links.oh.bowei.in/fresh062", "https://links.oh.bowei.in/fresh062"),
    ("Example.COM", "https://example.com/"),
    ("https://example.com:443/a?b=1#c", "https://example.com/a?b=1#c"),
])
def test_accepts(value, expected):
    assert normalize_url(value) == expected


@pytest.mark.parametrize("value", [
    "http://example.com",
    "https://user:pass@example.com",
    "https://example.com:8443/",
    "https://a!b.com",
    "https://exa mple.com",
    "https://" + "y" * 70 + ".com",
])
def test_rejects(value):
    with pytest.raises((ValueError, UnicodeError)):
        normalize_url(value)
