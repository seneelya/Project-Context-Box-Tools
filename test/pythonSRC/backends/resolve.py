"""Config → resolved backend chains. Pure, offline, network-free: turns the
``backends`` pool + ``roles`` map into an ordered fallback chain of normalized
backend dicts, and enforces the embedder-chain "same footprint" invariant.

Nothing here dials a backend — that is the driver modules' job. Split out so the
resolution logic (the part unit-tested most heavily, and reused by every
dispatcher) reads on its own without the HTTP drivers in the way.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

logger = logging.getLogger("memohood.backends")

# Backends whose base_url points at a private/local host: no cost ledger, and
# they must be allowlisted past the SSRF guard when the call sites are wired up.
_LOCAL_HOST_SUFFIXES = ("localhost",)

# A role may only START on a backend of its own service ``kind`` (v0.2 guard).
_ROLE_KIND = {"llm": "llm", "embedder": "embedder", "reranker": "reranker"}


def _backends_map(cfg: Optional[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Normalize the ``backends`` pool to a ``name -> definition`` map, accepting
    either the v0.2 LIST-of-objects form (each item carries its own ``name``) or
    a legacy ``name -> object`` mapping. List items without a usable ``name`` are
    dropped."""
    section = (cfg or {}).get("backends")
    if isinstance(section, list):
        out: Dict[str, Dict[str, Any]] = {}
        for item in section:
            if isinstance(item, dict):
                name = item.get("name")
                if isinstance(name, str) and name:
                    out[name] = item
        return out
    return section if isinstance(section, dict) else {}


def _roles_section(cfg: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    section = (cfg or {}).get("roles")
    return section if isinstance(section, dict) else {}


def _normalize_backend(name: str, definition: Dict[str, Any]) -> Dict[str, Any]:
    """Return a copy of *definition* with ``name`` set and every v0.2 field
    filled to its default: ``model_name`` <- ``model``, ``dims`` <- 0, and
    ``footprint`` <- ``"{model_name}|{dims}"`` (the DB passport; the owner may
    override it explicitly). Staged fields are left untouched — parsed if present,
    ignored by the callers."""
    b = dict(definition)
    b["name"] = name
    model = b.get("model") or ""
    if not (isinstance(b.get("model_name"), str) and b.get("model_name")):
        b["model_name"] = model
    dims = b.get("dims")
    if not isinstance(dims, int):
        dims = 0
        b["dims"] = 0
    if not (isinstance(b.get("footprint"), str) and b.get("footprint")):
        b["footprint"] = f"{b['model_name']}|{dims}"
    return b


def _fallback_names(backend: Dict[str, Any]) -> List[str]:
    """Normalize a backend's ``fallback`` (absent | str | list) to a list of
    names, dropping empties/non-strings."""
    raw = backend.get("fallback")
    if raw is None or raw == "":
        return []
    if isinstance(raw, str):
        return [raw]
    if isinstance(raw, (list, tuple)):
        return [n for n in raw if isinstance(n, str) and n]
    return []


def is_local_backend(backend: Dict[str, Any]) -> bool:
    """True if the backend targets a private/loopback host — used to skip the
    cost ledger and (later) to allowlist it past the SSRF guard. Cloud
    endpoints (Gemini/Cloudflare/Cohere) return False."""
    if backend.get("provider") == "fastembed":
        return True  # in-process ONNX — as local as it gets (no HTTP, no cost)
    base_url = backend.get("base_url")
    if not isinstance(base_url, str) or not base_url or base_url == "in-process":
        # No dialable URL → cloud SDK (cohere-rerank) or in-process: not remote-local.
        return False
    try:
        host = urlparse(base_url).hostname or ""
    except ValueError:
        return False
    host = host.lower()
    if host in ("localhost",) or host.endswith(_LOCAL_HOST_SUFFIXES):
        return True
    import ipaddress

    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return ip.is_private or ip.is_loopback


def resolve_chain(cfg: Optional[Dict[str, Any]], role: str) -> List[Dict[str, Any]]:
    """Resolve *role* to an ordered list of resolved backend dicts by starting
    at ``roles[role]`` and walking each backend's ``fallback`` links.

    Each returned dict is the backend's config dict plus a ``"name"`` key. The
    walk is breadth-first over the fallback links, cycle-safe (a backend is
    visited at most once) and stops at names that don't exist in ``backends``
    (logged and skipped). Returns ``[]`` if the role is unset or its starting
    backend is missing — callers degrade from an empty chain exactly as from a
    fully-failed one.

    For ``role == "embedder"`` the resolved chain is additionally passed through
    :func:`validate_embedder_chain`, which truncates it at the first
    ``model``/``dims`` divergence (a different embedding model is a paradigm
    change, not a fallback).
    """
    backends = _backends_map(cfg)
    roles = _roles_section(cfg)

    start = roles.get(role)
    if not isinstance(start, str) or not start:
        logger.debug("backends.resolve_chain: role %r has no starting backend", role)
        return []

    # Guard: a role should start on a backend of its own service kind. This is a
    # loud WARNING, not a hard drop — the dispatch layer (chat/embed) still skips
    # any wrong-provider backend, and we must keep walking the fallback links.
    expected_kind = _ROLE_KIND.get(role)
    start_def = backends.get(start)
    if (
        expected_kind
        and isinstance(start_def, dict)
        and start_def.get("kind")
        and start_def.get("kind") != expected_kind
    ):
        logger.warning(
            "backends.resolve_chain: role %r starts on backend %r of kind %r "
            "(expected %r) — check config.roles",
            role, start, start_def.get("kind"), expected_kind,
        )

    chain: List[Dict[str, Any]] = []
    visited: set = set()
    queue: List[str] = [start]
    while queue:
        name = queue.pop(0)
        if name in visited:
            continue
        visited.add(name)
        definition = backends.get(name)
        if not isinstance(definition, dict):
            logger.warning(
                "backends.resolve_chain: role %r references unknown backend %r; skipping",
                role, name,
            )
            continue
        chain.append(_normalize_backend(name, definition))
        queue.extend(fb for fb in _fallback_names(definition) if fb not in visited)

    if role == "embedder":
        chain = validate_embedder_chain(chain)
    return chain


def _embedder_chain_key(backend: Dict[str, Any]) -> str:
    """The identity an embedder fallback chain must keep constant: the
    ``footprint`` (``model_name|dims``). Deliberately NOT the raw ``model`` — a
    CPU-quant of the same model has a DIFFERENT server ``model`` string
    (e.g. ``...-Q8_0`` vs ``...-Q8_0-CPU``) but the SAME ``model_name`` and
    ``dims``, so it is a valid same-model fallback. A genuine paradigm change
    (different model_name or dims) changes this key."""
    fp = backend.get("footprint")
    if isinstance(fp, str) and fp:
        return fp
    name = backend.get("model_name") or backend.get("model")
    return f"{name}|{backend.get('dims')}"


def validate_embedder_chain(chain: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Enforce the "same model on a different runtime" invariant for an embedder
    fallback chain: every backend must share the head's ``footprint``
    (``model_name|dims``), NOT its raw ``model`` string.

    Returns the longest prefix of *chain* consistent with the head. A backend
    whose footprint differs (and everything after it) is dropped with a warning —
    reaching a different model_name/dims through the fallback path would silently
    corrupt the vector space (mixing incompatible vectors), so that is an explicit
    re-embed operation, not a fallback. A CPU-quant on a different ``model``
    string but the SAME ``model_name``/``dims`` IS a valid fallback (that is the
    whole point of footprint being model_name-based). Empty/1-element chains pass
    through unchanged.
    """
    if len(chain) <= 1:
        return chain
    head = chain[0]
    head_key = _embedder_chain_key(head)
    kept: List[Dict[str, Any]] = [head]
    for link in chain[1:]:
        if _embedder_chain_key(link) != head_key:
            logger.warning(
                "backends.validate_embedder_chain: backend %r (footprint=%r) diverges "
                "from head %r (footprint=%r); truncating fallback chain here — a "
                "different embedding model_name/dims is a paradigm change (re-embed), "
                "not a fallback.",
                link.get("name"), _embedder_chain_key(link),
                head.get("name"), head_key,
            )
            break
        kept.append(link)
    return kept
