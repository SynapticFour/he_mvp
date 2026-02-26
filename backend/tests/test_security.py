# SPDX-License-Identifier: Apache-2.0
"""Security helpers: secure_filename, sanitize_text."""
from app.core.security import sanitize_text, secure_filename, sha3_256_hex


def test_secure_filename_empty():
    assert secure_filename("") == "unnamed.bin"
    assert secure_filename("   ") == "unnamed.bin"


def test_secure_filename_strips_path():
    assert ".." not in secure_filename("../../../etc/passwd")
    assert secure_filename("/tmp/foo.bin").startswith("foo") or "unnamed" in secure_filename("/tmp/foo.bin")


def test_secure_filename_sanitizes_special_chars():
    out = secure_filename("file name with spaces.bin")
    assert " " not in out or out == "unnamed.bin"
    out = secure_filename("normal.bin")
    assert "normal" in out or "bin" in out


def test_sanitize_text_empty():
    assert sanitize_text("") == ""


def test_sanitize_text_strips_html():
    assert "<script>" not in sanitize_text("Hello <script>alert(1)</script> world")
    assert "Hello" in sanitize_text("Hello <b>bold</b>")


def test_sanitize_text_strips_javascript():
    assert "javascript:" not in sanitize_text("Click javascript:evil()").lower()


def test_sanitize_text_enforces_max_len():
    long_str = "a" * 3000
    assert len(sanitize_text(long_str, max_len=100)) == 100


def test_sha3_256_hex_hex_output():
    h = sha3_256_hex("test")
    assert len(h) == 64
    assert all(c in "0123456789abcdef" for c in h)
