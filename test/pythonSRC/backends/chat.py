"""The ``openai`` chat driver: POST one chat-completion turn to a single backend
and return the reply text. This is the sole network seam for the ``chat``
dispatcher — tests monkeypatch ``_chat_once`` (or ``requests.post`` underneath).
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from ._http import BackendError, _build_headers, _post_with_retries, _timeouts_for


def _apply_chat_params(body: Dict[str, Any], params: Optional[Dict[str, Any]]) -> None:
    """Fold optional decode *params* into the request *body*, in place.

    Recognised keys (all optional, all pass-through to the OpenAI-compatible
    endpoint — llama.cpp accepts ``grammar`` (GBNF) and ``seed`` natively):

    * ``temperature`` — overrides the hardcoded ``0.0`` default when present and
      not ``None`` (so callers who omit it keep the deterministic default);
    * ``grammar`` — a GBNF string that constrains the decoder ("grade floor");
    * ``seed`` — an int for per-call variation (used by ``retry_until_valid`` to
      vary attempts without touching temperature).

    Unknown keys are ignored. ``params=None``/``{}`` leaves *body* byte-identical
    to the pre-``params`` behaviour, so the default call path is unchanged.
    """
    if not params:
        return
    temperature = params.get("temperature")
    if temperature is not None:
        body["temperature"] = temperature
    grammar = params.get("grammar")
    if grammar:
        body["grammar"] = grammar
    seed = params.get("seed")
    if seed is not None:
        body["seed"] = seed


def _chat_once(
    backend: Dict[str, Any],
    system_prompt: str,
    user_content: str,
    *,
    timeout: Optional[float] = None,
    max_retries: int,
    params: Optional[Dict[str, Any]] = None,
    messages: Optional[list] = None,
) -> str:
    """POST one chat-completion turn to a single ``openai-chat`` backend and
    return the reply text. Raises :class:`BackendError` on missing credentials,
    network failure after retries, a read timeout (cold model load too slow), a
    non-2xx response, or an unparseable reply.

    *timeout* is the READ-timeout default (seconds); a per-backend ``timeout`` in
    config overrides it. The connect timeout is short and separate (see
    :func:`_http._timeouts_for`). A slow read is treated as a model still loading
    and is NOT retried; only a fast connect/transport failure is.

    *params* (optional) carries decode controls (``temperature``/``grammar``/
    ``seed``) folded into the request body by :func:`_apply_chat_params`. Omitted
    → ``temperature`` stays ``0.0`` and no ``grammar``/``seed`` is sent, i.e. the
    body is identical to the pre-``params`` behaviour. This is the transport seam
    the lab's ``llm_call`` drives for GBNF-constrained / seed-varied passes.

    *messages* (optional) — a NATIVE OpenAI messages array (``[{"role","content"}…]``)
    for a genuine multi-turn conversation. When given, it is sent VERBATIM as the
    request ``messages`` (so the llama.cpp server applies the model's own
    chat-template from the GGUF), and *system_prompt*/*user_content* are ignored.
    Omitted (``None``) → the historical single-turn ``[{system},{user}]`` body, so
    the default path is byte-identical. (Added Plan01.07 — proper multi-turn without
    hand-rolling a template.) *params* still applies in both paths.

    This is the one function tests monkeypatch to simulate a backend without
    real HTTP; :func:`chat` never talks to the network except through here.
    """
    base_url = backend.get("base_url")
    model = backend.get("model")
    if not isinstance(base_url, str) or not base_url:
        raise BackendError(f"backend {backend.get('name')!r} has no base_url")
    if not isinstance(model, str) or not model:
        raise BackendError(f"backend {backend.get('name')!r} has no model")

    url = base_url.rstrip("/") + "/chat/completions"
    headers = _build_headers(backend)
    body = {
        "model": model,
        "messages": messages if messages is not None else [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0.0,
    }
    _apply_chat_params(body, params)

    connect_to, read_to = _timeouts_for(backend, timeout)
    resp = _post_with_retries(
        url, headers, body, name=backend.get("name"),
        connect_to=connect_to, read_to=read_to, max_retries=max_retries,
    )

    if resp.status_code != 200:
        raise BackendError(
            f"backend {backend.get('name')!r} HTTP {resp.status_code}: {resp.text[:500]}",
            status_code=resp.status_code,
        )
    try:
        payload = resp.json()
        content = payload["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise BackendError(
            f"backend {backend.get('name')!r} reply missing choices[0].message.content: {exc}"
        ) from exc

    if not isinstance(content, str) or not content.strip():
        raise BackendError(f"backend {backend.get('name')!r} returned empty content")
    return content
