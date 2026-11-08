"""One shared clerk password for the local scanner. Put TLS in front on a LAN."""
import base64
import binascii
import hmac
import os
from fastapi import HTTPException, Request


def check_access(request: Request):
    password = os.getenv("SCANNER_ACCESS_PASSWORD", "")
    if not password:
        raise HTTPException(503, "Set SCANNER_ACCESS_PASSWORD before starting the scanner.")
    header = request.headers.get("authorization", "")
    try:
        scheme, encoded = header.split(" ", 1)
        decoded = base64.b64decode(encoded, validate=True).decode("utf-8")
        username, supplied = decoded.split(":", 1)
    except (ValueError, UnicodeError, binascii.Error):
        scheme = username = supplied = ""
    if scheme.lower() != "basic" or not hmac.compare_digest(username, "clerk") or not hmac.compare_digest(supplied, password):
        raise HTTPException(401, "Clerk password required.", headers={"WWW-Authenticate": 'Basic realm="Sample Scanner"'})
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        if request.headers.get("sec-fetch-site") == "cross-site":
            raise HTTPException(403, "Origin not allowed.")
        origin = request.headers.get("origin")
        if origin:
            allowed = {f"{request.url.scheme}://{request.headers.get('host', '')}"}
            allowed.update(x.strip() for x in os.getenv("SCANNER_ALLOWED_ORIGINS", "").split(",") if x.strip())
            if origin not in allowed:
                raise HTTPException(403, "Origin not allowed.")
