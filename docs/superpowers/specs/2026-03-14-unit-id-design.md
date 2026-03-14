# Unit ID CLI Argument Design

**Date:** 2026-03-14
**Status:** Approved

## Goal

Make the Modbus unit/slave ID configurable via a `--unit-id` CLI argument (default 1) instead of hardcoding `device_id=1` throughout the codebase.

## Current State

- `device_id=1` hardcoded in 3 places in `cli.py`:
  - `client.read_holding_registers(..., device_id=1)` in `read_registers()`
  - `client.write_register(..., device_id=1)` in `write_register()`
  - `client.write_registers(..., device_id=1)` in `write_register()`
- `RegisterEditorApp` in `tui.py` calls `read_registers()` and `write_register()` without any unit ID concept

## Architecture

### CLI (`cli.py`)

Add `--unit-id` argument to argparse alongside `--port`:

```python
parser.add_argument("--unit-id", type=int, default=1, help="Modbus unit/slave ID (default: 1)")
```

Add `unit_id: int = 1` parameter to `read_registers()`:

```python
def read_registers(
    client: Any,
    registers: Sequence[Register | StringRegister],
    unit_id: int = 1,
) -> dict[int, int | str | None]:
```

Replace all `device_id=1` with `device_id=unit_id` inside `read_registers()`.

Add `unit_id: int = 1` parameter to `write_register()`:

```python
def write_register(
    client: Any,
    reg: Register | StringRegister,
    value: int | str,
    unit_id: int = 1,
) -> bool:
```

Replace all `device_id=1` with `device_id=unit_id` inside `write_register()`.

Pass `unit_id=args.unit_id` at all call sites in `main()` and `_handle_write()`.

### TUI (`tui.py`)

Add `unit_id: int = 1` to `RegisterEditorApp.__init__()`:

```python
def __init__(
    self,
    client: Any,
    registers: list[Register | StringRegister],
    values: dict[int, int | str | None],
    unit_id: int = 1,
) -> None:
    ...
    self.unit_id = unit_id
```

Pass `self.unit_id` at each call to `read_registers()` and `write_register()` within the app.

In `cli.py` where `RegisterEditorApp` is constructed:
```python
RegisterEditorApp(client, registers, values, unit_id=args.unit_id).run()
```

## Testing

### `tests/test_cli.py` additions

- `test_read_registers_uses_unit_id` — call `read_registers(client, regs, unit_id=3)`, verify `read_holding_registers` called with `device_id=3`
- `test_write_register_uses_unit_id` — call `write_register(client, reg, value, unit_id=3)`, verify `write_register` called with `device_id=3`
- `test_unit_id_cli_flag` — monkeypatch `sys.argv` with `--unit-id 3`, verify `read_holding_registers` called with `device_id=3`

### `tests/test_tui.py` additions

- `test_tui_unit_id_passed_to_write` — construct `RegisterEditorApp(..., unit_id=3)`, trigger write, verify `write_register` called with `device_id=3`

## Files Touched

| File | Change |
|------|--------|
| `cli.py` | Add `--unit-id` arg; add `unit_id` param to `read_registers()` and `write_register()`; thread through call sites |
| `tui.py` | Add `unit_id` param to `RegisterEditorApp.__init__()`; thread through call sites |
| `tests/test_cli.py` | 3 new tests |
| `tests/test_tui.py` | 1 new test |

## Out of Scope

- Per-register unit IDs
- Unit ID validation (pymodbus handles invalid values)
