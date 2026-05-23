# Phase 17 Context: Adapter plugin interface

**Date:** 2026-05-23
**Phase:** 17
**Status:** Context captured (headless auto-mode)

## Domain

Phase 17 ships the third-party extension surface for horus-os. The
core runtime, CLI, and dashboard are stable after Phases 12-16. Now
external packages need a stable contract for shipping their own
inbound channels (webhooks, message queues, schedulers, anything that
calls into `run_agent` on horus-os's behalf) without forking the repo.

Two layers ship:

1. The contract: a `Protocol` describing what a horus-os adapter is,
   and a discovery helper that walks `importlib.metadata.entry_points`
   to load any package declaring `[project.entry-points."horus_os.adapters"]`.
2. The reference adapter: an HTTP webhook receiver that validates an
   HMAC signature, parses a JSON payload, runs `run_agent` against a
   configured agent profile, and returns the trace id plus the final
   text.

Phase 12 gave us `AgentProfile`. Phase 13 gave us `run_agent`
delegation primitives. Phase 16 gave us a FastAPI factory with
`create_app(data_dir)`. Phase 17 is composition: define the boundary,
ship one in-tree adapter, and prove a third-party package can plug in.

## Canonical refs

- `.planning/ROADMAP.md` Phase 17 success criteria
- `.planning/REQUIREMENTS.md` ADAPT-01, ADAPT-02, ADAPT-03
- `src/horus_os/server/api.py` FastAPI app factory (Phase 16)
- `src/horus_os/agent.py` `run_agent` (Phase 2, used by adapters)
- `src/horus_os/tools/registry.py` shape inspiration for the
  adapter contract (small Protocol, register-once, lookup-by-name)
- `pyproject.toml` `[project.entry-points]` is where the reference
  adapter is declared so the package self-publishes its hook

## Decisions

### 1. Contract is a `Protocol`, not an ABC

`Adapter` is a runtime-checkable Protocol with three members: a `name`
attribute, a `bind(app)` method that mounts routes onto the FastAPI
instance, and an optional `describe()` method that returns a static
metadata dict for diagnostics. Protocol over ABC keeps third-party
adapters free of an inheritance dependency on horus-os; any duck-typed
class with the right shape satisfies the contract.

### 2. Adapters package layout

New `src/horus_os/adapters/` package with:

- `__init__.py` re-exports `Adapter`, `discover_adapters`, and
  the in-tree `WebhookAdapter`.
- `base.py` holds the `Adapter` Protocol, the `AdapterContext`
  dataclass (config plus data_dir handed to adapters at bind time),
  and `discover_adapters()` which calls
  `entry_points(group="horus_os.adapters")` and resolves each one.
- `webhook.py` is the reference HTTP webhook adapter.

The package re-exports a minimal public surface so third-party adapter
authors only need to `from horus_os.adapters import Adapter,
AdapterContext`.

### 3. Discovery happens on FastAPI app startup, once

`create_app(data_dir)` calls `discover_adapters()` after the core
routes are registered. Each discovered adapter is instantiated with
no arguments (a `Callable[[], Adapter]` factory pattern via the
entry-point target) and `bind(app, ctx)` is called. The context
carries the `Config`, the `data_dir` Path, and a `Database` factory
so the adapter does not need to import horus-os internals beyond the
adapter package.

Failures during discovery do not abort `create_app`. A bad adapter
logs a warning and is skipped; the core dashboard stays up. This
matches the dashboard's "core works without optional features"
philosophy.

### 4. Reference webhook adapter shape

The webhook adapter mounts `POST /api/adapters/webhook` (the path
prefix `/api/adapters/{name}` is the convention; each adapter owns
its sub-tree). The handler:

1. Reads the raw body and the `X-Horus-Signature` header.
2. Computes `hmac.new(secret, body, hashlib.sha256).hexdigest()` and
   compares with `hmac.compare_digest`. Mismatch or missing header
   returns 401.
3. Parses JSON; expects `{ "prompt": str, "agent": str? }`. A missing
   prompt returns 400.
4. Loads the agent profile if specified (404 on unknown).
5. Runs `run_agent` with the profile's system prompt, default model,
   and the requesting provider (defaults to the config default).
6. Records a trace row tagged with the agent profile name.
7. Returns `{"trace_id": ..., "text": ..., "latency_ms": ...}`.

The secret comes from `HORUS_OS_WEBHOOK_SECRET` (env var). When the
secret is unset, the webhook returns 503 with a clear message: the
adapter refuses to operate without a configured shared secret. This
is the "safe by default" stance: no open webhook ships.

### 5. Entry-point declaration in pyproject

```
[project.entry-points."horus_os.adapters"]
webhook = "horus_os.adapters.webhook:WebhookAdapter"
```

The value resolves to the `WebhookAdapter` class (callable with no
args; instances satisfy the Protocol). Third-party packages declare
the same key with their own dotted path.

### 6. Testing third-party discovery without installing a package

Tests stub `discover_adapters` by monkeypatching
`horus_os.adapters.base.entry_points` (a module-level alias for
`importlib.metadata.entry_points`). The stub returns a list of
synthetic `EntryPoint` objects whose `.load()` returns an in-memory
fake adapter class. This is the textbook approach for entry-point
testing and does not require a separate package install fixture.

### 7. HMAC algorithm: SHA-256 hex digest

We pick SHA-256 because every standard webhook ecosystem (GitHub,
Stripe, Slack) uses it. The header is `X-Horus-Signature: sha256=<hex>`.
Comparison uses `hmac.compare_digest` to avoid timing oracles.
Replay protection is out of scope for the reference adapter; a
production deployment can layer a timestamp + nonce check on top.

### 8. Backwards compatibility

Adapters are purely additive. `create_app(data_dir)` continues to
work for callers who never set up an entry point. The dashboard, CLI,
and all existing tests behave byte-identically. v0.1 traces still
serialize cleanly through the new webhook trace path because
`record_trace` already accepts `agent_profile_name=None`.

### 9. Test surface

Three new test files:

- `tests/test_adapters_discovery.py`: stubs `entry_points` and asserts
  `discover_adapters()` returns the right names, in deterministic
  insertion order, and that a load failure on one entry point does
  not break the others.
- `tests/test_adapters_webhook.py`: end-to-end through FastAPI
  TestClient. Good HMAC, missing HMAC, bad HMAC, missing secret env,
  unknown agent, run_agent monkeypatched to a fake that records
  inputs and returns a canned `AgentResult`.
- `tests/test_adapters_integration.py`: stubs `entry_points` to
  return a third-party fake adapter, calls `create_app`, asserts
  the fake adapter's route is mounted and callable. This proves the
  "third-party install without modifying horus-os" requirement.

## Execution split

- **Plan 01:** Adapter contract, discovery helper, FastAPI wiring,
  and the third-party integration test. No reference adapter yet;
  the contract and discovery land as an atomic unit so any adapter
  package can build against it.
- **Plan 02:** Reference HTTP webhook adapter, full HMAC validation,
  agent profile routing, end-to-end tests, and the `pyproject.toml`
  entry-point declaration.

Atomic commits: docs(17) for plan+context, feat(17) for contract +
discovery + FastAPI wiring, feat(17) for the webhook adapter, docs(17)
for the summaries.

## Deferred / not in scope

- Adapter hot-reload at runtime (discovery is a one-time startup walk).
- Replay protection (timestamp + nonce header check) on the webhook;
  the reference adapter ships with HMAC signature validation only.
- Outbound adapters (push-style integrations that horus-os calls
  into). The contract is intentionally narrow to inbound surfaces.
- A `horus-os adapters` CLI command. Diagnostics live behind a future
  `/api/adapters` GET route if there is demand; v0.2 keeps the
  introspection surface trim.
- Per-adapter rate limits or auth scopes; local-only server in v0.2.
