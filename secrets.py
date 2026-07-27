"""
Windows DPAPI helpers for protecting API keys at rest.

Uses ctypes + crypt32 (no extra dependencies). On non-Windows platforms
encrypt/decrypt are no-ops that store plaintext with a warning in logs.
"""

from __future__ import annotations

import base64
import logging
import sys

log = logging.getLogger(__name__)

DPAPI_PREFIX = "dpapi:"


def is_dpapi_available() -> bool:
    return sys.platform == "win32"


def encrypt(plaintext: str) -> str:
    """Return DPAPI-protected value prefixed with ``dpapi:``."""
    if not plaintext:
        return ""
    if not is_dpapi_available():
        log.warning("DPAPI unavailable on this platform; storing API key without encryption")
        return plaintext
    raw = plaintext.encode("utf-8")
    protected = _crypt_protect(raw)
    return DPAPI_PREFIX + base64.b64encode(protected).decode("ascii")


def decrypt(stored: str) -> str:
    """Decrypt a ``dpapi:`` value, or return plaintext legacy values as-is."""
    if not stored:
        return ""
    if not stored.startswith(DPAPI_PREFIX):
        return stored
    if not is_dpapi_available():
        log.error("Cannot decrypt DPAPI key on non-Windows platform")
        return ""
    blob = base64.b64decode(stored[len(DPAPI_PREFIX) :], validate=True)
    return _crypt_unprotect(blob).decode("utf-8")


def is_encrypted(stored: str) -> bool:
    return bool(stored) and stored.startswith(DPAPI_PREFIX)


def _crypt_protect(data: bytes) -> bytes:
    import ctypes
    from ctypes import wintypes

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]

    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32

    in_blob = DATA_BLOB()
    in_blob.cbData = len(data)
    in_blob.pbData = ctypes.cast(
        ctypes.create_string_buffer(data, len(data)),
        ctypes.POINTER(ctypes.c_byte),
    )

    out_blob = DATA_BLOB()
    if not crypt32.CryptProtectData(
        ctypes.byref(in_blob),
        None,
        None,
        None,
        None,
        0,
        ctypes.byref(out_blob),
    ):
        raise OSError("CryptProtectData failed")

    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        kernel32.LocalFree(out_blob.pbData)


def _crypt_unprotect(data: bytes) -> bytes:
    import ctypes
    from ctypes import wintypes

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]

    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32

    in_blob = DATA_BLOB()
    in_blob.cbData = len(data)
    in_blob.pbData = ctypes.cast(
        ctypes.create_string_buffer(data, len(data)),
        ctypes.POINTER(ctypes.c_byte),
    )

    out_blob = DATA_BLOB()
    if not crypt32.CryptUnprotectData(
        ctypes.byref(in_blob),
        None,
        None,
        None,
        None,
        0,
        ctypes.byref(out_blob),
    ):
        raise OSError("CryptUnprotectData failed")

    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        kernel32.LocalFree(out_blob.pbData)
