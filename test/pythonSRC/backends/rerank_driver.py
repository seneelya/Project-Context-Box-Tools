"""The reranker driver: cross-encoder reranking over an openai-compatible
llama.cpp rerank endpoint.

A reranker takes (query, [documents]) and returns a relevance score per document
— a cross-encoder, so it catches signal a bi-encoder embedder misses (e.g.
polarity love/hate). Drivers:
  * ``openai-rerank`` — llama.cpp / any openai-compatible rerank server. The
    route is ``{host}/rerank`` (llama.cpp exposes rerank at the ROOT, not under
    ``/v1`` — a ``base_url`` ending in ``/v1`` is stripped back to the host).
    Body ``{model, query, documents}`` → ``{"results":[{index, relevance_score}]}``
    (Cohere-shaped). This is the owner's BGE/Qwen on 5003/6000.
  * ``cohere-rerank`` — the cloud SDK path, still served by the legacy
    ``_engine/rerank.py`` (not dialed from here yet; declared for forward-compat).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ._http import BackendError, _build_headers, _post_with_retries, _timeouts_for, logger

_RERANK_PROVIDERS = ("openai-rerank", "cohere-rerank")

# Cap chars per document — bounds request size and avoids shipping a
# pathologically huge chunk to a reranker (which has a fixed context window).
_RERANK_MAX_DOC_CHARS = 6000


def _apply_score_transform(score: float, transform: Optional[str]) -> float:
    """Map a raw reranker score to a comparable scale per the backend's
    ``score_transform``. Cross-encoders differ: BGE returns raw LOGITS (any real,
    e.g. -6.8..-0.5) while Qwen already returns 0..1 — so we must know per backend
    whether to squash. ``sigmoid`` = ``1/(1+e^-x)`` (BGE); ``none``/``raw``/``""``
    = leave as-is (Qwen). Unknown value logs a warning and passes through raw."""
    t = (transform or "").strip().lower()
    if t in ("", "none", "raw"):
        return score
    if t == "sigmoid":
        import math

        try:
            return 1.0 / (1.0 + math.exp(-score))
        except OverflowError:
            return 0.0 if score < 0 else 1.0
    logger.warning("backends: unknown score_transform %r; passing score through raw", transform)
    return score


def _rerank_once(
    backend: Dict[str, Any],
    query: str,
    documents: List[str],
    *,
    timeout: Optional[float] = None,
    max_retries: int,
) -> List[Dict[str, Any]]:
    """POST one rerank request to a single ``openai-rerank`` backend and return a
    list of ``{"index": int, "score": float}`` — the score already run through the
    backend's ``score_transform``. Raises :class:`BackendError` on missing
    base_url/model, network failure after retries, a read timeout, a non-2xx
    response, or an unparseable reply. Retry/timeout semantics mirror
    :func:`chat._chat_once`. Tests monkeypatch this seam to avoid real HTTP.
    """
    provider = backend.get("provider")
    name = backend.get("name")
    if provider == "cohere-rerank":
        # The cloud SDK path still lives in _engine/rerank.py; not dialed here.
        raise BackendError(f"reranker backend {name!r} provider 'cohere-rerank' not dialed from backends; use _engine/rerank.py")
    if provider != "openai-rerank":
        raise BackendError(f"backend {name!r} provider {provider!r} is not a rerank driver")

    base_url = backend.get("base_url")
    model = backend.get("model")
    if not isinstance(base_url, str) or not base_url:
        raise BackendError(f"reranker backend {name!r} has no base_url")
    if not isinstance(model, str) or not model:
        raise BackendError(f"reranker backend {name!r} has no model")

    # llama.cpp serves rerank at the ROOT (`/rerank`), NOT under `/v1`. Strip a
    # trailing `/v1` so a base_url shared with the embed/chat convention still hits
    # the right route (proven live: http://192.168.1.40:5003/rerank).
    root = base_url.rstrip("/")
    if root.endswith("/v1"):
        root = root[: -len("/v1")].rstrip("/")
    url = root + "/rerank"

    headers = _build_headers(backend)
    body = {
        "model": model,
        "query": query,
        "documents": [d[:_RERANK_MAX_DOC_CHARS] for d in documents],
    }

    connect_to, read_to = _timeouts_for(backend, timeout)
    resp = _post_with_retries(
        url, headers, body, name=name,
        connect_to=connect_to, read_to=read_to, max_retries=max_retries,
    )

    if resp.status_code != 200:
        raise BackendError(
            f"reranker backend {name!r} HTTP {resp.status_code}: {resp.text[:500]}",
            status_code=resp.status_code,
        )
    try:
        payload = resp.json()
        results = payload["results"]
    except (ValueError, KeyError, TypeError) as exc:
        raise BackendError(
            f"reranker backend {name!r} reply missing results[]: {exc}"
        ) from exc
    if not isinstance(results, list):
        raise BackendError(f"reranker backend {name!r} results is not a list: {str(payload)[:300]}")

    transform = backend.get("score_transform")
    out: List[Dict[str, Any]] = []
    for r in results:
        if not isinstance(r, dict):
            continue
        idx = r.get("index")
        raw = r.get("relevance_score", r.get("score"))
        if not isinstance(idx, int) or not isinstance(raw, (int, float)):
            continue
        out.append({"index": idx, "score": _apply_score_transform(float(raw), transform)})
    if not out:
        raise BackendError(f"reranker backend {name!r} returned no usable results")
    return out


def _rank_candidates(candidates: List[Dict[str, Any]], results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Reorder *candidates* by *results* (``[{index, score}]``, score already
    transformed), adding a ``rerank_score`` key to each. Indices out of range or
    duplicated are ignored; any candidate the reranker omitted is appended at the
    end in its original order with ``rerank_score = 0.0`` (never silently drop)."""
    ranked: List[Dict[str, Any]] = []
    seen: set = set()
    for r in sorted(results, key=lambda x: x.get("score", 0.0), reverse=True):
        idx = r.get("index")
        if not isinstance(idx, int) or idx < 0 or idx >= len(candidates) or idx in seen:
            continue
        seen.add(idx)
        item = dict(candidates[idx])
        item["rerank_score"] = float(r.get("score", 0.0))
        ranked.append(item)
    if len(ranked) < len(candidates):
        for i, c in enumerate(candidates):
            if i not in seen:
                item = dict(c)
                item.setdefault("rerank_score", 0.0)
                ranked.append(item)
    return ranked
