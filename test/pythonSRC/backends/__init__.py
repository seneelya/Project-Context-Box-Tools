"""Configurable backend orchestration for memohood (see
``_Plan/Design_BackendSchema_v0.2_FINAL.md``).

This package is the single place that turns a *role* ("llm", "embedder",
"reranker") into a concrete, ordered **fallback chain** of named backends and
drives the actual call, trying each backend in turn until one succeeds.

Layout (a module grown into a package — the public API stays importable as
``from ._engine import backends`` exactly as before):

* :mod:`._http` — transport floor: :class:`BackendError`, split connect/read
  timeouts, header/auth building, the cold-load-aware POST retry loop (shared by
  the chat and rerank drivers).
* :mod:`.resolve` — pure, offline config→chain resolution + the embedder-chain
  "same footprint" invariant. Network-free.
* :mod:`.chat` / :mod:`.embed_driver` / :mod:`.rerank_driver` — the per-service
  network seams (``_chat_once`` / ``_embed_once`` / ``_rerank_once``).

This ``__init__`` keeps the three **dispatchers** (:func:`chat` / :func:`embed`
/ :func:`rerank`) that walk a resolved chain first-success-wins, because they
reference the ``_*_once`` seams as module globals — which is what lets a test
``monkeypatch.setattr(backends, "_chat_once", ...)`` reach the real call site.

Design invariants (from the plan):

* **Fallback is the essence of a backend** — every backend may name a ``fallback``
  (a single name or a list); the chain is walked start → fallback…, cycle-safe.
* **Roles are only a hint** — a role names the *starting* backend; the resolver
  follows ``fallback`` links from there.
* **Embedder fallback = the SAME model on a different runtime** (GPU→CPU); the
  chain is truncated at the first ``footprint`` divergence (see
  :func:`.resolve.validate_embedder_chain`).
* **Never raises outward** — a failed call degrades (``None`` for chat/embed,
  ``(candidates, "rrf-only")`` for rerank) rather than crashing the caller.

v0.2 flat schema: a backend has ``kind`` = the *service type* (``llm`` /
``embedder`` / ``reranker`` — a role may only start on a backend of its own kind)
and ``provider`` = the *call driver* (``openai`` chat, ``openai-embedder``
embeddings, ``openai-rerank`` rerank, ``fastembed`` in-process ONNX;
``cohere-rerank`` declared, cloud path in ``_engine/rerank.py``).
"""

from __future__ import annotations

import logging
import time  # re-exported so tests can monkeypatch ``backends.time.sleep``
from typing import Any, Dict, List, Optional, Tuple

# --- transport floor -------------------------------------------------------
from ._http import (  # noqa: F401 - re-exported public/seam names
    BackendError,
    DEFAULT_TIMEOUT_S,
    MAX_RETRIES,
    _DEFAULT_CONNECT_TIMEOUT_S,
    _DEFAULT_READ_TIMEOUT_S,
    _RETRYABLE_STATUS,
    _api_key_for,
    _build_headers,
    _post_with_retries,
    _timeouts_for,
)

# --- config → chains (offline) ---------------------------------------------
from .resolve import (  # noqa: F401 - re-exported public/seam names
    _ROLE_KIND,
    _backends_map,
    _embedder_chain_key,
    _fallback_names,
    _normalize_backend,
    _roles_section,
    is_local_backend,
    resolve_chain,
    validate_embedder_chain,
)

# --- per-service network seams ---------------------------------------------
from .chat import _chat_once  # noqa: F401 - seam (monkeypatched by tests)
from .embed_driver import _embed_once  # noqa: F401 - seam
from .rerank_driver import (  # noqa: F401 - seam + rerank helpers
    _RERANK_PROVIDERS,
    _apply_score_transform,
    _rank_candidates,
    _rerank_once,
)

logger = logging.getLogger("memohood.backends")


# ---------------------------------------------------------------------------
# chat — openai-chat protocol, walk the chain
# ---------------------------------------------------------------------------


def chat(
    cfg: Optional[Dict[str, Any]],
    role: str,
    system_prompt: str,
    user_content: str,
    *,
    timeout: Optional[float] = None,
    max_retries: int = MAX_RETRIES,
    params: Optional[Dict[str, Any]] = None,
    messages: Optional[List[Dict[str, Any]]] = None,
) -> Optional[str]:
    """Run one chat turn against the *role*'s backend chain, returning the reply
    text of the FIRST backend that succeeds, or ``None`` if every backend in the
    chain fails (or the chain is empty). Never raises.

    *timeout* is the READ-timeout default (seconds), passed through to each
    backend; ``None`` means use the module default (generous, to allow a cold
    llama.cpp model load). A per-backend ``timeout`` in config overrides it.

    *params* (optional) carries decode controls (``temperature``/``grammar``/
    ``seed``) forwarded verbatim to each backend in the chain (see
    :func:`.chat._chat_once`). Omitted → deterministic ``temperature=0.0`` with
    no grammar/seed, i.e. the historical behaviour. This lets the lab drive
    GBNF-constrained / seed-varied passes through the same chain-walk transport,
    without the dispatcher interpreting the reply.

    *messages* (optional) — a NATIVE OpenAI messages array for a genuine multi-turn
    conversation; forwarded verbatim to the backend so the server applies the model's
    own chat-template (Plan01.07). Omitted → the historical ``system+user`` single-turn
    body, byte-identical to before (prod callers — recall/extract/copka — unaffected).

    This function is about *where* the call goes, not *what* is asked — it does
    not parse or reshape the reply (the core principle: the LLM answers one
    narrow question in natural language; the harness/caller builds structure).
    Only ``provider: openai`` backends are dialed; any other provider in the
    chain is skipped with a warning.
    """
    chain = resolve_chain(cfg, role)
    if not chain:
        logger.info("backends.chat: role %r resolved to an empty chain; degrading", role)
        return None

    last_exc: Optional[BackendError] = None
    for backend in chain:
        provider = backend.get("provider")
        if provider != "openai":
            logger.warning(
                "backends.chat: backend %r has provider %r (not an openai chat "
                "driver); skipping",
                backend.get("name"), provider,
            )
            continue
        try:
            # messages передаём В `_chat_once` ТОЛЬКО когда он задан → без него вызов
            # байт-в-байт прежний (существующие вызовы/тесты-фейки не видят нового kwarg).
            extra = {"messages": messages} if messages is not None else {}
            return _chat_once(
                backend, system_prompt, user_content,
                timeout=timeout, max_retries=max_retries, params=params, **extra,
            )
        except BackendError as exc:
            last_exc = exc
            logger.info(
                "backends.chat: backend %r failed (%s); trying next in chain",
                backend.get("name"), exc,
            )
            continue

    logger.warning(
        "backends.chat: all backends in role %r chain failed; degrading (last error: %s)",
        role, last_exc,
    )
    return None


# ---------------------------------------------------------------------------
# embed — walk the embedder chain (same-model/dims fallback)
# ---------------------------------------------------------------------------

_EMBED_PROVIDERS = ("openai-embedder", "fastembed")


def embed(
    cfg: Optional[Dict[str, Any]],
    role: str,
    texts: List[str],
    *,
    is_query: bool = False,
) -> Optional[List[List[float]]]:
    """Embed *texts* against the *role*'s backend chain, returning the vectors
    from the FIRST backend that succeeds, or ``None`` if every backend fails (or
    the chain is empty). ``[]`` for empty input. Never raises.

    The chain for ``role == "embedder"`` is dims-consistent by construction
    (:func:`.resolve.resolve_chain` truncates a divergent link), so every fallback
    here is the SAME model on a different runtime — vectors stay in one space.
    When a backend declares ``dims``, the returned vectors are validated against
    it (via ``embed.py``) before being accepted, so a misconfigured endpoint can't
    silently inject wrong-width vectors.

    NOTE (increment 3): this is the orchestration primitive + is exercised live
    by ``memohood_selftest(3)``, but the production ``embed.embed_texts`` routes
    through it via ``roles.embedder`` (path B done).
    """
    if not texts:
        return []
    chain = resolve_chain(cfg, role)
    if not chain:
        logger.info("backends.embed: role %r resolved to an empty chain; degrading", role)
        return None

    from .. import embed as embed_mod

    last_exc: Optional[BackendError] = None
    for backend in chain:
        if backend.get("kind") != "embedder":
            logger.warning(
                "backends.embed: backend %r has kind %r (not an embedder); skipping",
                backend.get("name"), backend.get("kind"),
            )
            continue
        try:
            vectors = _embed_once(backend, texts, is_query=is_query)
            dims = backend.get("dims")
            if isinstance(dims, int) and dims > 0:
                embed_mod._validate_vectors(vectors, dims, len(texts))
            return vectors
        except (BackendError, embed_mod.EmbedError) as exc:
            last_exc = exc if isinstance(exc, BackendError) else BackendError(str(exc))
            logger.info(
                "backends.embed: backend %r failed (%s); trying next in chain",
                backend.get("name"), exc,
            )
            continue

    logger.warning(
        "backends.embed: all backends in role %r chain failed; degrading (last error: %s)",
        role, last_exc,
    )
    return None


# ---------------------------------------------------------------------------
# rerank — cross-encoder reranking, walk the reranker chain
# ---------------------------------------------------------------------------


def rerank(
    cfg: Optional[Dict[str, Any]],
    role: str,
    query: str,
    candidates: List[Dict[str, Any]],
    *,
    timeout: Optional[float] = None,
    max_retries: int = MAX_RETRIES,
) -> Tuple[List[Dict[str, Any]], str]:
    """Rerank *candidates* (each a dict with a ``"text"`` key) against *query*
    using the *role* (``"reranker"``) backend chain. Returns ``(ranked, mode)``:

    * on success — *candidates* reordered with a ``rerank_score`` key added, and
      ``mode`` = the NAME of the backend that answered;
    * on any degradation (empty input, empty chain, every backend failed) —
      *candidates* UNCHANGED and ``mode == "rrf-only"`` (a valid, expected final
      state, NOT an error — the caller keeps its RRF order).

    Never raises. Mirrors :func:`embed`: kind-gated (only ``kind == "reranker"``
    backends are dialed), walks the fallback chain first-success-wins.

    NOTE (increment 4): this is the orchestration primitive + is exercised live by
    ``memohood_selftest(4)``. Wiring it into ``retrieve.hybrid_search`` (replacing
    the direct ``_engine/rerank.py`` Cohere call) is deferred to the CORE phase —
    the retrieval/ranking algorithm is being rewritten near-scratch, so we do not
    touch the live recall path here; we only prove the transport reaches + scores.
    """
    if not candidates:
        return candidates, "rrf-only"
    chain = resolve_chain(cfg, role)
    if not chain:
        logger.info("backends.rerank: role %r resolved to an empty chain; degrading to rrf-only", role)
        return candidates, "rrf-only"

    documents = [c.get("text") or "" for c in candidates]
    last_exc: Optional[BackendError] = None
    for backend in chain:
        if backend.get("kind") != "reranker":
            logger.warning(
                "backends.rerank: backend %r has kind %r (not a reranker); skipping",
                backend.get("name"), backend.get("kind"),
            )
            continue
        provider = backend.get("provider")
        if provider not in _RERANK_PROVIDERS:
            logger.warning(
                "backends.rerank: backend %r has provider %r (not a rerank driver); skipping",
                backend.get("name"), provider,
            )
            continue
        try:
            results = _rerank_once(backend, query, documents, timeout=timeout, max_retries=max_retries)
        except BackendError as exc:
            last_exc = exc
            logger.info(
                "backends.rerank: backend %r failed (%s); trying next in chain",
                backend.get("name"), exc,
            )
            continue
        return _rank_candidates(candidates, results), backend.get("name")

    logger.warning(
        "backends.rerank: all backends in role %r chain failed; degrading to rrf-only (last error: %s)",
        role, last_exc,
    )
    return candidates, "rrf-only"
