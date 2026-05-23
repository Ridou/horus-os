"""Built-in tools shipped with horus-os.

For v0.1 there is exactly one: `read_file`. More built-ins land in later
phases when the dashboard, CLI, and integration adapters need them.
"""

from __future__ import annotations

from pathlib import Path

from horus_os.types import Tool

_READ_FILE_PARAMETERS: dict = {
    "type": "object",
    "properties": {
        "path": {
            "type": "string",
            "description": "Path to the file. Relative paths resolve relative to base_dir if the tool was constructed with one, otherwise relative to the current working directory.",
        },
    },
    "required": ["path"],
}


def read_file_tool(base_dir: str | Path | None = None) -> Tool:
    """Return a `Tool` that reads a local file.

    When `base_dir` is provided, all paths are resolved relative to it
    and any resolved path that escapes the directory raises
    PermissionError. When `base_dir` is None the tool has full
    filesystem read access under the user account running horus-os.
    """
    base_path = Path(base_dir).resolve() if base_dir is not None else None

    def handler(path: str) -> str:
        candidate = Path(path)
        if base_path is not None:
            if candidate.is_absolute():
                resolved = candidate.resolve()
            else:
                resolved = (base_path / candidate).resolve()
            if base_path != resolved and base_path not in resolved.parents:
                raise PermissionError(f"Path {path!r} resolves outside the configured base_dir")
        else:
            resolved = candidate.expanduser().resolve()
        return resolved.read_text()

    description = "Read the text content of a local file and return it as a string."
    if base_path is not None:
        description += f" Paths are resolved relative to {base_path} and may not escape it."
    return Tool(
        name="read_file",
        description=description,
        parameters=_READ_FILE_PARAMETERS,
        handler=handler,
    )
