"""Data types for the skills subsystem.

A skill is a named, reusable instruction unit stored as a Markdown file with
YAML-style frontmatter (FEATURES.md Feature 8). The frontmatter carries the
addressable metadata (name, description, tags, kind, allowed_tools) and the
Markdown body holds the instructions. Skills are a distinct capability layer
from notes and plugins (PITFALLS SK-2): the Skill dataclass deliberately does
not reuse AgentProfile, though it borrows the same None-means-unrestricted
sentinel for allowed_tools.

This module parses and represents skills; it never executes a skill body.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# The only two legal values for Skill.kind. A "prompt-template" skill is a pure
# instruction unit with no executable code and is the safe default (PITFALLS
# SK-1). A "code" skill bears code and must pass the plugin-level capability
# gate before any body is acted on; that enforcement lands in plan 74-03.
KIND_PROMPT_TEMPLATE = "prompt-template"
KIND_CODE = "code"


class SkillParseError(ValueError):
    """Raised when a skill file cannot be parsed into a Skill.

    Carries the offending rel_path so discovery and the CLI can name the file
    that failed instead of surfacing a bare KeyError or a raw parser exception.
    """

    def __init__(self, message: str, *, rel_path: str) -> None:
        self.rel_path = rel_path
        super().__init__(f"{rel_path}: {message}")


@dataclass
class Skill:
    """A discovered, named instruction unit.

    `allowed_tools` follows the AgentProfile sentinel: None means unrestricted,
    a list constrains which tools the skill may call (enforced in plan 74-03).
    `kind` is either "prompt-template" (the safe default) or "code".
    `rel_path` is the skills_dir-relative posix path the skill was loaded from.
    """

    name: str
    description: str
    body: str
    rel_path: str
    kind: str = KIND_PROMPT_TEMPLATE
    tags: list[str] = field(default_factory=list)
    allowed_tools: list[str] | None = None  # None means unrestricted
