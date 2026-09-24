"""Content sniffing for files downloaded from Sherlock.

Sherlock stores files by hash and serves them as ``application/octet-stream``
without a filename, so the extension has to be inferred from the magic bytes.
"""

from __future__ import annotations

__all__ = ["guess_extension_by_magic"]


def guess_extension_by_magic(data: bytes) -> str:
    """Guess a file extension from the leading bytes of ``data``.

    Returns a dotted extension such as ``".png"``, falling back to ``".bin"``
    when the content is not recognised.
    """
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if data.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if data.startswith(b"%PDF-"):
        return ".pdf"
    if data.startswith(b"PK\x03\x04"):
        return ".zip"
    if data.startswith(b"\x25\x21PS-Adobe-"):
        return ".ps"
    if data.startswith(b"\xef\xbb\xbf") or _looks_like_text(data):
        return ".txt"
    return ".bin"


def _looks_like_text(data: bytes) -> bool:
    """Heuristic: a UTF-8-decodable prefix with no NUL or control bytes."""
    head = data[:512]
    if not head or b"\x00" in head:
        return False
    try:
        text = head.decode("utf-8")
    except UnicodeDecodeError:
        # A multi-byte character may straddle the 512-byte cut; retry shorter.
        try:
            text = head[:-4].decode("utf-8")
        except UnicodeDecodeError:
            return False
    return all(ch in "\t\n\r\f\v" or ch >= " " for ch in text)
