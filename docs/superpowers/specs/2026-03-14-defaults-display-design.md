# Defaults Display Design

**Date:** 2026-03-14
**Status:** Approved

## Goal

Show factory-default values alongside live register values in the CLI table, highlight values that differ from their default, and add a `--changed` flag to show only registers that have been modified from their defaults.

## Current State

- `reader.py` reads 115 registers and renders a 4-column Rich table: Address, Name, Value, Unit
- `Register` dataclass has 5 fields: `address`, `name`, `data_type`, `scale`, `unit`
- No concept of default values exists in the codebase

## Architecture

### Data Model (`registers.py`)

Add `default: int | None = None` as the last field of `Register`:

```python
@dataclass(frozen=True)
class Register:
    address: int
    name: str
    data_type: Literal["uint16", "int16"]
    scale: int
    unit: str
    default: int | None = None
```

No `__post_init__` change needed. `None` means "no default defined for this register."

`StringRegister` is unchanged — no string registers have defaults in the spec.

**Default values** are sourced from the "Default" column of `docs/specs/EVCS-Modbus-TCP-register-list-v3.8.xlsx` (sheet "Holding registers"). Registers with `-` in that column keep `default=None`.

80 of the 115 registers have numeric defaults:
- 11 of the 33 existing `REGISTERS` entries (addresses: 5009, 5016, 5017, 5026, 5049, 5050, 5062, 5094, 5095, 5109, 5127)
- 69 of the 80 `_NEW_REGISTERS` entries (all except: 5060, 5061, 5064, 5114, 5115, 5116, 5117, 5123, 5124, 5125, 5126)

Stored values are **raw register values** — the same integers that `read_registers` returns after int16 sign conversion (e.g. `-500` for address 5071, not `65036`).

### Reader Changes (`reader.py`)

**`build_table` update** — adds a 5th "Default" column and per-cell highlighting:

- Column order: Address | Name | Value | Unit | Default
- Default column content:
  - `Register` with `reg.default is not None`: `format_value(reg.default, reg.scale)` (same scaling as Value)
  - `Register` with `reg.default is None`: `""`
  - `StringRegister`: `""`
- Value cell highlighting: when `raw is not None` and `reg.default is not None` and `raw != reg.default`, wrap the value string in `[yellow]...[/yellow]`
- Registers with no default, or with a `None` (error) value, are never highlighted

**New `filter_changed` function:**

```python
def filter_changed(
    registers: Sequence[Register | StringRegister],
    values: dict[int, int | str | None],
) -> list[Register | StringRegister]:
    """Return only registers whose live value differs from their default.

    Excludes: StringRegister entries, registers with no default,
    registers whose value read as None (error).
    """
```

Keeps a register only when all of:
1. `isinstance(reg, Register)` (not `StringRegister`)
2. `reg.default is not None`
3. `values.get(reg.address) is not None`
4. `values.get(reg.address) != reg.default`

**`--changed` CLI flag** — boolean flag (`action="store_true"`):

```
uv run python reader.py <host> --changed
```

Applied **after** reading values. Data flow:

```
main()
  → parse args
  → filter_registers(ALL_REGISTERS, category=…, address_range=…, name=…)
  → connect ModbusTcpClient
  → read_registers(client, filtered_registers)
  → if --changed: filter_changed(filtered_registers, values)
  → build_table(final_registers, values)
  → print table
```

`--changed` is combinable with `--category`, `--address`, and `--name` (AND logic: existing filters narrow the register list before reading; `--changed` then narrows the result to modified registers only).

## Testing

### `tests/test_registers.py` additions

- `test_register_default_is_none_by_default` — `Register` constructed without `default=` has `.default is None`
- `test_register_with_default` — `Register(…, default=6)` has `.default == 6`
- `test_registers_with_defaults_count` — exactly 11 entries in `REGISTERS` have `default is not None`
- `test_new_registers_with_defaults_count` — exactly 69 entries in `_NEW_REGISTERS` have `default is not None`

### `tests/test_reader.py` additions

- `test_build_table_has_default_column` — table has 5 columns
- `test_build_table_shows_formatted_default` — `Register(default=6, scale=1)` with live value `10` → Default column shows `"6"`, Value cell contains `[yellow]`
- `test_build_table_no_default_shows_blank` — `Register(default=None)` → Default column cell is `""`
- `test_build_table_value_matches_default_no_highlight` — value == default → Value cell contains no `[yellow]`
- `test_filter_changed_returns_changed` — `Register(default=6)`, value=`10` → included
- `test_filter_changed_excludes_matching` — `Register(default=6)`, value=`6` → excluded
- `test_filter_changed_excludes_no_default` — `Register(default=None)` → excluded
- `test_filter_changed_excludes_error` — value=`None` → excluded
- `test_filter_changed_excludes_string_registers` — `StringRegister` → excluded

## Files Touched

| File | Change |
|---|---|
| `registers.py` | Add `default` field to `Register`; populate 80 register entries |
| `reader.py` | Update `build_table` (5th column, highlighting); add `filter_changed`; add `--changed` CLI flag |
| `tests/test_registers.py` | 4 new tests |
| `tests/test_reader.py` | 9 new tests |

## Out of Scope

- Write support (registers remain read-only)
- Displaying the spec's "Range" column
- Persisting a custom baseline (option B from brainstorming)
