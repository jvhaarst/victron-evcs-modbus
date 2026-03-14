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

- `reader.py` gains `write_register()` and `--write` / `--interactive` CLI flags
- `tui.py` is a new file containing the Textual app
- The TUI imports `read_registers`, `write_register`, `filter_registers`, `ALL_REGISTERS` from `reader.py` and `registers.py`
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

Add `access: Literal["R", "R/W"] = "R"` as the 5th field:

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

### `write_register` function

```python
def write_register(
    client: Any,
    reg: Register | StringRegister,
    value: int | str,
) -> bool:
    """Write a single register value via Modbus FC6 (scalar) or FC16 (string).

    For int16 registers, value must be a signed Python int (e.g. -500).
    Returns True on success, False on Modbus error.
    """
```

- **Scalar `Register`** (uint16 or int16): FC6 (`write_register`). int16 values < 0 converted to uint16 before writing (`value += 65536`).
- **`StringRegister`**: FC16 (`write_registers`). Value encoded to UTF-8, padded/truncated to `register_count` 16-bit words.
- Returns `True` on success, `False` on Modbus error response.

### Value validation (used by `--write` and TUI)

```python
def validate_write_value(reg: Register | StringRegister, raw_str: str) -> int | str:
    """Parse and validate a string input for writing to reg.

    Returns the validated value (int for scalar, str for string registers).
    Raises ValueError with a descriptive message on invalid input.
    """
```

- For `Register`: parse as int, check uint16 (0–65535) or int16 (−32768–32767) bounds.
- For `StringRegister`: check byte length fits in `register_count * 2` bytes.

### `--write` CLI flag

```
uv run python reader.py <host> --write <address> <value>
```

Data flow in `main()`:
1. Parse `--write <address> <value>`
2. Look up `address` in `ALL_REGISTERS`; exit 1 with error if not found
3. Check `reg.access == "R/W"`; exit 1 with error if read-only
4. Call `validate_write_value(reg, value)`; exit 1 with error if invalid
5. Connect, call `write_register(client, reg, parsed_value)`
6. Print success or error message; exit accordingly

### `--interactive` CLI flag

```
uv run python reader.py <host> --interactive [--category ...] [--address ...] [--name ...]
```

- Compatible with `--category`, `--address`, `--name` filters (applied before launching TUI)
- Connects, reads registers, then hands off to `tui.py` with the client, register list, and values dict

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
| Enter | Begin editing value (R/W registers only; no-op on R) |
| Escape | Cancel edit, restore original value |
| Ctrl+S | Write all pending changes to device |
| Ctrl+R | Refresh (re-read all registers; prompts if pending writes exist) |
| Ctrl+Q | Quit (confirmation dialog if pending writes exist) |

### Visual conventions

- **R-only rows**: dimmed text; Enter does nothing
- **Pending writes** (`*` prefix): highlighted colour until written
- **Editing**: inline Input widget replaces value cell; original value restored on Escape
- **Footer bar**: always visible, shows key bindings and pending count

### Quit confirmation dialog

When Ctrl+Q is pressed with pending writes:
```
You have N unsaved changes. Write before quitting?
  [Yes]  [No]  [Cancel]
```
- **Yes**: write all pending, then quit
- **No**: discard pending, quit immediately
- **Cancel**: return to TUI

### Refresh with pending writes

When Ctrl+R is pressed with pending writes:
```
Refreshing will discard N unsaved changes. Continue?
  [Yes]  [No]
```
- **Yes**: discard pending, re-read
- **No**: return to TUI

## Testing

### `tests/test_registers.py` additions

- `test_register_access_defaults_to_r` — `Register(...)` without `access=` has `.access == "R"`
- `test_register_rw_access` — `Register(..., access="R/W")` has `.access == "R/W"`
- `test_string_register_access_defaults_to_r` — `StringRegister(...)` without `access=` has `.access == "R"`
- `test_registers_rw_count` — exactly 76 scalar `Register` entries have `access == "R/W"`
- `test_device_name_is_rw` — `StringRegister` at address 5027 has `access == "R/W"`

### `tests/test_reader.py` additions

- `test_write_register_scalar` — mock FC6 success → `write_register` returns `True`
- `test_write_register_scalar_error` — mock FC6 error response → returns `False`
- `test_write_register_int16_negative` — value `−500` sent as `65036` over FC6
- `test_write_register_string` — mock FC16 success → returns `True`
- `test_validate_write_value_uint16_valid` — "10" for uint16 → `10`
- `test_validate_write_value_uint16_out_of_range` — "70000" → `ValueError`
- `test_validate_write_value_int16_valid` — "-500" for int16 → `-500`
- `test_validate_write_value_int16_out_of_range` — "40000" for int16 → `ValueError`
- `test_write_cli_flag` — `--write 5016 10` calls `write_register` with correct args
- `test_write_cli_invalid_address` — unknown address → exit 1 with error message
- `test_write_cli_readonly_address` — R-only address → exit 1 with error message
- `test_write_cli_out_of_range` — value out of type bounds → exit 1 with error message

### `tests/test_tui.py` (new file)

Uses Textual's `Pilot` test driver (`async`):

- `test_tui_loads` — app mounts without error, DataTable has correct row count
- `test_tui_enter_on_readonly_does_nothing` — press Enter on R row → no Input widget mounted
- `test_tui_enter_edit_escape_restores` — edit value, Escape → original value shown, no `*` marker
- `test_tui_edit_marks_pending` — edit value, Enter to confirm → `*` marker on row
- `test_tui_ctrl_s_calls_write` — pending change + Ctrl+S → `write_register` called with correct args
- `test_tui_ctrl_q_with_pending_shows_dialog` — pending change + Ctrl+Q → confirmation dialog visible

## Files Touched

| File | Change |
|------|--------|
| `registers.py` | Add `access` field to `Register` and `StringRegister`; populate 77 R/W entries |
| `reader.py` | Add `write_register`, `validate_write_value`; add `--write` and `--interactive` CLI flags |
| `tui.py` | New file: Textual app |
| `tests/test_registers.py` | 5 new tests |
| `tests/test_reader.py` | 12 new tests |
| `tests/test_tui.py` | New file: 6 TUI tests |
| `pyproject.toml` | Add `textual` dependency |

## Out of Scope

- Range validation against spec-defined min/max values
- Write confirmation per-register (Ctrl+S writes all pending at once)
- Undo history beyond single-register Escape
- Live polling / auto-refresh
