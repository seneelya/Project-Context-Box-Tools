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