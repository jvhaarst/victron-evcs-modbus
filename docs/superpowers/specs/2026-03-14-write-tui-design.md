# Write TUI Design

**Date:** 2026-03-14
**Status:** Approved

## Goal

Add write support for R/W registers via two interfaces: a non-interactive `--write` CLI flag for scripting single values, and a `--interactive` full-screen TUI for browsing and editing multiple registers.

## Current State

- `reader.py` reads 115 registers and renders a 5-column Rich table (Address, Name, Value, Unit, Default)
- `Register` dataclass has 6 fields; `StringRegister` has 4 fields
- No write support exists; all registers are treated as read-only
- The spec sheet (`EVCS-Modbus-TCP-register-list-v3.8.xlsx`) has an "Access" column: 38 registers are `R`, 77 are `R/W` (76 scalar + 1 StringRegister: Device name at 5027)

## Architecture

### Option A (chosen): `tui.py` + extend `reader.py`

- `reader.py` gains `write_register()`, `validate_write_value()`, and `--write` / `--interactive` CLI flags
- `tui.py` is a new file containing the Textual app
- The TUI imports `read_registers`, `write_register`, `validate_write_value`, `filter_registers`, `ALL_REGISTERS` from `reader.py` and `registers.py`
- Clear boundary: `reader.py` = data layer, `tui.py` = UI layer

## Data Model (`registers.py`)

### `Register` dataclass

Add `access: Literal["R", "R/W"] = "R"` as the 7th field:

```python
@dataclass(frozen=True)
class Register:
    address: int
    name: str
    data_type: Literal["uint16", "int16"]
    scale: int
    unit: str
    default: Optional[int] = None
    access: Literal["R", "R/W"] = "R"

    def __post_init__(self) -> None:
        if self.scale <= 0:
            raise ValueError(f"scale must be > 0, got {self.scale!r}")
```

### `StringRegister` dataclass

Add `access: Literal["R", "R/W"] = "R"` as the 5th field, after `encoding`. **This ordering is intentional and must not be changed**: no existing code passes `encoding` positionally, so the default is safe, but reordering would break any call of the form `StringRegister(addr, name, count, "ascii")`.

```python
@dataclass(frozen=True)
class StringRegister:
    address: int
    name: str
    register_count: int
    encoding: str = "utf-8"
    access: Literal["R", "R/W"] = "R"

    def __post_init__(self) -> None:
        if self.register_count <= 0:
            raise ValueError(f"register_count must be > 0, got {self.register_count!r}")
```

### Access values

- Default `"R"` keeps all existing constructors valid with no changes
- 76 scalar `Register` entries gain `access="R/W"` (all R/W addresses except StringRegister 5027)
- `StringRegister(5001, "Serial Id", 6)` stays `access="R"` (default)
- `StringRegister(5027, "Device name", 22)` gains `access="R/W"`

### No range field

The spec range strings are inconsistently formatted ("0 to 2", "0 - 2", "-32768 to +32767"). Validation uses type bounds only:
- `uint16`: 0 to 65535
- `int16`: −32768 to 32767

The device enforces register-specific range constraints independently.

## Reader Changes (`reader.py`)

### `validate_write_value` function

```python
def validate_write_value(reg: Register | StringRegister, input_str: str) -> int | str:
    """Parse and validate a human-readable string input for writing to reg.

    For scalar Register: input_str is the human-readable (display) value,
    using the same scale as format_value(). E.g. for scale=10, input "0.2"
    converts to raw wire value 2. Returns a raw int ready for write_register.

    For StringRegister: returns the string as-is after length validation.

    Raises ValueError with a descriptive message on invalid input.
    """
```

**Scalar `Register` rules:**
- Parse `input_str` as float (allows "0.2", "-500", "10")
- Multiply by `reg.scale` and round to nearest int to get `raw`
- Validate `raw` against type bounds: uint16 → 0–65535; int16 → −32768–32767
- Return `raw` as `int`

Examples:
- `scale=1, input="10"` → `raw=10`
- `scale=10, input="0.2"` → `raw=2`
- `scale=1, input="-500"` for int16 → `raw=-500` (valid)
- `scale=1, input="70000"` for uint16 → `ValueError`

**`StringRegister` rules:**
- Encode `input_str` to UTF-8, check byte length ≤ `register_count * 2`
- Raise `ValueError` if oversized
- Return `input_str` as `str`

### `write_register` function

```python
def write_register(
    client: Any,
    reg: Register | StringRegister,
    value: int | str,
) -> bool:
    """Write a single register value via Modbus FC6 (scalar) or FC16 (string).

    value must already be validated and in raw form:
    - For scalar Register: raw wire int (e.g. 2 for display 0.2 with scale=10)
    - For int16: signed Python int (e.g. -500); conversion to uint16 wire format
      is handled internally (value += 65536 if value < 0)
    - For StringRegister: the string value; encoded to UTF-8, null-padded to
      register_count * 2 bytes, packed as big-endian uint16 words for FC16

    Returns True on success, False on Modbus error response.
    """
```

- **Scalar `Register`** (uint16 or int16): FC6 (`client.write_register(address, wire_value, device_id=1)`). Wire value = `value + 65536` if `value < 0` else `value`.
- **`StringRegister`**: encode `value` as UTF-8, right-pad with `\x00` to exactly `register_count * 2` bytes (null termination included), unpack as `register_count` big-endian uint16 words, send via FC16 (`client.write_registers(address, words, device_id=1)`).
- Returns `True` on success, `False` on any failure: Modbus error response (`response.isError() == True`) **or** any transport-level exception (e.g. `ConnectionException`, `ModbusIOException`). Exceptions are caught internally and result in `False`; they do not propagate to the caller.

### CLI flag rules (mutual exclusion)

`--interactive`, `--write`, and `--changed` are mutually exclusive — use a single `argparse` mutually exclusive group. `--category`, `--address`, and `--name` filters remain combinable with all three (they are not in the exclusive group). When used with `--write`, filters have no effect (the address is specified directly); they are silently ignored.

### `--write` CLI flag

```
uv run python reader.py <host> --write <address> <value>
```

- `--write` takes `nargs=2` (address string, value string)
- Argparse handles negative numbers in `nargs=2` correctly when they follow the address string — no special syntax required: `--write 5071 -500` works as-is
- String values with spaces must be shell-quoted: `--write 5027 "My Charger"`

Data flow in `main()`:
1. Parse `--write address value` (both as strings)
2. Look up `address` (as int) in `ALL_REGISTERS`; exit 1 with error if not found
3. Check `reg.access == "R/W"`; exit 1 with error if read-only
4. Call `validate_write_value(reg, value)`; exit 1 with error if invalid
5. Connect, call `write_register(client, reg, raw_value)`
6. On success print the display value: `"Written 5016 (Charging current): 10 A"` (formatted with `format_value(raw, reg.scale)` and `reg.unit`); on error print failure message; exit accordingly

### `--interactive` CLI flag

```
uv run python reader.py <host> --interactive [--category ...] [--address ...] [--name ...]
```

- Compatible with `--category`, `--address`, `--name` filters (applied before launching TUI)
- Mutually exclusive with `--write` and `--changed`
- Connects, reads registers, then launches the Textual app from `tui.py`, passing the client, filtered register list, and values dict

## TUI (`tui.py`)

### Layout

```
┌─ Victron EVCS Register Editor ──────────────────────────────────────┐
│ Address │ Name                  │ Value  │ Unit │ Default │ Access  │
│─────────────────────────────────────────────────────────────────────│
│   5009  │ Charge mode           │ 0      │      │ 0       │ R/W     │
│ ► 5016  │ Charging current      │[ 16  ] │ A    │ 6       │ R/W     │  ← editing
│   5017  │ Max current           │ 10     │ A    │ 10      │ R/W     │
│   5018  │ Charging current act. │ 16.0   │ A    │         │ R       │  ← dimmed
│ * 5026  │ Charger position      │ 1      │      │ 0       │ R/W     │  ← pending
└─────────────────────────────────────────────────────────────────────┘
│ 3 pending  ^S Write  ^R Refresh  ^Q Quit  Enter Edit  Esc Cancel   │
└─────────────────────────────────────────────────────────────────────┘
```

### Key bindings (nano-style)

| Key | Action |
|-----|--------|
| Arrow keys | Navigate rows |
| Enter | Begin editing (R/W registers only; no-op on R); **or confirm edit** when in edit mode |
| Escape | Cancel edit, restore original value |
| Ctrl+S | Write all pending changes to device |
| Ctrl+R | Refresh (re-read all registers; prompts if pending writes exist) |
| Ctrl+Q | Quit (confirmation dialog if pending writes exist) |

### Visual conventions

- **R-only rows**: dimmed text; Enter does nothing
- **Pending writes** (`*` prefix): highlighted colour until written
- **Editing**: inline Input widget replaces value cell; input pre-filled with current display value (from `format_value`); Enter confirms the edit (validates, marks pending); Escape cancels and restores original
- **Footer bar**: always visible, shows key bindings and pending count
- **Table construction**: the TUI builds its own `Textual` `DataTable` widget directly — it does **not** reuse `build_table` from `reader.py`. Columns: Address, Name, Value, Unit, Default, Access (6 columns)

### Quit confirmation dialog

When Ctrl+Q is pressed with pending writes:
```
You have N unsaved changes. Write before quitting?
  [Yes]  [No]  [Cancel]
```
- **Yes**: write all pending, then quit
- **No**: discard pending, quit immediately
- **Cancel**: dismiss dialog, return to TUI

### Refresh with pending writes

When Ctrl+R is pressed with pending writes:
```
Refreshing will discard N unsaved changes. Continue?
  [Yes]  [No]
```
- **Yes**: discard pending, re-read all registers, clear all `*` markers
- **No**: dismiss dialog, return to TUI

### Connection error handling

If a write fails during Ctrl+S (e.g. network drop), `write_register` returns `False`. The TUI:
- Stops writing further registers (does not attempt remaining pending writes)
- Shows a status bar error: `"Write failed at address XXXX — check connection"`
- Keeps all affected registers marked as pending (not cleared)
- Remains open; the user may retry Ctrl+S or Ctrl+Q

If Ctrl+R fails to read (connection error), the values dict retains stale values and a status bar error is shown.

## Dependencies

Add to `pyproject.toml`:
- Runtime: `textual>=0.47.0`
- Dev/test: `pytest-asyncio` (for async TUI tests using Textual's `Pilot`)

## Testing

### `tests/test_registers.py` additions (5 tests)

- `test_register_access_defaults_to_r` — `Register(...)` without `access=` has `.access == "R"`
- `test_register_rw_access` — `Register(..., access="R/W")` has `.access == "R/W"`
- `test_string_register_access_defaults_to_r` — `StringRegister(...)` without `access=` has `.access == "R"`
- `test_registers_rw_count` — exactly 76 scalar `Register` entries have `access == "R/W"`
- `test_device_name_is_rw` — `StringRegister` at address 5027 has `access == "R/W"`

### `tests/test_reader.py` additions (13 tests)

- `test_write_register_scalar` — mock FC6 success → `write_register` returns `True`
- `test_write_register_scalar_error` — mock FC6 error response → returns `False`
- `test_write_register_int16_negative` — value `−500` sent as `65036` over FC6
- `test_write_register_string` — mock FC16 success → returns `True`
- `test_validate_write_value_uint16_valid` — `"10"` for scale=1 uint16 → `10`
- `test_validate_write_value_scaled` — `"0.2"` for scale=10 uint16 → raw `2`
- `test_validate_write_value_uint16_out_of_range` — `"70000"` → `ValueError`
- `test_validate_write_value_int16_valid` — `"-500"` for int16 → `-500`
- `test_validate_write_value_int16_out_of_range` — `"40000"` for int16 → `ValueError`
- `test_write_cli_flag` — `--write 5016 10` calls `write_register` with correct args
- `test_write_cli_invalid_address` — unknown address → exit 1 with error message
- `test_write_cli_readonly_address` — R-only address → exit 1 with error message
- `test_write_cli_out_of_range` — value out of type bounds → exit 1 with error message

### `tests/test_tui.py` (new file, 10 tests)

Uses Textual's `Pilot` test driver (`async`, requires `pytest-asyncio`):

- `test_tui_loads` — app mounts without error, DataTable has correct row count
- `test_tui_enter_on_readonly_does_nothing` — press Enter on R row → no Input widget mounted
- `test_tui_enter_edit_escape_restores` — edit value, Escape → original value shown, no `*` marker
- `test_tui_edit_marks_pending` — edit value, confirm → `*` marker on row
- `test_tui_ctrl_s_calls_write` — pending change + Ctrl+S → `write_register` called with correct args
- `test_tui_ctrl_q_with_pending_shows_dialog` — pending change + Ctrl+Q → confirmation dialog visible
- `test_tui_ctrl_q_dialog_no_discards` — pending change + Ctrl+Q + No → quits without writing
- `test_tui_ctrl_q_dialog_cancel_returns` — pending change + Ctrl+Q + Cancel → dialog dismissed, TUI active
- `test_tui_ctrl_r_with_pending_shows_dialog` — pending change + Ctrl+R → refresh confirmation dialog visible
- `test_tui_ctrl_s_write_failure_shows_error` — pending change + Ctrl+S + `write_register` returns False → status bar shows error, row still marked pending

## Files Touched

| File | Change |
|------|--------|
| `registers.py` | Add `access` field to `Register` and `StringRegister`; populate 77 R/W entries |
| `reader.py` | Add `write_register`, `validate_write_value`; add `--write` and `--interactive` CLI flags |
| `tui.py` | New file: Textual app |
| `tests/test_registers.py` | 5 new tests |
| `tests/test_reader.py` | 13 new tests |
| `tests/test_tui.py` | New file: 10 TUI tests |
| `pyproject.toml` | Add `textual>=0.47.0` runtime; `pytest-asyncio` dev dependency |

## Out of Scope

- Range validation against spec-defined min/max values
- Write confirmation per-register (Ctrl+S writes all pending at once)
- Undo history beyond single-register Escape
- Live polling / auto-refresh
