---
phase: 08-web-chat-and-dashboard
plan: "00"
subsystem: server-api
tags: [fastapi, server, json-api, chat-endpoint, traces-endpoint]

# Dependency graph
requires:
  - phase: "03-persistence-layer"
  - phase: "06-memory-layer-write-path"
  - phase: "07-01"
provides:
  - "horus_os.server.create_app FastAPI factory"
  - "GET /api/health, /api/traces, /api/traces/{id}, /api/writes"
  - "POST /api/chat with run_agent_loop + trace recording + audit-trail wiring"
  - "[dashboard] optional extra"
affects:
  - "08-01 mounts static files in the same app and upgrades horus-os serve"

# Tech tracking
tech-stack:
  added:
    - "fastapi>=0.110 (optional via [dashboard] extra)"
    - "uvicorn[standard]>=0.30 (optional via [dashboard] extra)"
    - "httpx>=0.27 (dev dep for FastAPI TestClient)"
  patterns:
    - "App factory create_app(data_dir) so tests can spin up fresh isolated instances and production code can pass an explicit data dir."
    - "FastAPI is a lazy import inside create_app. The top-level package imports cleanly without it."
    - "Body(...) annotation for the chat endpoint so FastAPI treats the dict as a request body, not a query string."
    - "Module-reference monkeypatching: tests stub `horus_os.server.api.run_agent_loop` rather than the agent module directly."

key-files:
  created:
    - "src/horus_os/server/__init__.py, 4 lines, re-exports create_app"
    - "src/horus_os/server/api.py, 198 lines, full FastAPI factory + handlers"
    - "tests/test_server_api.py, 193 lines, 15 endpoint tests"
  modified:
    - "pyproject.toml, [dashboard] extra + dev deps for FastAPI / httpx"
    - "src/horus_os/__init__.py, lazy create_app re-export"

requirements-completed:
  - DASH-01 (partial)
  - DASH-02 (partial)
  - DASH-03 (partial)

# Metrics
duration: 38m
completed: 2026-05-23
test-count: 15 (163 cumulative)
