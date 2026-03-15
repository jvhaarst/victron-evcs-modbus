# Moderate Refactor: Extract by Concern

**Date:** 2026-03-15
**Status:** Approved
**Scope:** Code quality / maintainability — no functional changes

---

## Problem

`cli.py` (499 lines) mixes four concerns: argument parsing, Modbus I/O, register data logic, and display formatting. `tui.py` imports business logic from `cli.py`, creating an awkward dependency. Address-range parsing is duplicated between `--address` and `--scan`. A linear scan in `read_registers` is O(n) per address. `Register.range` shadows the Python builtin.

## Solution

Extract `cli.py` into three focused modules. No functional changes — same CLI interface, same test coverage.

## Module Structure (after)

### `modbus.py` (new)

All Modbus I/O operations, extracted from `cli.py`:

- `read_registers(client, registers, unit_id)` — batch-read scalars + individual string reads. Fix: replace the `next(r for r in scalar_regs if r.address == addr)` linear scan with a pre-built `{address: reg}` dict.
- `write_register(client, reg, value, unit_id, verify)` — FC6/FC16 write with optional read-back verification.
- `scan_registers(client, start, end, unit_id)` — raw uint16 scan over arbitrary address range.

Imports: `pymodbus`, `struct`, and types from `registers` (`Register`, `StringRegister`). No display or CLI dependencies.

### `registers.py` (enriched)

Existing: `Register`, `StringRegister`, `REGISTERS`, `STRING_REGISTERS`, `ALL_REGISTERS`.

Added (moved from `cli.py`):

- `format_value(raw, scale)` — convert raw register int to display string.
- `validate_write_value(reg, input_str)` — parse and validate user input against register type/range/scale.
- `filter_changed(registers, values)` — return registers differing from factory default.
- `parse_address_range(range_str)` — new helper extracting the duplicated `"START-END"` parsing logic from `--address` and `--scan` handlers.

**Not moved:** `filter_registers` stays in `cli.py` because it imports `CATEGORIES` from `categories.py`. Moving it to `registers.py` would create a `registers -> categories` dependency that risks a future circular import. It belongs at the orchestration layer.

Also: rename `Register.range` to `Register.value_range` (removes `# noqa: A003`).

### `cli.py` (slimmed, ~250 lines)

Entry point and orchestration:

- `argparse` setup and argument parsing.
- `filter_registers()` — stays here because it depends on `CATEGORIES` from `categories.py`.
- `_handle_scan()`, `_handle_write()`, `main()` — dispatch logic.
- `build_table()`, `build_scan_table()` — Rich table construction (CLI-specific display).

Imports from `modbus` and `registers` instead of defining everything inline. Retains `import struct` for the `struct.error` catch in `main()`'s exception handler.

### `tui.py` (import changes only)

Current:
```python
from cli import format_value, read_registers, validate_write_value, write_register
```

After:
```python
from modbus import read_registers, write_register
from registers import format_value, validate_write_value
```

No logic changes.

### `categories.py` (unchanged)

No changes needed.

## Test Updates

- **`test_cli.py`**: Update imports to pull `format_value`, `filter_changed`, `validate_write_value` from `registers`, and `read_registers`, `write_register` from `modbus`. `filter_registers` stays imported from `cli`. Update all `range=` keyword arguments in `Register()` constructors to `value_range=`. Monkeypatch targets: `cli.ModbusTcpClient` remains correct for all CLI integration tests since client construction stays in `cli.py`.
- **`test_registers.py`**: No `.range` references to update (none exist). No import changes needed.
- **`test_tui.py`**: No changes (imports from `tui` and `registers` directly).
- **`test_categories.py`**: No changes.

Note: `scan_registers`, `build_scan_table`, and `_handle_scan` currently have zero test coverage. This refactor preserves that status quo — adding coverage is out of scope.

## Specific Code Fixes

1. **O(n) lookup in `read_registers`**: Replace `next(r for r in scalar_regs if r.address == addr)` with `reg_by_addr[addr]` dict built once before the loop.
2. **Duplicated address-range parsing**: Extract `parse_address_range(s: str) -> tuple[int, int]` that raises `ValueError` on bad input. Used by both `--address` parsing in `main()` and `_handle_scan()`.
3. **`Register.range` -> `Register.value_range`**: Rename field, update all references in `registers.py`, `cli.py`, and `test_cli.py`. (`tui.py` has no `.range` references.)

## Out of Scope

- Unifying `Register`/`StringRegister` into a class hierarchy (would be a larger refactor).
- Package structure with `src/` layout or `__init__.py`.
- Splitting test files.
- New features or behavior changes.
