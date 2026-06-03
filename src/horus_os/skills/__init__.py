"""Skills subsystem: discoverable, reusable instruction units.

A skill is a Markdown file with YAML-style frontmatter under the configured
skills_dir. SkillStore discovers and parses them; the directory is the source
of truth (FEATURES.md Feature 8). This package is a distinct capability layer
from notes and plugins (PITFALLS SK-2) and imports neither.
"""

from __future__ import annotations

from horus_os.skills.executor import SkillAuthorizationError, SkillExecutor
from horus_os.skills.store import SkillStore, parse_skill_markdown
from horus_os.skills.tools import register_use_skill, use_skill_tool
from horus_os.skills.types import Skill, SkillParseError

__all__ = [
    "Skill",
    "SkillAuthorizationError",
    "SkillExecutor",
    "SkillParseError",
    "SkillStore",
    "parse_skill_markdown",
    "register_use_skill",
    "use_skill_tool",
]
