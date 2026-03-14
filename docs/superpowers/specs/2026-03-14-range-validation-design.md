# Range Validation Design

**Date:** 2026-03-14
**Status:** Approved

## Goal

After a user enters a value for a write (`--write` CLI or TUI editor), validate it against the device's documented register range before sending to the device. Reject values outside the range with a descriptive error. Source: `docs/specs/EVCS-Modbus-TCP-register-list-v3.8.xlsx` Range column.

## Current State

- `Register` has no range field
- `validate_write_value()` validates only data type bounds (uint16: 0–65535, int16: –32768–32767)
- Values outside device range are silently sent; the device may clamp or ignore them

## Architecture

### Data Model (`registers.py`)

Add `range: tuple[float, float] | None = None` as the last field on `Register`, after `notes`.

> **Note on field name:** `range` shadows the Python built-in `range`. This is accepted as a trade-off — the name precisely matches the domain vocabulary and the built-in is not used inside the dataclass body. Linters may warn; the warning is acceptable.



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
    notes: str = ""
    range: tuple[float, float] | None = None
```

- Type is `tuple[float, float]` to support scaled registers (e.g., scale=10 → (0.1, 6553.5))
- `None` means no documented range constraint (use type bounds only)
- Only `Register` gets this field; `StringRegister` does not (strings are length-bounded, not range-bounded)

### Validation (`cli.py`)

In `validate_write_value()`, add a range check **after** parsing `display_val` as float and **before** multiplying by scale. An invalid-number error (non-numeric input) is raised before the range check; range validation only runs when input is a valid number.

```python
display_val = float(input_str)  # existing
# New:
if reg.range is not None:
    lo, hi = reg.range
    if not (lo <= display_val <= hi):
        raise ValueError(
            f"Value out of range: {display_val} is not between {lo} and {hi}"
        )
raw = round(display_val * reg.scale)  # existing
```

### Range Population (`registers.py`)

Range values are stored as display floats (raw ÷ scale), sourced from the xlsx Range column. Registers are **not** given a range if:

- The range equals the data type bounds (uint16: 0–65535; int16: –32768–(+)32767)
- The range is a single value or complex expression (e.g., `"1.0"`, `"(0 to 32)*10"`)
- The range is a garbage value (e.g., `"2023-03-01 00:00:00"`)
- The register is read-only (range validation has no effect)

The following table lists every R/W register that receives a non-`None` range (59 total):

| Address | Name | scale | xlsx Range | range tuple |
|---------|------|-------|-----------|-------------|
| 5009 | Charge mode | 1 | `0 to 2` | `(0.0, 2.0)` |
| 5010 | Start/stop charging | 1 | `0 to 1` | `(0.0, 1.0)` |
| 5016 | Charging current | 1 | `6 to 32` | `(6.0, 32.0)` |
| 5017 | Max current | 1 | `6 to 32` | `(6.0, 32.0)` |
| 5026 | Charger position | 1 | `0 to 1` | `(0.0, 1.0)` |
| 5049 | Charger autostart | 1 | `0 to 1` | `(0.0, 1.0)` |
| 5050 | Control via display | 1 | `0 to 1` | `(0.0, 1.0)` |
| 5051 | Display active backlight | 1 | `1 to 100` | `(1.0, 100.0)` |
| 5052 | Display idle backlight | 1 | `1 to 100` | `(1.0, 100.0)` |
| 5053 | Display active timeout | 1 | `1 to 65535` | `(1.0, 65535.0)` |
| 5054 | Contactor active when charged | 1 | `0 to 1` | `(0.0, 1.0)` |
| 5055 | Manual mode phase | 1 | `0 to 1` | `(0.0, 1.0)` |
| 5056 | Auto mode phase | 1 | `0 to 2` | `(0.0, 2.0)` |
| 5057 | Power for 3phase | 1 | `1 to 65535` | `(1.0, 65535.0)` |
| 5058 | Power for single phase | 1 | `1 to 65535` | `(1.0, 65535.0)` |
| 5059 | Phase switching timeout | 1 | `1 to 65535` | `(1.0, 65535.0)` |
| 5060 | CP Calibration command | 1 | `1 to 4` | `(1.0, 4.0)` |
| 5062 | Min current | 1 | `6 to 31` | `(6.0, 31.0)` |
| 5063 | Power calibration offset | 1 | `60 - 140` | `(60.0, 140.0)` |
| 5065 | Auto mode type | 1 | `0 to 1` | `(0.0, 1.0)` |
| 5066 | Backup battery SOC for start charging in Battery powered | 1 | `1 to 100` | `(1.0, 100.0)` |
| 5067 | Backup battery min SOC to allow charging if OFF Grid | 1 | `1 to 100` | `(1.0, 100.0)` |
| 5068 | Backup battery emulation | 1 | `0 to 1` | `(0.0, 1.0)` |
| 5069 | 'Feed in'. Start delay | 1 | `1 to 65535` | `(1.0, 65535.0)` |
| 5070 | 'Feed in'. Stop delay | 1 | `1 to 65535` | `(1.0, 65535.0)` |
| 5076 | 'Feed in'. Current step | 10 | `1 to 65535` | `(0.1, 6553.5)` |
| 5077 | 'Feed in'. Time step | 1 | `1 to 65535` | `(1.0, 65535.0)` |
| 5078 | 'Battery powered'. Start delay min | 1 | `1 to 65535` | `(1.0, 65535.0)` |
| 5079 | 'Battery powered'. Stop delay | 1 | `1 to 65535` | `(1.0, 65535.0)` |
| 5080 | 'Battery powered'. Start abort delay | 1 | `1 to 65535` | `(1.0, 65535.0)` |
| 5082 | 'Battery powered'. BKPB balance SOC max | 1 | `1 - 100` | `(1.0, 100.0)` |
| 5085 | 'Battery powered'. BKPB power threshold for decrease | 1 | `1 to 65535` | `(1.0, 65535.0)` |
| 5086 | 'Battery powered'. Grid power threshold for decrease | 1 | `1 to 65535` | `(1.0, 65535.0)` |
| 5087 | 'Battery powered'. Discharging detect timeout | 1 | `1 to 65535` | `(1.0, 65535.0)` |
| 5088 | 'Battery powered'. Next try timeout for increase | 1 | `1 to 65535` | `(1.0, 65535.0)` |
| 5089 | 'Battery powered'. Time step | 1 | `1 to 65535` | `(1.0, 65535.0)` |
| 5090 | 'Battery powered'. Current step | 10 | `1 to 65535` | `(0.1, 6553.5)` |
| 5091 | 'Battery powered'. Grid power for 'feed in' detection | 1 | `-32768 to -1` | `(-32768.0, -1.0)` |
| 5092 | 'Battery powered'. Start delay max | 1 | `1 to 65535` | `(1.0, 65535.0)` |
| 5099 | External lock | 1 | `0 to 1` | `(0.0, 1.0)` |
| 5100 | Multiple relay charging | 1 | `0 to 1` | `(0.0, 1.0)` |
| 5101 | Multiple relay charging. Relays switching delay | 1 | `1 to 65535` | `(1.0, 65535.0)` |
| 5102 | Allow battery/grid power for auto mode | 1 | `0 to 1` | `(0.0, 1.0)` |
| 5103 | Battery/grid power timeout | 1 | `5 to 65535` | `(5.0, 65535.0)` |
| 5104 | Overload protection | 1 | `0 to 1` | `(0.0, 1.0)` |
| 5105 | Input current limit | 10 | `1 to 65535` | `(0.1, 6553.5)` |
| 5106 | Overload protection ON/OFF timeout | 1 | `1 to 65535` | `(1.0, 65535.0)` |
| 5107 | Overload protection cut-off timeout | 1 | `1 to 65535` | `(1.0, 65535.0)` |
| 5118 | Overload current decrease timeout | 1 | `1 to 65535` | `(1.0, 65535.0)` |
| 5119 | Overload current decrease counter | 1 | `1 to 65535` | `(1.0, 65535.0)` |
| 5120 | Overload current decrease rate | 1 | `1 to 65535` | `(1.0, 65535.0)` |
| 5132 | Light ring brightness limit | 1 | `0 -100` (typo) | `(0.0, 100.0)` |
| 5133 | CP auto-calibration state | 1 | `0 to 1` | `(0.0, 1.0)` |
| 5134 | 'Battery powered'. Low excess power threshold | 1 | `1 to 65535` | `(1.0, 65535.0)` |
| 5136 | 'Battery powered'. Emulated BKPB SoC | 1 | `0 - 100` | `(0.0, 100.0)` |
| 5137 | 'Battery powered'. 'feed in' detection | 1 | `0 to 1` | `(0.0, 1.0)` |
| 5138 | 'Battery powered'. BKPB SoC max | 1 | `1 to 100` | `(1.0, 100.0)` |
| 5139 | Multiple relay charging. Conditions check delay | 1 | `1 to 65535` | `(1.0, 65535.0)` |
| 5140 | Online update feed | 1 | `0 to 1` | `(0.0, 1.0)` |

Registers **not** given a range (skipped):

| Address | Reason |
|---------|--------|
| 5064 EVCS reset | Range `"1.0"` is single value; register is a command |
| 5071–5075 int16 R/W | Range `"-32768 to +32767"` is the full int16 bounds — not tighter than the type |
| 5081, 5083, 5084, 5093 | Range `"0 to 65535"` equals uint16 type bounds |
| 5108, 5110 | Range `"0 - 65535"` equals uint16 type bounds |
| 5128–5131 | Range `"0 - 65535"` equals uint16 type bounds |
| 5135 int16 | Range `"-32768 to 32767"` equals int16 type bounds |

## Testing

### `tests/test_cli.py` additions

- `test_validate_write_value_range_ok` — reg with range `(6.0, 32.0)`, input `"10"` → returns `10`, no error
- `test_validate_write_value_range_boundary_low` — input `"6"` (exactly at `lo`) → returns `6`, no error (inclusive bound)
- `test_validate_write_value_range_boundary_high` — input `"32"` (exactly at `hi`) → returns `32`, no error (inclusive bound)
- `test_validate_write_value_range_too_low` — input `"5"` → `ValueError` containing `"out of range"`
- `test_validate_write_value_range_too_high` — input `"33"` → `ValueError` containing `"out of range"`
- `test_validate_write_value_no_range` — reg with `range=None`, input `"1000"` (within uint16 bounds, would be rejected by many device ranges if one were set) → no range error, returns `1000`

### No new TUI tests

TUI validation calls `validate_write_value()` indirectly when the user enters a value. The function is already unit-tested. The TUI test for invalid-input handling already exercises the error path.

## Files Touched

| File | Change |
|------|--------|
| `registers.py` | Add `range` field to `Register`; populate for 59 R/W registers |
| `cli.py` | Add range check in `validate_write_value()` before scale multiplication |
| `tests/test_cli.py` | 6 new tests |

## Invariants

- The `range` tuple, when not `None`, must satisfy `lo <= hi`. This is not validated at dataclass construction time — correctness is enforced at data-entry time (the values in `registers.py` are manually verified against the xlsx).

## Out of Scope

- Displaying the range in the TUI editor or table (future)
- Range validation for string length (already enforced separately)
- Clamping values to range (error + reject is the right UX)
