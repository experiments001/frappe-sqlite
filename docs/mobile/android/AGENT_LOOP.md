# Android Agent Loop

This file is the **entry point** for every agent run on the Android work.
Read this first. Always. Then read `PHASE_TRACKER.md`. Then act.

---

## The Loop

```
START
  │
  ▼
1. READ  → AGENT_LOOP.md (this file)
  │       → PHASE_TRACKER.md  (current phase + status)
  │       → MASTER_PLAN.md    (full phase specs)
  │
  ▼
2. ORIENT
  │  What phase are we in?
  │  What was the last thing done? (read last commit message)
  │  Are we blocked? (check BLOCKERS.md if it exists)
  │
  ▼
3. EXECUTE  → Work through the tasks for the current phase
  │           (each phase has explicit tasks in MASTER_PLAN.md)
  │           One phase at a time. Do not skip ahead.
  │
  ▼
4. VALIDATE → Run the validation checklist for the current phase
  │           (defined in MASTER_PLAN.md under each phase)
  │
  ▼
5. RECORD   → Update PHASE_TRACKER.md (mark tasks done, note failures)
  │           → Commit: "android: phase-N – <what was done>"
  │
  ▼
6. DECIDE
  │  All validations pass? → Advance PHASE_TRACKER.md to next phase → LOOP
  │  Some failures?        → Write to BLOCKERS.md → STOP (human checkpoint)
  │  Blocked by hardware?  → Note in BLOCKERS.md → STOP
  │
  ▼
END (or loop back to START for next phase)
```

---

## Rules

- **Never skip phase validation.** A phase is done only when its checklist passes.
- **Commit after each phase.** Message format: `android: phase-N – <summary>`
- **If something is unclear**, write the question to `BLOCKERS.md` and stop.
- **Space issues**: if disk is tight, run `./mobile/android/scripts/clean-cache.sh` before building.
- **Emulator**: the smallest viable emulator is `Pixel_3a` API 33 (arm64). Install via `scripts/setup-emulator.sh`.
- **Branch**: `feature/mobile-android-first-run` — all work stays on this branch.
- **PR target**: `main` (same pattern as the desktop PR #7).

---

## Quick Orient Commands

```bash
# Where are we?
cat docs/mobile/android/PHASE_TRACKER.md

# Last 5 commits
git log --oneline -5

# Is the emulator running?
adb devices

# Is the sidecar Python env ok?
python3 -c "import frappe; print('ok')" 2>&1 | head -3

# Is Tauri Android scaffolded?
ls mobile/android/shell/src-tauri/gen/android/ 2>/dev/null && echo "yes" || echo "not yet"
```

---

## Phase Summary (quick reference)

| Phase | Name                      | Goal                                          |
|-------|---------------------------|-----------------------------------------------|
| 0     | Environment               | Android SDK/NDK + emulator installed & working |
| 1     | Tauri Android scaffold    | `tauri android dev` compiles and launches shell |
| 2     | Python runtime (Chaquopy) | Python 3.11 + Frappe deps in APK               |
| 3     | In-process server         | Frappe serves /login at 127.0.0.1:8765         |
| 4     | Runtime paths             | Paths adapted for Android data dirs            |
| 5     | First-run setup screen    | Config saved, server starts on first launch    |
| 6     | Smoke test + PR           | Full end-to-end verified, PR opened            |

Full details for each phase: see **MASTER_PLAN.md**.
