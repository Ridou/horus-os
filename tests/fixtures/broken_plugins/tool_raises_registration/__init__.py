"""TEST-19 fixture: tool factory raises during registration.

The module imports cleanly, so ``PluginLoader.load()`` reaches the
``make_tool`` factory. The factory then raises ``ValueError``, which
the loader catches and surfaces as
``PluginLoadResult(status="error", error_phase="load",
error="ValueError: ...")``.

This exercises the loader's rollback path: any tool / adapter the
loader registered BEFORE the failing factory call must be unregistered
from the master registries by the time ``load()`` returns. The fixture
declares a single tool so the rollback list is trivial, but the
contract is the same when multiple tools partial-register before a
failure.
"""

from horus_os.types import Tool


def make_tool() -> Tool:
    """Factory the manifest declares; raises ValueError on every call.

    The PluginLoader resolves the entry point, gets this callable
    back, and calls it once. The exception bubbles up into the
    loader's try/except wrap.
    """
    raise ValueError(
        "tool_raises_registration.make_tool is intentionally broken; "
        "this is a TEST-19 fixture for error_phase='load' (factory failure)"
    )
