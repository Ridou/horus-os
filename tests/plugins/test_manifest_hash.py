"""Determinism, order-independence, and set-sensitivity tests for
``compute_manifest_hash``.

Phase 43's permission gate persists the hash on grant rows and
compares against a freshly-computed value on upgrade; mismatch flips
state to ``'pending'`` and re-prompts. These three properties are
what make that comparison meaningful.
"""

from __future__ import annotations

from horus_os.plugins.manifest import compute_manifest_hash


def test_hash_is_deterministic() -> None:
    h1 = compute_manifest_hash(["filesystem.read", "net.outbound"])
    h2 = compute_manifest_hash(["filesystem.read", "net.outbound"])
    assert h1 == h2
    assert len(h1) == 64


def test_hash_is_order_independent() -> None:
    h1 = compute_manifest_hash(["filesystem.read", "net.outbound"])
    h2 = compute_manifest_hash(["net.outbound", "filesystem.read"])
    assert h1 == h2


def test_hash_changes_when_capability_set_changes() -> None:
    h1 = compute_manifest_hash(["filesystem.read"])
    h2 = compute_manifest_hash(["filesystem.read", "net.outbound"])
    assert h1 != h2


def test_hash_is_duplicate_tolerant() -> None:
    """Duplicate entries in the input collapse to the same hash (set)."""
    h1 = compute_manifest_hash(["filesystem.read", "filesystem.read"])
    h2 = compute_manifest_hash(["filesystem.read"])
    assert h1 == h2


def test_hash_of_empty_capability_set() -> None:
    """Empty capability set is still hashable and deterministic."""
    h1 = compute_manifest_hash([])
    h2 = compute_manifest_hash(set())
    assert h1 == h2
    assert len(h1) == 64


def test_hash_is_lowercase_hex() -> None:
    h = compute_manifest_hash(["filesystem.read", "net.outbound", "secrets.read"])
    assert all(c in "0123456789abcdef" for c in h)
