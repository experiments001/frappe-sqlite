# Frappe SQLite — Android

Quick-and-dirty Android port of the Frappe SQLite desktop app.

**Status**: Planning / Phase 0

**Architecture**: Tauri v2 Android shell + Chaquopy (embedded CPython 3.11) + Frappe WSGI on localhost.

## Structure

```
mobile/android/
├── runtime/runner/     Python server (migration, server, paths, main)
├── shell/              Tauri v2 Android shell (scaffolded in Phase 1)
├── scripts/            Build and environment scripts
└── README.md           This file
```

## Docs

All plans and phase tracking live in `docs/mobile/android/`:

- `AGENT_LOOP.md`   — start here for every agent run
- `PHASE_TRACKER.md` — current phase and task status
- `MASTER_PLAN.md`   — full phase-by-phase plan

## Quick Start (Phase 0)

```bash
./mobile/android/scripts/setup-env.sh
./mobile/android/scripts/setup-emulator.sh
```

Then follow `docs/mobile/android/MASTER_PLAN.md` Phase 1.
