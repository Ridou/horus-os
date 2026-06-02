"""SkillStore: filesystem-backed discovery of skill files.

The directory under `skills_dir` is the SOURCE OF TRUTH (FEATURES.md Feature
8): each `*.md` file with a leading YAML-style frontmatter fence is one skill.
There is no separate database for the MVP, the same philosophy as the notes
folder, but SkillStore is kept completely independent of NotesStore, Database,
and the plugin system (PITFALLS Anti-Pattern 5, SK-2). This module imports no
YAML loader: the frontmatter is parsed by a small hand-rolled restricted
key:value reader so a crafted skill file cannot construct arbitrary objects
(threat T-74-01) and so the install grows no new heavy dependency.

Path safety mirrors NotesStore: every read resolves against the configured
root and refuses any path that escapes it (threat T-74-02). Discovery is
crash-safe: a file that fails to parse is skipped and recorded on a side
channel rather than raising, mirroring the plugin DiscoveryError pattern
(threat T-74-03).
"""

from __future__ import annotations

from pathlib import Path

from horus_os.skills.types import KIND_CODE, KIND_PROMPT_TEMPLATE, Skill, SkillParseError

# A skill is delimited by a leading frontmatter fence of exactly three dashes
# on its own line, an idiom borrowed from the wider Markdown frontmatter
# convention. The opening fence must be the very first line of the file.
_FENCE = "---"

# Frontmatter keys that parse as list values. Everything else is a scalar
# string. A list value may be a YAML-style inline "[a, b]" or a comma-separated
# string; both normalize to a list[str].
_LIST_KEYS = frozenset({"tags", "allowed_tools"})


def _split_list(raw: str) -> list[str]:
    """Parse a frontmatter list value into a list of trimmed strings.

    Accepts either an inline "[a, b, c]" form or a bare "a, b, c" string. Empty
    items are dropped so a trailing comma never yields a blank entry.
    """
    text = raw.strip()
    if text.startswith("[") and text.endswith("]"):
        text = text[1:-1]
    items = [item.strip().strip("'\"") for item in text.split(",")]
    return [item for item in items if item]


def _parse_frontmatter(block: str, *, rel_path: str) -> dict[str, str | list[str]]:
    """Parse the text between the frontmatter fences as a restricted mapping.

    Each non-blank line must be a ``key: value`` pair. Anything else (a bare
    line, a nested structure, a list item dash) is rejected with SkillParseError
    so only a simple mapping is ever accepted.
    """
    mapping: dict[str, str | list[str]] = {}
    for line in block.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" not in stripped:
            raise SkillParseError(
                f"frontmatter line is not a key: value pair: {stripped!r}",
                rel_path=rel_path,
            )
        key, _, value = stripped.partition(":")
        key = key.strip()
        value = value.strip().strip("'\"") if key not in _LIST_KEYS else value.strip()
        if not key:
            raise SkillParseError("frontmatter has an empty key", rel_path=rel_path)
        if key in _LIST_KEYS:
            mapping[key] = _split_list(value)
        else:
            mapping[key] = value
    return mapping


def parse_skill_markdown(text: str, *, rel_path: str) -> Skill:
    """Parse skill Markdown text into a Skill.

    The text must open with a ``---`` fence on its first line, contain a closing
    ``---`` fence, carry a restricted ``key: value`` frontmatter mapping with at
    least a ``name``, and have the body as everything after the closing fence.
    Any structural failure raises SkillParseError carrying rel_path, never a raw
    parser exception or a bare KeyError.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != _FENCE:
        raise SkillParseError(
            "missing leading '---' frontmatter fence",
            rel_path=rel_path,
        )
    closing_index: int | None = None
    for index in range(1, len(lines)):
        if lines[index].strip() == _FENCE:
            closing_index = index
            break
    if closing_index is None:
        raise SkillParseError(
            "unterminated frontmatter block (no closing '---')",
            rel_path=rel_path,
        )

    frontmatter_block = "\n".join(lines[1:closing_index])
    body = "\n".join(lines[closing_index + 1 :]).strip("\n")
    mapping = _parse_frontmatter(frontmatter_block, rel_path=rel_path)

    name = mapping.get("name")
    if not name or not isinstance(name, str):
        raise SkillParseError("frontmatter is missing a 'name'", rel_path=rel_path)

    description = mapping.get("description", "")
    if not isinstance(description, str):
        description = ""

    raw_kind = mapping.get("kind", "")
    kind = KIND_CODE if raw_kind in ("code", "code-bearing") else KIND_PROMPT_TEMPLATE

    tags = mapping.get("tags", [])
    if not isinstance(tags, list):
        tags = []

    allowed = mapping.get("allowed_tools")
    allowed_tools = allowed if isinstance(allowed, list) else None

    return Skill(
        name=name,
        description=description,
        body=body,
        rel_path=rel_path,
        kind=kind,
        tags=list(tags),
        allowed_tools=allowed_tools,
    )


class SkillStore:
    """Read view over a directory of skill Markdown files.

    The directory is the source of truth. Discovery is crash-safe: list_skills
    returns one Skill per parseable file and pushes parse failures onto
    list_skill_errors instead of raising. Path safety mirrors NotesStore.
    """

    def __init__(self, skills_dir: str | Path) -> None:
        self.skills_dir = Path(skills_dir)

    def _resolved_root(self) -> Path:
        return self.skills_dir.resolve()

    def _resolve(self, rel_path: str, *, must_be_under_root: bool = True) -> Path:
        root = self._resolved_root()
        candidate = Path(rel_path)
        if candidate.is_absolute():
            resolved = candidate.resolve()
        else:
            resolved = (root / candidate).resolve()
        if must_be_under_root and root != resolved and root not in resolved.parents:
            raise PermissionError(f"Path {rel_path!r} resolves outside the skills directory")
        return resolved

    def list_skills(self) -> list[Skill]:
        """Return every parseable skill under skills_dir, sorted by name.

        A file that fails to parse is skipped, not raised; the failure is
        recorded for list_skill_errors. An absent skills_dir yields [].
        """
        skills, _ = self._discover()
        return skills

    def list_skill_errors(self) -> list[tuple[str, str]]:
        """Return (rel_path, error message) for each skill file that failed to parse."""
        _, errors = self._discover()
        return errors

    def _discover(self) -> tuple[list[Skill], list[tuple[str, str]]]:
        root = self._resolved_root()
        if not root.exists():
            return [], []
        skills: list[Skill] = []
        errors: list[tuple[str, str]] = []
        for path in sorted(root.rglob("*.md")):
            if not path.is_file():
                continue
            # Use the literal directory-entry path relative to root, NOT
            # path.resolve(): a symlink that points outside the root must keep
            # its in-root rel_path so _resolve can flag the escape, rather than
            # raising a bare ValueError out of relative_to.
            rel = path.relative_to(root).as_posix()
            try:
                resolved = self._resolve(rel)
                text = resolved.read_text(errors="replace")
                skills.append(parse_skill_markdown(text, rel_path=rel))
            except SkillParseError as exc:
                errors.append((rel, str(exc)))
            except PermissionError as exc:
                errors.append((rel, str(exc)))
        skills.sort(key=lambda skill: skill.name)
        return skills, errors

    def get_skill(self, name: str) -> Skill | None:
        """Return the skill whose frontmatter name matches `name`, or None.

        Matching is by frontmatter name, not filename, so use_skill addresses a
        skill by the name the author declared.
        """
        for skill in self.list_skills():
            if skill.name == name:
                return skill
        return None

    def list_skill_summaries(self) -> list[dict[str, str]]:
        """Return only {"name", "description"} per skill, never the body.

        This is the level-1 progressive-disclosure surface (FEATURES.md): the
        skills menu loaded into a system prompt is name + description only; the
        full body is fetched on demand in plan 74-03.
        """
        return [
            {"name": skill.name, "description": skill.description} for skill in self.list_skills()
        ]
