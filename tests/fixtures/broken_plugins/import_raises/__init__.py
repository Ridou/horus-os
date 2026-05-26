"""TEST-19 fixture: module that raises at import time.

The ``raise`` statement at module scope fires the moment
``importlib.import_module("tests.fixtures.broken_plugins.import_raises")``
runs, before ``make_tool`` is reachable. ``PluginLoader.load()`` catches
the resulting ``RuntimeError`` and returns
``PluginLoadResult(status="error", error_phase="load")``.

The ``make_tool`` factory is declared in the manifest's
``[[contributions.tools]]`` so the loader has a real entry-point string
to resolve; the import-time raise means the loader never reaches the
factory call.
"""

raise RuntimeError(
    "import_raises is intentionally broken; this is a TEST-19 fixture "
    "for error_phase='load' (module-import failure)"
)


def make_tool():  # pragma: no cover — unreachable; module raises at import
    """Factory the manifest declares; never executes because of the raise above."""
    raise AssertionError("unreachable")
