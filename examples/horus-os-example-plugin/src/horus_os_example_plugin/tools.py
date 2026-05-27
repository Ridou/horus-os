"""Reference plugin tools: scenarios (a) + (b).

Scenario (a): ``echo_text_tool(ctx, path)`` requires
``Capability.FILESYSTEM_READ`` and returns the file's content via
``ctx.filesystem.read(path)``. With the capability denied, the
``CapabilityGuard`` wrap site raises ``PermissionDenied`` before the
handler body runs.

Scenario (b): ``lookup_secret_tool(ctx, key)`` requires
``Capability.SECRETS_READ`` and returns ``os.environ.get(key)`` via
``ctx.secrets.read(key)`` — None on a missing key, the string value
on a set key. Missing keys are a legitimate runtime state, not a
permission failure (matches ``DESCRIPTIONS[SECRETS_READ]`` semantics).

Both tools are discovered through the manifest's
``[[contributions.tools]]`` entries; the entry-point group is the
discovery seam, not import-time side effects.

Every name imported from horus-os comes from
``horus_os.plugins.api`` — the SINGLE public API surface. The Phase 48
TEST-21 two-layer guard (ruff banned-api + pytest source-tree scan)
rejects any other ``from horus_os`` line under this directory.
"""

from __future__ import annotations

from horus_os.plugins.api import Capability, PluginContext, Tool, require_capability


@require_capability(Capability.FILESYSTEM_READ)
def _echo_text_impl(ctx: PluginContext, path: str) -> str:
    """Read and return the text content at ``path``.

    Requires ``Capability.FILESYSTEM_READ``. Path-escape defense lives
    in the ``_FilesystemShim`` (Path.resolve before the cap check), so
    callers do not need to validate the input themselves.
    """
    return ctx.filesystem.read(path)


@require_capability(Capability.SECRETS_READ)
def _lookup_secret_impl(ctx: PluginContext, key: str) -> str | None:
    """Return the env var value for ``key``, or None when unset.

    Requires ``Capability.SECRETS_READ``. A missing env var is NOT a
    permission failure; the shim returns None. A missing capability,
    however, raises ``PermissionDenied`` at the wrap site.
    """
    return ctx.secrets.read(key)


def echo_text_tool() -> Tool:
    """Tool factory for scenario (a). The loader calls this with zero args."""
    return Tool(
        name="echo_text_tool",
        description="Read the text content at a given file path.",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Absolute or relative path to a text file.",
                },
            },
            "required": ["path"],
        },
        handler=_echo_text_impl,
    )


def lookup_secret_tool() -> Tool:
    """Tool factory for scenario (b). The loader calls this with zero args."""
    return Tool(
        name="lookup_secret_tool",
        description="Read an environment variable by name.",
        parameters={
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "description": "Environment variable name.",
                },
            },
            "required": ["key"],
        },
        handler=_lookup_secret_impl,
    )
