"""Closed catalog of capabilities a plugin can request.

A ``StrEnum`` keeps the catalog closed: any value not in this enum
fails ``MANIFEST_V1_SCHEMA`` validation at manifest-load time. The
``DESCRIPTIONS`` mapping carries one plain-English sentence per
capability that the installer (Phase 44) renders verbatim at the
install-time grant prompt.

Adding a new capability requires three changes in one commit:
  1. Add the enum member here.
  2. Add a ``DESCRIPTIONS`` entry; the module-level ``assert`` below
     refuses to import if either side drifts.
  3. Add the wiring (Phase 43 ``CapabilityGuard`` + ``PermissionGate``)
     that actually enforces the new capability.

Pitfall 1 (closed enum) ban on string-typed catalogs is enforced by
this module's ``StrEnum`` shape; ``MANIFEST_V1_SCHEMA`` uses
``Capability`` as the canonical lookup at validation time.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum


class Capability(StrEnum):
    """Closed enum of capability strings horus-os recognizes in v0.5.

    Each member's value is the string a plugin author writes in the
    ``[capabilities]`` array of ``horus-plugin.toml``. The names are
    stable across versions; new capabilities land as additional
    members but never rename existing ones.
    """

    FILESYSTEM_READ = "filesystem.read"
    FILESYSTEM_WRITE = "filesystem.write"
    NET_OUTBOUND = "net.outbound"
    SECRETS_READ = "secrets.read"
    # Phase 74 (SKILL-03, SK-1): the grant a code-bearing skill needs before
    # its embedded steps run. Prompt-template skills never need it; only a
    # skill declared kind=code is gated on this capability, default-deny.
    SKILL_EXEC = "skill.exec"
    # Phase 75 (SHELL-01, SE-1): the grant an agent needs before the shell_exec
    # tool registers for it. This is the second half of the double gate; the
    # first half is the shell_enabled config flag plus the HORUS_OS_SHELL_ENABLED
    # env var. Default-deny: without this grant the tool never reaches the agent.
    SHELL_EXEC = "shell.exec"
    # Phase 75 (SHELL-03): the grant a code snippet needs to run through the same
    # gated subprocess path as shell_exec. Code execution reuses the shell
    # substrate (structured args, working-directory boundary, timeout, audit row).
    CODE_EXEC = "code.exec"


DESCRIPTIONS: Mapping[Capability, str] = {
    Capability.FILESYSTEM_READ: (
        "Read files from disk paths the plugin declares. Does NOT include "
        "writing, deleting, or modifying files."
    ),
    Capability.FILESYSTEM_WRITE: (
        "Create, modify, and delete files at disk paths the plugin declares. "
        "Implies read access to the same paths."
    ),
    Capability.NET_OUTBOUND: (
        "Open outbound network connections to hosts the plugin declares. "
        "Does NOT permit inbound listeners or connections to third-party "
        "hosts the manifest did not list."
    ),
    Capability.SECRETS_READ: (
        "Read secret values (API keys, tokens) the plugin declares by key "
        "name. Does NOT permit listing all secrets or writing new ones."
    ),
    Capability.SKILL_EXEC: (
        "Run the embedded steps of a code-bearing skill. Prompt-template "
        "skills never need this; only a skill marked kind=code is gated on it."
    ),
    Capability.SHELL_EXEC: (
        "Run shell commands as a structured argument list inside the "
        "configured safe working directory. Commands may not use shell "
        "metacharacters and may not escape the working directory."
    ),
    Capability.CODE_EXEC: (
        "Run code snippets through the same gated subprocess path as shell "
        "commands, inside the configured safe working directory with the same "
        "metacharacter and working-directory boundary checks."
    ),
}


# Import-time guard: if a contributor adds a Capability member without
# also adding a DESCRIPTIONS entry (or vice versa), this assertion
# refuses the import. It is a deliberate failure-mode: the installer's
# grant prompt depends on a description being present for every
# capability the user can be asked to authorize.
assert set(DESCRIPTIONS.keys()) == set(Capability), (
    "Every Capability member must have a DESCRIPTIONS entry "
    f"(missing: {set(Capability) - set(DESCRIPTIONS.keys())}; "
    f"extra: {set(DESCRIPTIONS.keys()) - set(Capability)})"
)


__all__ = ["DESCRIPTIONS", "Capability"]
