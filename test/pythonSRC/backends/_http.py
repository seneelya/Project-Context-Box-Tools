"""Shared HTTP plumbing for the backend drivers (``chat`` / ``rerank`` both POST
JSON to an openai-compatible llama.cpp endpoint with identical retry/timeout
semantics). Extracted so the cold-load timeout policy lives in ONE place.

Nothing here resolves chains or knows about a specific service kind — it is the
transport floor: the error type, the split connect/read timeouts, header/auth
building, and the retry loop. The driver modules (``chat``/``rerank_driver``)
build their own request body and parse their own reply shape on top of this.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger("memohood.backends")

# Split connect/read timeouts, because llama.cpp acts as a model ROUTER: the
# first request naming a not-yet-loaded model holds the connection open while the
# model loads into VRAM (tens of seconds for a big model like Ornith-35B), then
# answers. So:
#   * CONNECT timeout stays short — "is the server process even up?" A dead port
#     fails fast and IS worth a retry (the server may be mid-restart).
#   * READ timeout must be generous — a slow read is almost always a cold model
#     LOAD in progress, not a hang; retrying it would just queue ANOTHER load and
#     make things worse, so a read timeout is a terminal failure here, not retried.
# A model that fails to load returns a normal HTTP error (surfaced as BackendError
# with status_code), not a timeout.
_DEFAULT_CONNECT_TIMEOUT_S = 5.0
_DEFAULT_READ_TIMEOUT_S = 120.0
DEFAULT_TIMEOUT_S = _DEFAULT_READ_TIMEOUT_S  # back-compat alias (read timeout)
MAX_RETRIES = 3
_RETRYABLE_STATUS = (429, 500, 502, 503, 504)

# time is imported at module scope (not lazily) so a test can monkeypatch
# ``time.sleep`` via the package's re-exported ``time`` attribute and have the
# retry loop below see it (the module object is a process-wide singleton).
import time


class BackendError(RuntimeError):
    """A single backend call failed. Never escapes :func:`chat`/:func:`embed`/
    :func:`rerank` — they catch it and try the next backend in the chain, then
    degrade (``None`` / ``rrf-only``).

    ``status_code`` carries the HTTP status on a non-2xx reply, or ``None`` when
    no response arrived (network error/timeout after retries, missing api key,
    unparseable reply)."""

    def __init__(self, message: str, *, status_code: Optional[int] = None) -> None:
        super().__init__(message)
        self.status_code = status_code


def _timeouts_for(backend: Dict[str, Any], read_default: Optional[float]) -> Tuple[float, float]:
    """Resolve ``(connect, read)`` timeouts for *backend*. A per-backend
    ``connect_timeout``/``timeout`` (read) in config overrides the defaults —
    e.g. a big model on 5000 may want ``timeout: 180`` for its cold load, while a
    fast cloud endpoint may want ``timeout: 30``. Per the v0.2 schema ``0`` (or
    absent) means "auto": fall back to *read_default* / the module default."""
    connect = backend.get("connect_timeout")
    read = backend.get("timeout")
    if read is None or read == 0:  # 0 = auto (v0.2)
        read = read_default if read_default is not None else _DEFAULT_READ_TIMEOUT_S
    try:
        connect_f = (
            float(connect) if connect not in (None, 0) else _DEFAULT_CONNECT_TIMEOUT_S
        )
    except (TypeError, ValueError):
        connect_f = _DEFAULT_CONNECT_TIMEOUT_S
    try:
        read_f = float(read)
    except (TypeError, ValueError):
        read_f = _DEFAULT_READ_TIMEOUT_S
    return (connect_f, read_f)


def _api_key_for(backend: Dict[str, Any]) -> Optional[str]:
    """Read the backend's API key from the env var it names (``api_key_env``).
    Returns ``None`` if no env var is named (local servers usually need none)."""
    env_name = backend.get("api_key_env")
    if not isinstance(env_name, str) or not env_name:
        return None
    return os.environ.get(env_name)


def _build_headers(backend: Dict[str, Any]) -> Dict[str, str]:
    """Build the request headers for an openai-compatible POST: JSON content type,
    the project-wide browser-like User-Agent (a nicety — never block on it), and a
    Bearer ``Authorization`` when the backend names an ``api_key_env``. Raises
    :class:`BackendError` if the env var is named but unset (a cloud backend that
    can't authenticate must fail this backend and fall through, not send an
    unauthenticated request)."""
    headers = {"Content-Type": "application/json"}
    try:
        from ..security import DEFAULT_USER_AGENT

        headers["User-Agent"] = DEFAULT_USER_AGENT
    except Exception:  # noqa: BLE001 - UA is a nicety, never block a call on it
        pass

    env_name = backend.get("api_key_env")
    if isinstance(env_name, str) and env_name:
        api_key = os.environ.get(env_name)
        if not api_key:
            raise BackendError(
                f"backend {backend.get('name')!r} needs env {env_name} but it is unset"
            )
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def _post_with_retries(
    url: str,
    headers: Dict[str, str],
    body: Dict[str, Any],
    *,
    name: Any,
    connect_to: float,
    read_to: float,
    max_retries: int,
):
    """POST *body* to *url* with the cold-load-aware retry policy, returning the
    ``requests`` Response (the caller checks ``status_code`` and parses the body).

    Raises :class:`BackendError` on a read timeout (treated as a cold model LOAD
    still in progress — TERMINAL, dialed exactly once, never retried) or on a
    connect/transport failure after *max_retries* (server down/restarting — worth
    a bounded retry). A retryable HTTP status (429/5xx) is retried up to
    *max_retries*, then the Response is returned as-is for the caller to surface.

    This is the single network seam shared by ``_chat_once`` and ``_rerank_once``;
    tests monkeypatch ``requests.post`` (a process-wide singleton) to avoid HTTP.
    """
    import requests  # heavy/optional import kept local

    attempt = 0
    while True:
        try:
            resp = requests.post(url, headers=headers, json=body, timeout=(connect_to, read_to))
        except requests.exceptions.ReadTimeout as exc:
            # Connection was made but the reply didn't arrive within read_to —
            # almost always a cold model LOAD still in progress. Retrying would
            # enqueue another load and worsen it, so fail terminally (no retry).
            raise BackendError(
                f"backend {name!r} read timeout after {read_to:.0f}s "
                f"(model still loading, or inference too slow?)",
                status_code=None,
            ) from exc
        except requests.RequestException as exc:
            # Connect error / reset / DNS — server down or mid-restart. Fast to
            # detect (short connect timeout) and worth a bounded retry.
            if attempt >= max_retries:
                raise BackendError(
                    f"request to {url} failed after {attempt} retries: {exc}", status_code=None,
                ) from exc
            time.sleep(min(2 ** attempt, 30))
            attempt += 1
            continue

        if resp.status_code in _RETRYABLE_STATUS and attempt < max_retries:
            time.sleep(min(2 ** attempt, 30))
            attempt += 1
            continue
        return resp
