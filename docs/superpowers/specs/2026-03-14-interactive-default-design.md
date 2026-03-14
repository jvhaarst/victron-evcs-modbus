# Interactive Default Mode Design

**Date:** 2026-03-14
**Status:** Approved
**Beads:** victron_evcs_modbus-my8

## Goal

Make the interactive TUI the default mode when no mode flag is given. Add an explicit `--read` flag for table output. Remove `--interactive` (superseded by the new default).

## Current State

- Default (no flag): reads registers, prints Rich table, exits
- `--changed`: reads registers, filters to changed values, prints table, exits
- `--write ADDRESS VALUE`: writes a single register, exits
- `--interactive`: reads registers, launches TUI pre-populated with live values, exits when TUI closes

`--changed`, `--write`, and `--interactive` are in a mutually-exclusive argparse group.

## Architecture

### Mode dispatch

Remove `--interactive` and `--changed` from the mutually-exclusive mode group. Add `--read`:

**New mode group:** `--read | --write`

**`--changed`** becomes a standalone filter flag. It is only meaningful in table mode; when used without `--read` (and without `--write`), it implicitly triggers read/table mode. When used with `--write`, `--changed` is silently ignored (write takes precedence; argparse no longer enforces exclusion here — this is intentional, documented, and the existing `--write` logic short-circuits before `--changed` is consulted).

**Mode dispatch logic in `main()`:**

```
if args.write              → write mode (unchanged; --changed silently ignored)
elif args.read or args.changed → read/table mode
else                       → interactive TUI  ← new default
```

### TUI path: pre-read behavior preserved

The new default TUI path behaves identically to the current `--interactive` path: it connects, reads all registers into a `values` dict, then launches `RegisterEditorApp(client, registers, values, unit_id=args.unit_id)`. The `RegisterEditorApp` import moves from the `if args.interactive:` conditional block to the new `else` (default) branch.

### Argument help text

- `--read`: `"Print register table and exit"`
- `--changed`: `"Show only registers that differ from factory default (implies --read; ignored with --write)"`

## Files Touched

| File | Change |
|------|--------|
| `cli.py` | Remove `--interactive`; move `--changed` out of mode group; add `--read` to mode group; update mode dispatch; move TUI import+launch to `else` branch |
| `tests/test_cli.py` | Add 5 new tests (see Testing section); no existing `--interactive` tests to remove |
| `README.md` | Update options table and examples |

## Testing

New tests to add:

- `test_default_mode_launches_tui` — no mode flag → `RegisterEditorApp.run()` called
- `test_read_flag_prints_table` — `--read` flag → table printed, `RegisterEditorApp` not called
- `test_read_and_changed_flags` — `--read --changed` together → `filter_changed` called, table printed
- `test_changed_flag_implies_read` — `--changed` alone (no `--read`) → table printed (not TUI)
- `test_changed_with_write_ignored` — `--changed --write 5016 10` → write succeeds, `filter_changed` not called

Existing test `test_changed_flag_calls_filter_changed` (line 245 of `tests/test_cli.py`) already covers `--changed` calling `filter_changed`. It should be verified to still pass after the argparse restructure; no logic change needed.

Existing `--write` tests: unaffected.

## Out of Scope

- `--changed` filter in TUI mode
