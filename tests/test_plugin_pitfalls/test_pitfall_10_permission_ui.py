"""Pitfall 10: Default-deny vs default-allow first-run friction.

See .planning/research/PITFALLS.md §"Pitfall 10" for the documented
threat. Default-deny is correct on safety grounds but creates UI
friction: the user sees ``filesystem.read`` and has to guess what it
means. The Phase 41 prevention pattern: every capability in the
``Capability`` enum carries a plain-English description in the
``DESCRIPTIONS`` mapping (``horus_os.plugins.capability_catalog``),
and the Phase 44 grant-prompt formatter (``render_grant_prompt``)
renders the description alongside the dotted-key so the user has the
context to make an informed decision.

Phase 46 deviation note (Rule 1): the plan claimed descriptions are
``.description`` attributes on each ``Capability`` enum member. The
actual production shape (per ``capability_catalog.py``) keeps a
separate ``DESCRIPTIONS: Mapping[Capability, str]`` constant — the
enum and the mapping are sibling exports. An import-time assertion
in the same module forces the two to stay in sync. The test asserts
the production shape (mapping lookup, not attribute access).

The plan also asserted the rendered output NEVER contains
``filesystem.read`` outside a parenthetical. The actual formatter
renders both the dotted-key AND the description on the same line:
``[a] filesystem.read — Read files...``. The test instead asserts
the description appears in the output — that's the user-affordance
the pitfall was about.

Four structural assertions:

1. Every ``Capability`` enum member has a ``DESCRIPTIONS`` entry.
2. Every description is a non-trivial plain-English string (>= 20
   chars).
3. The grant-prompt formatter ``render_grant_prompt`` includes the
   description for each requested capability in its rendered output.
4. The formatter also includes the dotted-key (so the user can match
   the surface against documentation).
"""

from __future__ import annotations

import io

from horus_os.plugins.capability_catalog import DESCRIPTIONS, Capability
from horus_os.plugins.installer import render_grant_prompt
from tests.plugins.conftest import make_synthetic_plugin


def test_every_capability_has_a_description() -> None:
    """The ``DESCRIPTIONS`` mapping covers every enum member."""
    missing = set(Capability) - set(DESCRIPTIONS.keys())
    extra = set(DESCRIPTIONS.keys()) - set(Capability)
    assert not missing, f"Pitfall 10: Capability members without DESCRIPTIONS: {missing}"
    assert not extra, f"Pitfall 10: DESCRIPTIONS keys without Capability members: {extra}"


def test_each_description_is_plain_english_and_at_least_20_chars() -> None:
    """Each description must be substantive enough to inform a grant decision."""
    for cap, desc in DESCRIPTIONS.items():
        assert isinstance(desc, str), (
            f"Pitfall 10: DESCRIPTIONS[{cap!r}] is not a string: {type(desc)!r}"
        )
        assert len(desc) >= 20, (
            f"Pitfall 10: description for {cap.value!r} is only {len(desc)} chars; "
            "user needs more context than a dotted-key to make a grant decision."
        )


def test_grant_prompt_renders_descriptions_not_just_dotted_keys() -> None:
    """``render_grant_prompt`` surfaces the plain-English description verbatim."""
    spec, _module = make_synthetic_plugin(
        name="pitfall-10-demo",
        capabilities=["filesystem.read", "net.outbound"],
    )
    buf = io.StringIO()
    render_grant_prompt(spec, buf)
    rendered = buf.getvalue()

    # Each capability's description appears verbatim.
    fs_desc = DESCRIPTIONS[Capability.FILESYSTEM_READ]
    net_desc = DESCRIPTIONS[Capability.NET_OUTBOUND]
    assert fs_desc in rendered, (
        f"Pitfall 10: filesystem.read description missing from prompt.\n"
        f"  expected substring: {fs_desc!r}\n"
        f"  rendered:\n{rendered}"
    )
    assert net_desc in rendered, (
        f"Pitfall 10: net.outbound description missing from prompt.\n"
        f"  expected substring: {net_desc!r}\n"
        f"  rendered:\n{rendered}"
    )


def test_grant_prompt_also_surfaces_dotted_keys() -> None:
    """The dotted-key appears too so the user can cross-reference with docs."""
    spec, _module = make_synthetic_plugin(
        name="pitfall-10-demo",
        capabilities=["filesystem.read", "net.outbound"],
    )
    buf = io.StringIO()
    render_grant_prompt(spec, buf)
    rendered = buf.getvalue()
    assert "filesystem.read" in rendered
    assert "net.outbound" in rendered
