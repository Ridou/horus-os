"""Plugin runtime package.

Public API for plugin authors lives in ``horus_os.plugins.api``; internal
modules (``spec``, ``capability_catalog``, ``manifest``, plus the
future ``discovery``, ``loader``, ``permissions``, ``health``) are NOT
part of the stable contract.

See Pitfall 8 in ``.planning/research/PITFALLS.md`` for the rationale
behind the single-public-surface rule (Phase 48 will enforce it via
a ruff custom rule against the reference plugin).
"""
