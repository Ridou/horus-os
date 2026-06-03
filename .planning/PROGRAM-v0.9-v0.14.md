# Program Roadmap: v0.9 - v0.14

Long-range plan covering the six milestones that absorb the full v0.9 gap
analysis (`.planning/research/v0.9-gap-analysis.md`, themes A-K after the
completeness pass). This is a program-level map, not a committed milestone plan.
Each milestone is finalized through the normal GSD flow (`/gsd-new-milestone` ->
requirements -> roadmap -> phases); the phase lists below are indicative, to show
shape and sequencing.

Baseline at authoring (2026-06-03): v0.8.0 shipped, SQLite schema v13.

The gap analysis ran in two passes. Pass 1 produced themes A-G (memory,
self-improvement, orchestration, cost/safety, proactivity, dashboard, Odysseus).
A coverage-driven pass 2 added themes H-K (execution substrate and
extensibility, interop and platform surface, interaction modality, distribution
and onboarding) and certified the remaining private modules as purely personal.
The comb is considered exhaustive. Pass-2 items are folded into the milestones
below: the hook system moves into v0.9 as substrate, and two new milestones
(v0.13 Interop and Distribution, v0.14 Interaction Modality) carry the rest.

## Why a program, not one release

The gap analysis surfaced roughly five milestones of generic capability. The
themes are not independent: the safety and event substrate must land before
agents are turned loose, and the dashboard work model must exist before the rich
UI is built on it. So "do all of it" becomes a dependency-ordered sequence, not
a single tag.

Sequencing principle: **capability behind its guardrails**. v0.8 shipped raw
power (autonomous research, gated shell, metered-but-unbounded spend). v0.9
lands the rails (budgets, approvals, redaction, lanes) and the controlled
autonomy that rides on them. Later milestones add depth (memory/learning),
legibility (issue system), and breadth (workspace/models).

## Cross-cutting principles (apply to every milestone)

- Every new capability is **opt-in**. A bare `pip install horus-os` still starts
  with only an LLM key and activates none of it. Heavy or optional dependencies
  live behind their own extra, following the v0.8 pattern.
- **No personal data** in any committed text (CLAUDE.md rule 1). Generic platform
  only; nothing ported from the private sibling carries personal-life features.
- SQLite migrations are **additive and idempotent**, run on first start. Mind the
  schema-migration tripwire: bumping `SCHEMA_VERSION` touches every hardcoded
  version-expectation file (migration tests, install_smoke, test_storage). Each
  milestone that adds tables bumps the version once and updates all of them.
- **Three-OS hard gate** (macOS, Ubuntu, Windows x Python 3.11, 3.12) is the
  non-negotiable final phase of every milestone before a tag.
- No em-dashes in committed prose (including `.planning/*.md`; the CI guard scans
  changed planning files).

---

## v0.9 - Autonomy and Control

**Goal:** Make agents act on their own, safely. Land the event/safety substrate,
the cost and approval rails, and the controlled autonomy that rides on them, with
the minimum dashboard surface to supervise it.

**Themes:** C (orchestration/autonomy) + D (cost/safety) + E (proactivity/events)
+ a thin slice of F (approvals, inbox, run-liveness).

**Value narrative:** v0.8 gave agents the ability to spend money and run shell
with no spend cap and no human-in-the-loop gate. v0.9 closes that: budgets that
pause on breach, risk-tiered approvals, secrets redaction, and priority lanes so
background autonomy never starves user work. Only then do watches, heartbeat
loops, and spontaneous/overnight runs become safe to ship.

**New extras (candidate):** none strictly required; watches/trend-monitor may use
the existing `[web]` extra. Most of this is core-but-opt-in via config and env
flags, mirroring the scheduler pattern.

**Candidate phases:**
1. Substrate: inline lifecycle hook system (pre/post tool, pre/post task, allow/deny/warn) + event bus + priority execution lanes (`hooks/`, `event_bus`, `lanes`). The hook system is the seam the cost/approval/redaction features in later phases register onto rather than inlining. (Theme H, the pass-2 catch.)
2. Cost control: monetary budget enforcement + daily pre-flight ceiling + stale-run reaper (`budget_enforcer`, `cost_guard`, `process_reaper`), wired as hooks. Reads existing per-call cost rows.
3. Approval system: tiered smart approval + destructive-action gate + verification gate (`smart_approval`, `approval`, `verification`), one shared classifier, as deny-hooks.
4. Safety hardening: secrets-redaction filter + subprocess resource guard + skill threat scanner + task-spec completeness gate + loop detector + rate limiter (`secrets_filter`, `subprocess_mgr`, `skill_safety`, `contracts/task_spec`, `hooks/tool_hooks`).
5. Scheduler upgrades: natural-language scheduler + catch-up/missed-fire policy + per-agent heartbeat loop (`nl_scheduler`, `routine_scheduler`, `heartbeat_scheduler`).
6. Watch rules / triggers engine (`watches`) on the event bus, with daily caps and dedup.
7. Controlled autonomy: spontaneous/idle loop + overnight batch runner (`spontaneous`, `overnight`), behind every gate from phases 2-4 and the lanes from phase 1.
8. Supervision surface: approvals queue + unified inbox + run-liveness watchdog + activity feed (`inbox`, `activity_logger`, dashboard).
9. Three-OS gate + v0.9.0 release.

**Schema:** new tables likely include `budgets`, `budget_incidents`,
`approvals`, `watch_rules`, `alert_rules`, `inbox_items`, `activity_log`, plus
hook-registration metadata. Single additive version bump (v13 -> v14).

**Dependencies:** none external; lands first because it is the substrate.

---

## v0.10 - Memory and Learning

**Goal:** Turn the vault-plus-vector store into a real memory engine, and give
agents a learning loop so they measurably improve over time.

**Themes:** A (memory intelligence) + B (self-improvement).

**Value narrative:** This is the truest meaning of "a team of agents that gets
better." Structured facts with conflict resolution replace blind chunk storage;
auto-memorization makes capture ambient; consolidation and forgetting keep memory
from rotting; a mistakes-and-solutions loop feeds outcomes back into future runs.

**New extras (candidate):** reuses the existing `[local-memory]` embeddings +
vector stack; the cheap-model consolidation calls reuse existing providers. No
new heavy dependency expected.

**Candidate phases:**
1. Fact model: structured fact extraction + conflict resolution + version chains (`memory_engine`). Schema for facts + supersession.
2. Auto-memorization pipeline: fire-and-forget post-task extraction, two-gate consolidation, daily caps, secret masking (`auto_memorize`).
3. Recall intelligence: relevance-ranked recall + staleness caveats + working-memory tier + anti-accumulation injection (`memory_recall`, `working_memory`).
4. Maintenance: fragment consolidation sweep + light dream/sleep cycle + intelligent forgetting (`memory_consolidation`, `dream_consolidation`, `memory_engine.forget_*`).
5. Insight + health: correlation engine + vault-drift scanner + knowledge-debt metric (`correlation_engine`, `vault_drift`, `librarian`).
6. Continuity: cross-run session persistence + structural compaction + mistakes log + post-task learning loop + session-context handoff + long-session history compression (`session_manager`, `agent_learning`, `agent_identity`, `session_context`, `history_compress`). (Session persistence is a Theme-K pass-2 catch.)
7. Recall breadth: FTS5 full-text search over past task transcripts + summarize-for-injection (`routers/knowledge` pattern), complementing the vector index. (Theme I pass-2 catch.)
8. Solution memory + solution-to-skill promotion + skill curator lifecycle (`solution_memory`, `skills` curator fields).
9. Steering: `behavior_adjust` tool + safe append-only self-evolution + reverse prompting + proposal lifecycle (`behavior_adjust`, `agent_self_evolution`, `reverse_prompting`, `proposals`).
10. Memory-health dashboard surface + proposals review queue.
11. Three-OS gate + v0.10.0 release.

**Schema:** `memory_facts` (with version/supersession + `forget_after`),
`solutions`, curator columns on skills, `proposals`, rejection-memory store,
`agent_sessions`, an FTS5 transcript index. Additive bump (v14 -> v15).

**Dependencies:** independent of v0.9; the proposals queue reuses v0.9's
approvals/inbox surface if present, otherwise ships its own minimal view.

---

## v0.11 - Work Legibility

**Goal:** Make agent work legible. Upgrade the flat task list into a real issue
system with a detail surface, and give the command center the daily-driver UX it
lacks.

**Themes:** F (dashboard/work legibility), consuming the data v0.9/v0.10 produce.

**Value narrative:** The most demoable milestone. A rich task model (sub-tasks,
priority, labels, human-readable IDs) under a detail page with comments and a run
timeline, a kanban board, references and backlinks, and a command palette turn a
status list into a place you actually run operations from.

**New extras (candidate):** frontend-only (cmdk, dnd-kit); no Python extra.
Frontend phases run without git worktrees (node_modules cannot span worktrees).

**Candidate phases:**
1. Realtime substrate: WebSocket event push (`routers/websocket` pattern) so the dashboard receives live task/run/activity events instead of polling. (Theme I pass-2 catch; backs liveness, live-run, and badges.)
2. Rich task data model: `parent_id` sub-tasks, priority, labels, human-readable IDs, project links + migration + API.
3. Issue/task detail page: split layout, inline edit, comment + run-event timeline, per-task cost, sub-issues tab.
4. References + backlinks + hover preview (render-time ID pills, "referenced by" panel).
5. Kanban board with drag-to-change-status, optimistic updates, live working-pulse.
6. Goal hierarchy tree (nestable objective tree so work traces to "why").
7. Routines management page over a schedule-CRUD API + live run monitoring (active-run panel + transcript + stop) + context-window snapshot view (per-run token accounting) + workspace file browser (`routers/{schedules,context,files}` patterns).
8. Command palette (Cmd+K) + sidebar nav badges + richer trend charts.
9. Three-OS gate + v0.11.0 release.

**Schema:** task-model columns (`parent_id`, `priority`, `labels`,
`identifier`, `project_id`), `issue_references`, `goals`, `context_snapshots`.
Additive bump (v15 -> v16).

**Dependencies:** strongest after v0.9 (approvals/inbox/liveness data exist) and
v0.10 (so the detail timeline can surface memory facts and proposals).

---

## v0.12 - Workspace and Models

**Goal:** Turn the command center into a workspace and make local-model serving
guided rather than manual.

**Themes:** G (Odysseus-derived), plus optional breadth.

**Value narrative:** Hardware-aware model serving (scan, fit-score, one-click
launch) makes the local-first story turnkey. Blind model compare gives a built-in
eval surface. A document editor and a mobile PWA make the dashboard somewhere you
work, not just watch.

**New extras (candidate):** `[models]` (hardware scan + serving orchestration);
image generation, if pursued, behind its own extra. All opt-in, all excluded
from `[all]` if they carry heavy or platform-specific wheels (mirroring the
`[local-memory]` precedent).

**Candidate phases:**
1. Model cookbook backend: hardware scan + model catalog + VRAM fit-scoring.
2. Model serving: auto-download + quantization + one-click vLLM / llama.cpp / Ollama launch, wired to the existing local-LLM provider.
3. Blind model compare: fan-out one prompt to N providers, blind side-by-side view.
4. Self-authoring skills: agent writes/refines its own skills, behind the existing default-deny code-skill gate plus a review/sandbox path (the safety gate is the hard part).
5. In-app document editor (multi-tab markdown/CSV with inline AI edits).
6. Mobile-first PWA pass (manifest + responsive) over the existing dashboard.
7. Optional breadth: image generation/editing gallery; generic IMAP/SMTP + CalDAV adapters (kept generic, opt-in).
8. Three-OS gate + v0.12.0 release.

**Schema:** minimal; mostly config + cache tables. Additive bump if any.

**Dependencies:** independent of the others; pure additive breadth. Can reorder
earlier if local-model serving becomes a priority over legibility.

---

## v0.13 - Interop and Distribution

**Goal:** Make horus-os a good citizen of the wider agent ecosystem and make
agents shippable, importable, and operable by others.

**Themes:** H (execution substrate, remaining) + I (interop surface, remaining) +
K (distribution and onboarding). Pass-2 themes.

**Value narrative:** Today horus-os only consumes MCP and runs in isolation.
This milestone inverts that: it serves its own vault and tools over MCP, packages
agents as shareable bundles, imports templates, and gives self-hosters real
operability (deep health checks) and a guided first-run. It also lands the
pluggable executor layer (including a Python sandbox) and the typed inter-agent
contract that make multi-agent work robust.

**New extras (candidate):** `[mcp-server]` (FastMCP) for the server mode; the
rest is core-but-opt-in.

**Candidate phases:**
1. MCP server mode: expose vault/memory/tools as MCP tools + resources over stdio, path-gated, behind a `horus-os mcp-serve` entry (`mcp/vault_server` pattern).
2. Pluggable executor backends + Python code sandbox + callable-capability registry (`executors/`, `contracts/capabilities`).
3. Typed inter-agent communication contract + peer-capability discovery + dead-letter handling + handoff-edge visualization (`contracts/intents`, MILESTONES v8.9 A2A).
4. Agent bundle format (Claude-Skills-compatible) + install/publish CLI + PR-curated registry.
5. GitHub template import + project ZIP export (data portability).
6. Operability: deep subsystem health endpoint + agent-config versioning/rollback + runtime agent creation (`routers/system`, `agent_config`, `agent_factory`).
7. Guided onboarding / setup wizard: idempotent, resumable, env auto-detection, live per-service credential validation, first-run dashboard flow. (Aligned with the owner's easy-setup priority; could pull forward to an earlier milestone if desired.)
8. Three-OS gate + v0.13.0 release.

**Dependencies:** benefits from v0.9 (hooks/lanes) and v0.10 (sessions). MCP
server mode and the bundle format are independent and could pull forward.

---

## v0.14 - Interaction Modality

**Goal:** Add new ways to talk to the command center: real-time voice and video,
and multi-language output.

**Themes:** J (interaction modality). Pass-2 theme.

**Value narrative:** A headline differentiator. Speech-to-speech voice with
barge-in, webcam/screen-share input, and live transcription make agents
reachable by voice; an optional telephony bridge turns that into a phone channel;
multi-language output broadens reach. The backend already has Gemini, so the
Live integration is mostly client and transport work.

**New extras (candidate):** `[voice]` (audio/transport deps); `[telephony]` for
the phone-channel adapter, opt-in and excluded from `[all]`.

**Candidate phases:**
1. Gemini Live core: ephemeral-token endpoint + WebSocket transport + speech-to-speech with barge-in + live transcription saved to vault.
2. Multimodal Live input: webcam / screen-share frames + audio worklet capture/playback pipeline + a dashboard voice/video session surface with history.
3. Multi-language output + translation helper (provider-routed, graceful degradation) + the runtime em-dash/text normalizer as an output filter (`translate`, `text_normalize`).
4. Optional voice channel adapter: generic real-time telephony bridge (audio transcode + turn loop + barge-in + call lifecycle), as an opt-in adapter plugin.
5. Three-OS gate + v0.14.0 release.

**Dependencies:** the WebSocket substrate from v0.11 is reused here; otherwise
independent. Can run earlier if voice is a priority.

---

## What this program deliberately excludes

Carried over from the gap-analysis scope guards and prior anti-feature
decisions: multi-tenant / multi-company, full RBAC, hosted SaaS, mobile native
clients (PWA only), the private PR-review pipeline, and all personal-life
features (contacts, photos/face-recognition, health, travel/itinerary, yoga,
people graph). These remain out of scope for the open-source project.

## Open sequencing questions for milestone planning

- Whether the proposals/approvals/inbox surface lands minimally in v0.9 and is
  enriched in v0.11, or is built once in v0.11 (v0.9 would then ship a thinner
  CLI-first supervision path).
- Whether the dream/consolidation engine ships light in v0.10 and gains the full
  Hebbian/retrieval-reversal engine later, or ships full in v0.10.
- Whether v0.12 (models/workspace) should jump ahead of v0.11 (legibility) if
  guided local serving proves higher-demand than the issue system.
