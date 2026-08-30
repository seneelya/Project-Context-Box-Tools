"""Fixture for REQ-006: module-level constants — public ones must reach the card, private ones
must not (unless separately consumed — that path is Consumed internals, not this fixture)."""

from __future__ import annotations

KNOWN_SEAMS = ("alpha", "beta", "gamma", "delta", "epsilon", "zeta", "eta")

_PRIVATE_LIMIT = 42


def public_fn(x: int) -> int:
    return x + _PRIVATE_LIMIT
