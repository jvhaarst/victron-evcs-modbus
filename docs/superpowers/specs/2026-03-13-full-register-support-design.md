# Full Register Support Design

**Date:** 2026-03-13
**Status:** Approved

## Goal

Extend the Victron EVCS Modbus TCP reader to cover all 115 named holding registers from the spec sheet, with support for string registers, signed int16 registers, and CLI filtering by category, address range, and name substring.

## Current State

- 33 scalar `uint16` registers implemented in `registers.py`
- Single `Register` frozen dataclass (address, name, data_type, scale, unit)
- `reader.py` reads all registers in one batched FC3 call (chunked to 125-register limit)
- CLI: `uv run python reader.py <host> [--port PORT]`

## Architecture

### Data Model (`registers.py`)

Keep `Register` (scalar) unchanged. Add a `StringRegister` dataclass for multi-register string reads:

```python
@dataclass(frozen=True)
class StringRegister:
    address: int        # start address
    name: str
    register_count: int # number of Modbus registers (each holds 2 bytes)
    encoding: str = "utf-8"
```

Two new lists:
- `STRING_REGISTERS` — the 2 string registers (Serial Id: 5001–5006, Device name: 5027–5048)
- `ALL_REGISTERS: list[Register | StringRegister]` — full combined list (115 entries: 33 existing + 80 new scalar + 2 string)

`REGISTERS` (existing 33 scalar entries) is kept as-is for backwards compatibility.

The 80 new scalar registers to add come from `docs/specs/EVCS-Modbus-TCP-register-list-v3.8.xlsx` (sheet "Holding registers"). All addresses 5051–5140 not yet in `REGISTERS`, plus missing addresses in 5051–5093 and 5096–5120 range. See the spreadsheet for the authoritative list of names, types, scales, and units.

### Categories (`categories.py`)

New file with a `CATEGORIES` dict mapping category name → list of addresses. Registers may appear in multiple categories. Categories are separate from register definitions.

```python
CATEGORIES: dict[str, list[int]] = {
    "status":      [...],   # charger state, power, current, errors
    "session":     [...],   # session time, energy, cost
    "device":      [...],   # product id, serial, firmware, name, uptime
    "config":      [...],   # charging config, protection settings
    "auto_mode":   [...],   # feed-in and battery-powered auto mode params
    "sensors":     [...],   # humidity + temperatures (5121-5127)
    "diagnostics": [...],   # calibration, relay status, reboot counters
}
```

### Reader Changes (`reader.py`)

**int16 sign conversion** — in `read_registers`, after storing a raw value, if `reg.data_type == "int16"` and `raw > 32767`, apply `raw -= 65536`. Stored in the result dict as a signed Python int.

**String reads** — `StringRegister` entries are read individually (not batched with scalars, as they span non-contiguous address blocks). Each read:
1. Calls `read_holding_registers(address=reg.address, count=reg.register_count, device_id=1)`
2. Packs the uint16 words as big-endian bytes: `struct.pack(f">{reg.register_count}H", *raw_words)`
3. Strips **trailing** null bytes only: `raw_bytes.rstrip(b'\x00')` (not `strip()` or `replace`, to preserve embedded nulls if present)
4. Decodes with `reg.encoding`
5. Result stored in the shared dict as a `str` (or `None` on error)

Return type becomes `dict[int, int | str | None]`.

**`build_table` update** — `StringRegister` has no `.scale` or `.unit`. `build_table` must branch on register type:
- Scalar `Register`: render value via `format_value(raw, reg.scale)`, unit column from `reg.unit`
- `StringRegister`: render value as the decoded string directly (no scale), unit column blank (`""`)
- Either type with `None` value: render `"[red]error[/red]"`, unit blank

`format_value` is only called for scalar `Register` entries.

**Filtering** — new `filter_registers` function:

```python
def filter_registers(
    registers: Sequence[Register | StringRegister],
    *,
    category: str | None = None,
    address_range: tuple[int, int] | None = None,
    name: str | None = None,
) -> list[Register | StringRegister]:
```

- `category`: keep registers whose address appears in `CATEGORIES[category]`
- `address_range`: keep registers with `start <= address <= end`
- `name`: case-insensitive substring match on `reg.name`
- Multiple filters AND together (intersection)
- No filters → return all registers

### CLI Changes (`reader.py` `main()`)

Three new optional arguments:

| Argument | Example | Effect |
|---|---|---|
| `--category` | `--category sensors` | Filter to predefined category |
| `--address` | `--address 5000-5050` | Filter by address range (inclusive) |
| `--name` | `--name power` | Filter by name substring (case-insensitive) |

Multiple flags combine as AND. Invalid category name prints available categories and exits with code 1.

**`--address` parsing:** The value is a string in the form `"START-END"` (e.g. `"5000-5050"`). Parse in `main()` by splitting on `"-"` and converting both parts to `int`. On malformed input (not exactly two integer parts), print an error message and exit with code 1.

## Data Flow

```
main()
  → parse args (host, port, category, address, name)
  → build filter from args via filter_registers(ALL_REGISTERS, ...)
  → connect ModbusTcpClient
  → read_registers(client, filtered_registers)
      → for each scalar chunk: read_holding_registers (batched, ≤125)
      → for each StringRegister: read_holding_registers (individual)
      → apply int16 sign conversion
  → build_table(filtered_registers, values)
  → print table
```

## Testing

### `test_registers.py` additions
- `StringRegister` has required fields and defaults (`encoding="utf-8"`)
- `ALL_REGISTERS` has exactly 115 entries
- No duplicate addresses across `REGISTERS` and `STRING_REGISTERS`

### `test_categories.py` (new)
- All addresses in each category exist in `ALL_REGISTERS`
- `sensors` category contains 5121 (humidity)
- No unknown category names

### `test_reader.py` additions
- int16 sign conversion: raw `65036` (= -500 as int16) → stored as `-500`
- String decode: mock whose `.registers` returns `[0x4D79, 0x4465, 0x7669, 0x6365, 0x0000, 0x0000]` → decoded string `"MyDevice"` (mock must return uint16 word list, not bytes)
- `filter_registers` with `category="sensors"` returns only sensor addresses
- `filter_registers` with `address_range=(5000, 5015)` returns correct subset
- `filter_registers` with `name="power"` returns all registers with "power" in name
- Combined filters AND correctly
- `build_table` renders `StringRegister` value as string directly, unit column blank

## Files Touched

| File | Change |
|---|---|
| `registers.py` | Add 80 new scalar `Register` entries, `StringRegister` dataclass, `STRING_REGISTERS`, `ALL_REGISTERS` |
| `categories.py` | New file: `CATEGORIES` dict |
| `reader.py` | int16 conversion, string reads, `filter_registers`, CLI args |
| `tests/test_registers.py` | New tests for `StringRegister`, `ALL_REGISTERS` |
| `tests/test_categories.py` | New test file |
| `tests/test_reader.py` | New tests for sign conversion, string decode, filtering |

## Out of Scope

- Write support (all registers remain read-only in this iteration)
- Parsing register definitions from the Excel file at runtime
- `--unit-id` CLI argument (tracked in beads as `victron_evcs_modbus-dmp`)
