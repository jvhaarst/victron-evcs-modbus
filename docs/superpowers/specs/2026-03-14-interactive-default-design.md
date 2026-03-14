# Interactive Default Mode Design

**Date:** 2026-03-14
**Status:** Approved
**Beads:** victron_evcs_modbus-my8

## Goal

Make the interactive TUI the default mode when no mode flag is given. Add an explicit `--read` flag to trigger the table-output mode that is currently the default.

## Current State

- Default (no flag): reads registers, prints Rich table, exits
- `--changed`: reads registers, filters to changed values, prints table, exits
- `--write ADDRESS VALUE`: writes a single register, exits
- `--interactive`: launches TUI editor

`--changed`, `--write`, and `--interactive` are in a mutually-exclusive argparse group.

## Architecture

### Mode dispatch

Remove `--changed` from the mutually-exclusive mode group. Add `--read` to the mode group:

**New mode group:** `--read | --write | --interactive`

**`--changed`** becomes a standalone filter flag (not in the mode group). It is only meaningful in read/table mode; when used without `--read`, it implicitly triggers read mode.

**`--changed` + `--interactive` together is invalid.** The CLI exits 1 with:
`"error: --changed cannot be used with --interactive"`. This matches the spirit of the existing mutex group.

**Mode dispatch logic in `main()`:**

```
if args.write        → write mode (unchanged)
elif args.changed and args.interactive → error, exit 1
elif args.read or args.changed → read/table mode
elif args.interactive or (no mode flag) → interactive TUI
```

### `--interactive` retained

`--interactive` is kept as an explicit flag for backward compatibility (scripts or aliases that already use it). It behaves identically to the new default.

### Argument help text updates

- `--read`: `"Print register table and exit"`
- `--interactive`: `"Launch interactive TUI editor (default when no mode flag is given)"` — intentional help text change
- `--changed`: `"With --read: show only registers that differ from factory default"`

## Files Touched

| File | Change |
|------|--------|
| `cli.py` | Move `--changed` out of mode group; add `--read` to mode group; update mode dispatch; update help strings |
| `tests/test_cli.py` | Update default-mode tests to expect TUI launch; add `--read` tests |
| `README.md` | Update options table and examples |

## Testing

- `test_default_mode_launches_tui` — `sys.argv = ["cli.py", "host"]`, no mode flag → `RegisterEditorApp.run()` called
- `test_read_flag_prints_table` — `--read` flag → table printed, `RegisterEditorApp` not called
- `test_changed_flag_implies_read` — `--changed` alone → table printed (not TUI)
- `test_interactive_flag_explicit` — `--interactive` flag → TUI launched (backward compat)
- `test_changed_and_interactive_errors` — `--changed --interactive` → `SystemExit(1)`, error message contains "cannot be used"
- Existing `--write` tests: unaffected

## Out of Scope

- `--changed` filter in TUI mode
- Removing `--interactive` flag
