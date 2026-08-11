"""The embedding drivers: dispatch a single backend's embed call to the helper
in ``_engine.embed`` that owns the actual HTTP/ONNX + vector validation.

``openai-embedder`` -> OpenAI-shaped ``{base_url}/embeddings`` (5002 and any
openai-compatible cloud endpoint); ``fastembed`` -> on-box in-process ONNX.
``_embed_once`` is the seam the ``embed`` dispatcher and selftest monkeypatch.
"""

from __future__ import annotations

from typing import Any, Dict, List

from ._http import BackendError, _api_key_for


def _embed_once(backend: Dict[str, Any], texts: List[str], *, is_query: bool = False) -> List[List[float]]:
    """Embed *texts* via a single backend, dispatching on ``provider`` to the
    corresponding helper in ``_engine.embed`` (which owns all embedding HTTP,
    batching, and vector validation). Raises :class:`BackendError` on any
    failure. The seam tests monkeypatch to avoid real HTTP.

    For ``openai-embedder`` the backend's ``prompt_style`` is applied first (e.g.
    harrier's asymmetric Instruct prompt for queries; a no-op for a plain
    embedder). ``fastembed`` keeps its own model-name e5 auto-prefix inside
    ``_embed_local``, so no styling is applied here. Unlike ``chat``, embedding
    requests carry no per-backend split timeout yet — embed models are small (fast
    cold load), so ``embed.py``'s single timeout is adequate.
    """
    from .. import embed as embed_mod  # lazy: embed.py pulls in db/security

    provider = backend.get("provider")
    name = backend.get("name")
    try:
        if provider == "openai-embedder":
            base_url = backend.get("base_url")
            if not isinstance(base_url, str) or not base_url:
                raise BackendError(f"embedder backend {name!r} has no base_url")
            # Apply the backend's prompt_style (e.g. harrier's asymmetric Instruct
            # prompt) before sending. Default/none = unchanged, so this is a no-op
            # for plain embedders like Gemma-5002.
            prepared = embed_mod.apply_prompt_style(
                texts, backend.get("prompt_style"),
                is_query=is_query, task=backend.get("prompt_task"),
            )
            return embed_mod._embed_openai_compat(
                prepared, base_url=base_url, model=backend.get("model"), api_key=_api_key_for(backend),
            )
        if provider == "fastembed":
            return embed_mod._embed_local(texts, backend.get("model"), is_query=is_query)
        raise BackendError(f"backend {name!r} provider {provider!r} is not an embedder driver")
    except embed_mod.EmbedError as exc:
        raise BackendError(f"embed via {name!r} failed: {exc}", status_code=None) from exc
