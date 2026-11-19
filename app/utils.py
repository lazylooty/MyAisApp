from decimal import Decimal, InvalidOperation
from typing import Optional
from urllib.parse import urlencode

from fastapi.responses import RedirectResponse


def safe_local_redirect(path: Optional[str], default: str = "/") -> str:
    """Allow only relative local redirects to prevent open-redirect vulnerabilities."""
    if not path:
        return default
    candidate = path.strip()
    if not candidate.startswith("/") or candidate.startswith("//"):
        return default
    return candidate.split("?", 1)[0]


def flash_redirect(
    path: str,
    *,
    message: Optional[str] = None,
    error: Optional[str] = None,
    **extra_params: str | int,
) -> RedirectResponse:
    """Standard PRG (Post/Redirect/Get) helper with safe query encoding."""
    base = safe_local_redirect(path, default="/")
    params = {}
    if message:
        params["message"] = message
    if error:
        params["error"] = error
    for key, val in extra_params.items():
        if val is not None and str(val) != "":
            params[key] = str(val)
    url = f"{base}?{urlencode(params)}" if params else base
    return RedirectResponse(url=url, status_code=303)


def parse_opt_int(raw: Optional[str]) -> Optional[int]:
    if not raw:
        return None
    cleaned = raw.strip()
    if not cleaned:
        return None
    try:
        value = int(cleaned)
    except ValueError:
        return None
    return value if value > 0 else None


def parse_opt_positive_float(raw: Optional[str]) -> Optional[float]:
    if not raw:
        return None
    cleaned = raw.strip().replace(" ", "").replace(",", ".")
    if not cleaned:
        return None
    try:
        value = float(cleaned)
    except ValueError:
        return None
    return value if value > 0 else None


def parse_opt_decimal(raw: Optional[str]) -> Optional[Decimal]:
    if not raw:
        return None
    cleaned = raw.strip().replace(" ", "").replace(",", ".")
    if not cleaned:
        return None
    try:
        value = Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return None
    return value if value > 0 else None
