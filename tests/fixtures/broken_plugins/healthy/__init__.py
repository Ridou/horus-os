"""TEST-19 control fixture: a healthy plugin that loads cleanly.

``make_tool`` returns a working ``Tool`` named ``hello_tool`` whose
handler echoes its keyword arguments back. Used as the success path
in ``test_loader.py`` and as the alongside-broken-plugins control in
``test_loader_isolation.py`` to prove the isolation guarantee — a
healthy plugin still loads in the same pass as failing ones.
"""

from typing import Any

from horus_os.types import Tool


def _echo_handler(**kwargs: Any) -> dict[str, Any]:
    """Pass-through handler: returns its kwargs as ``{"echo": kwargs}``."""
    return {"echo": dict(kwargs)}


def make_tool() -> Tool:
    """Construct the control ``hello_tool``.

    The Tool's name MUST match the ``[[contributions.tools]]`` name
    in horus-plugin.toml — ``hello_tool``. ``PluginLoader`` enforces
    the match via ``_materialize_tool``.
    """
    return Tool(
        name="hello_tool",
        description="Echoes its keyword arguments back as a dict.",
        parameters={
            "type": "object",
            "properties": {
                "value": {"type": "string", "description": "Anything to echo."},
            },
            "required": [],
        },
        handler=_echo_handler,
    )
