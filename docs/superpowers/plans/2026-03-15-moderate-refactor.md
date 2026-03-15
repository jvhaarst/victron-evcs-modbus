# Moderate Refactor Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract `cli.py` into focused modules (`modbus.py`, enriched `registers.py`, slimmed `cli.py`) and fix code smells.

**Architecture:** Move Modbus I/O into `modbus.py`, register-related logic into `registers.py`, keep CLI orchestration in `cli.py`. No functional changes — existing tests validate correctness at each step.

**Tech Stack:** Python 3.12, pymodbus, rich, textual, pytest

**Spec:** `docs/superpowers/specs/2026-03-15-moderate-refactor-design.md`

**Test command:** `uv run pytest -v`
**Lint command:** `uvx ruff check .`

---

## Chunk 1: Rename and extract helpers

### Task 1: Rename `Register.range` to `Register.value_range`

**Files:**
- Modify: `registers.py:19` (dataclass field)
- Modify: `registers.py:30-139` (all `range=` keyword args in REGISTERS list)
- Modify: `cli.py:203-204` (`reg.range` attribute access in `validate_write_value`)
- Modify: `tests/test_cli.py` (all `range=` keyword args in Register constructors)

- [ ] **Step 1: Rename the dataclass field in `registers.py`**

In `registers.py`, line 19, change:
```python
    range: tuple[float, float] | None = None  # display-value range (raw ÷ scale); None = no constraint  # noqa: A003
```
to:
```python
    value_range: tuple[float, float] | None = None  # display-value range (raw ÷ scale); None = no constraint
```

Then use replace-all to change every `range=` keyword argument to `value_range=` in the REGISTERS list (lines 30-139). There are 59 occurrences like `range=(0.0, 2.0)` → `value_range=(0.0, 2.0)`.

- [ ] **Step 2: Update `cli.py` references**

In `cli.py`, lines 203-204, change:
```python
    if reg.range is not None:
        lo, hi = reg.range
```
to:
```python
    if reg.value_range is not None:
        lo, hi = reg.value_range
```

- [ ] **Step 3: Update `tests/test_cli.py` references**

Replace all `range=(` with `value_range=(` in Register constructors (lines 602, 607, 612, 617, 623, 636). Also update the comment on line 629:
```python
    # range=None means no range constraint beyond type bounds
```
to:
```python
    # value_range=None means no range constraint beyond type bounds
```

- [ ] **Step 4: Run tests and lint**

```bash
uv run pytest -v
uvx ruff check .
```

Expected: All 117 tests pass. Ruff clean (the `# noqa: A003` is gone).

- [ ] **Step 5: Commit**

```bash
git add registers.py cli.py tests/test_cli.py
git commit -m "refactor: rename Register.range to value_range (removes builtin shadow)"
```

---

### Task 2: Add `parse_address_range` to `registers.py`

**Files:**
- Modify: `registers.py` (add function after `ALL_REGISTERS`)
- Create: test in `tests/test_registers.py`

- [ ] **Step 1: Write failing tests in `tests/test_registers.py`**

Add at end of file:
```python
from registers import parse_address_range


def test_parse_address_range_valid():
    assert parse_address_range("5000-5050") == (5000, 5050)


def test_parse_address_range_single_register():
    assert parse_address_range("5000-5000") == (5000, 5000)


def test_parse_address_range_invalid_format():
    with pytest.raises(ValueError, match="Format: START-END"):
        parse_address_range("bad-range")


def test_parse_address_range_not_enough_parts():
    with pytest.raises(ValueError, match="Format: START-END"):
        parse_address_range("5000")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_registers.py::test_parse_address_range_valid -v
```

Expected: ImportError — `parse_address_range` not defined yet.

- [ ] **Step 3: Implement `parse_address_range` in `registers.py`**

Add after the `ALL_REGISTERS` definition (after line 165):
```python
def parse_address_range(range_str: str) -> tuple[int, int]:
    """Parse a 'START-END' string into a (start, end) integer tuple.

    Raises ValueError if the format is invalid.
    """
    parts = range_str.split("-")
    if len(parts) != 2 or not all(p.strip().isdigit() for p in parts):
        raise ValueError(
            f"Invalid address range '{range_str}'. Format: START-END (e.g. 5000-5050)"
        )
    return int(parts[0]), int(parts[1])
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_registers.py -v
uvx ruff check .
```

Expected: All tests pass. Ruff clean.

- [ ] **Step 5: Commit**

```bash
git add registers.py tests/test_registers.py
git commit -m "refactor: add parse_address_range helper to registers.py"
```

---

## Chunk 2: Create `modbus.py`

### Task 3: Extract Modbus I/O into `modbus.py`

**Files:**
- Create: `modbus.py`
- Modify: `cli.py` (remove extracted functions, add imports from modbus)
- Modify: `tui.py:12` (update imports)
- Modify: `tests/test_cli.py` (update imports for `read_registers`, `write_register`)

- [ ] **Step 1: Create `modbus.py`**

Create `modbus.py` by extracting three functions from `cli.py`. Include the O(n) fix in `read_registers` — replace `next(r for r in scalar_regs if r.address == addr)` with a pre-built dict.

```python
"""Modbus TCP I/O operations for Victron EVCS registers."""
from __future__ import annotations

import struct
from typing import TYPE_CHECKING, Any

from pymodbus.client import ModbusTcpClient

from registers import Register, StringRegister

if TYPE_CHECKING:
    from collections.abc import Sequence


def read_registers(
    client: Any,
    registers: Sequence[Register | StringRegister],
    unit_id: int = 1,
) -> dict[int, int | str | None]:
    """Read registers in batch requests (max 125 per FC3 call) for scalars,
    and individually for string registers.

    Returns a dict mapping address -> raw value (or None on error).
    """
    if not registers:
        return {}

    scalar_regs = [r for r in registers if isinstance(r, Register)]
    string_regs = [r for r in registers if isinstance(r, StringRegister)]
    result: dict[int, int | str | None] = {}

    # Batch-read scalar registers (chunked to ≤125 addresses per FC3 call)
    if scalar_regs:
        reg_by_addr = {r.address: r for r in scalar_regs}
        addresses = sorted(reg_by_addr)
        chunk_start = 0
        while chunk_start < len(addresses):
            start_addr = addresses[chunk_start]
            chunk_end = chunk_start
            while (
                chunk_end + 1 < len(addresses)
                and addresses[chunk_end + 1] - start_addr < 125
            ):
                chunk_end += 1
            end_addr = addresses[chunk_end]
            count = end_addr - start_addr + 1

            response = client.read_holding_registers(
                address=start_addr, count=count, device_id=unit_id
            )
            if response.isError():
                for addr in addresses[chunk_start : chunk_end + 1]:
                    result[addr] = None
            else:
                raw_values = response.registers
                for addr in addresses[chunk_start : chunk_end + 1]:
                    offset = addr - start_addr
                    raw = raw_values[offset] if offset < len(raw_values) else None
                    if raw is not None:
                        reg = reg_by_addr[addr]
                        if reg.data_type == "int16" and raw > 32767:
                            raw -= 65536
                    result[addr] = raw
            chunk_start = chunk_end + 1

    # Read string registers individually
    for reg in string_regs:
        response = client.read_holding_registers(
            address=reg.address, count=reg.register_count, device_id=unit_id
        )
        if response.isError():
            result[reg.address] = None
        else:
            raw_bytes = struct.pack(f"<{reg.register_count}H", *response.registers)
            result[reg.address] = raw_bytes.rstrip(b"\x00").decode(reg.encoding)

    return result


def write_register(
    client: Any,
    reg: Register | StringRegister,
    value: int | str,
    unit_id: int = 1,
    verify: bool = False,
) -> tuple[bool, bool | None]:
    """Write a single register via Modbus FC6 (scalar) or FC16 (string).

    Returns (success, verified):
      (True,  None)  — write OK, verify not requested
      (True,  True)  — write OK, read-back matched
      (True,  False) — write OK, read-back mismatch (device may have clamped value)
      (False, None)  — write failed
    """
    try:
        if isinstance(reg, StringRegister):
            raw_bytes = value.encode(reg.encoding)
            padded = raw_bytes.ljust(reg.register_count * 2, b"\x00")
            words = list(struct.unpack(f"<{reg.register_count}H", padded))
            response = client.write_registers(
                address=reg.address, values=words, device_id=unit_id
            )
        else:
            wire_value = (value + 65536) if value < 0 else value
            response = client.write_register(
                address=reg.address, value=wire_value, device_id=unit_id
            )
        if response.isError():
            return False, None
        if not verify:
            return True, None
        try:
            count = reg.register_count if isinstance(reg, StringRegister) else 1
            rb = client.read_holding_registers(
                address=reg.address, count=count, device_id=unit_id
            )
            if rb.isError():
                return True, None
            if isinstance(reg, StringRegister):
                rb_bytes = struct.pack(f"<{reg.register_count}H", *rb.registers)
                rb_str = rb_bytes.rstrip(b"\x00").decode(reg.encoding)
                return True, rb_str == value
            return True, rb.registers[0] == wire_value
        except (OSError, struct.error, UnicodeDecodeError):
            return True, None
    except OSError:
        return False, None


def scan_registers(
    client: Any,
    start: int,
    end: int,
    unit_id: int = 1,
) -> dict[int, int | None]:
    """Read raw uint16 values for every address in [start, end] inclusive.

    Reads in chunks of up to 125 registers per FC3 call.
    Returns a dict mapping address -> raw uint16 value (or None on error).
    """
    result: dict[int, int | None] = {}
    addr = start
    while addr <= end:
        count = min(125, end - addr + 1)
        response = client.read_holding_registers(address=addr, count=count, device_id=unit_id)
        if response.isError():
            for a in range(addr, addr + count):
                result[a] = None
        else:
            for i, raw in enumerate(response.registers):
                result[addr + i] = raw
        addr += count
    return result
```

- [ ] **Step 2: Update `cli.py` — remove extracted functions, add imports**

Remove these functions from `cli.py`:
- `read_registers` (lines 30-91)
- `write_register` (lines 279-326)
- `scan_registers` (lines 222-245)

Add to `cli.py` imports (near the top, after existing imports):
```python
from modbus import read_registers, scan_registers, write_register
```

Remove `from pymodbus.client import ModbusTcpClient` from cli.py — wait, cli.py still creates `ModbusTcpClient` instances in `_handle_scan`, `_handle_write`, and `main`. So keep `ModbusTcpClient` import in `cli.py`.

Remove the now-unused `from typing import TYPE_CHECKING, Any` import only if `Any` is no longer used in cli.py. Check: `_handle_scan` and `_handle_write` use `args: Any`, so `Any` stays. `TYPE_CHECKING` and `Sequence` can be removed if no remaining function uses them — `filter_registers`, `filter_changed`, `build_table`, `build_scan_table` all use `Sequence`, so keep `TYPE_CHECKING` and `Sequence`.

The `import struct` stays in `cli.py` for the `struct.error` catch in `main()`.

- [ ] **Step 3: Update `tui.py` imports**

Change line 12 of `tui.py` from:
```python
from cli import format_value, read_registers, validate_write_value, write_register
```
to:
```python
from cli import format_value, validate_write_value
from modbus import read_registers, write_register
```

(Note: `format_value` and `validate_write_value` still live in `cli.py` at this point — they move in Task 4.)

- [ ] **Step 4: Update `tests/test_cli.py` imports**

Change the import block at lines 8-16 from:
```python
from cli import (
    build_table,
    filter_changed,
    filter_registers,
    format_value,
    read_registers,
    validate_write_value,
    write_register,
)
```
to:
```python
from cli import (
    build_table,
    filter_changed,
    filter_registers,
    format_value,
    validate_write_value,
)
from modbus import read_registers, write_register
```

- [ ] **Step 5: Run tests and lint**

```bash
uv run pytest -v
uvx ruff check .
```

Expected: All 117+ tests pass. Ruff clean.

- [ ] **Step 6: Commit**

```bash
git add modbus.py cli.py tui.py tests/test_cli.py
git commit -m "refactor: extract Modbus I/O into modbus.py"
```

---

## Chunk 3: Move register logic and use `parse_address_range`

### Task 4: Move `format_value`, `validate_write_value`, `filter_changed` to `registers.py`

**Files:**
- Modify: `registers.py` (add functions)
- Modify: `cli.py` (remove functions, update imports)
- Modify: `tui.py:12` (update imports)
- Modify: `tests/test_cli.py` (update imports)

- [ ] **Step 1: Move functions to `registers.py`**

Add these three functions to `registers.py`, after `parse_address_range` and before the end of file. They are copied verbatim from `cli.py` except `validate_write_value` now references `value_range` instead of `range`:

```python
def format_value(raw: int, scale: int) -> str:
    """Convert a raw register integer to a display string.

    scale=1 → integer string; scale>1 → decimal with appropriate precision.
    """
    if scale == 1:
        return str(raw)
    return str(round(raw / scale, max(0, len(str(scale)) - 1)))


def validate_write_value(reg: Register | StringRegister, input_str: str) -> int | str:
    """Parse and validate a human-readable display value for writing to reg.

    For Register: parses as float, checks device range, multiplies by scale,
    rounds to int, validates type bounds. Returns raw int ready for write_register.
    For StringRegister: validates UTF-8 byte length. Returns input_str unchanged.
    Raises ValueError with a descriptive message on invalid input.
    """
    if isinstance(reg, StringRegister):
        try:
            encoded = input_str.encode(reg.encoding)
        except UnicodeEncodeError as e:
            raise ValueError(f"String contains unencodable characters: {e}") from e
        max_bytes = reg.register_count * 2
        if len(encoded) > max_bytes:
            raise ValueError(
                f"String too long: {len(encoded)} bytes, max {max_bytes}"
            )
        return input_str
    try:
        display_val = float(input_str)
    except ValueError:
        raise ValueError(f"Invalid number: {input_str!r}") from None
    if reg.value_range is not None:
        lo, hi = reg.value_range
        if not (lo <= display_val <= hi):
            raise ValueError(
                f"Value out of range: {display_val} is not between {lo} and {hi}"
            )
    raw = round(display_val * reg.scale)
    if reg.data_type == "uint16":
        if not (0 <= raw <= 65535):
            raise ValueError(
                f"Value out of range for uint16 (0–65535 raw, got {raw})"
            )
    elif not (-32768 <= raw <= 32767):
        raise ValueError(
            f"Value out of range for int16 (-32768–32767 raw, got {raw})"
        )
    return raw


def filter_changed(
    registers: Sequence[Register | StringRegister],
    values: dict[int, int | str | None],
) -> list[Register | StringRegister]:
    """Return only registers whose live value differs from their factory default.

    Excludes: StringRegister entries, registers with no default (default=None),
    registers whose value is None (read error).
    """
    return [
        reg for reg in registers
        if isinstance(reg, Register)
        and reg.default is not None
        and (raw := values.get(reg.address)) is not None
        and raw != reg.default
    ]
```

Also add the required imports at the top of `registers.py`:
```python
from __future__ import annotations

from typing import TYPE_CHECKING
```
and:
```python
if TYPE_CHECKING:
    from collections.abc import Sequence
```

- [ ] **Step 2: Remove moved functions from `cli.py`**

Remove from `cli.py` (note: line numbers are from the **original** file before Task 3's changes — locate by function name, not line number):
- `format_value`
- `validate_write_value`
- `filter_changed`

Update `cli.py` imports — add to the `from registers import` line:
```python
from registers import ALL_REGISTERS, Register, StringRegister, format_value, validate_write_value, filter_changed
```

Remove the now-redundant definitions. `filter_registers` stays in `cli.py`.

- [ ] **Step 3: Update `tui.py` imports**

Change the imports from:
```python
from cli import format_value, validate_write_value
from modbus import read_registers, write_register
```
to:
```python
from modbus import read_registers, write_register
from registers import format_value, validate_write_value
```

- [ ] **Step 4: Update `tests/test_cli.py` imports**

Change:
```python
from cli import (
    build_table,
    filter_changed,
    filter_registers,
    format_value,
    validate_write_value,
)
from modbus import read_registers, write_register
```
to:
```python
from cli import build_table, filter_registers
from modbus import read_registers, write_register
from registers import filter_changed, format_value, validate_write_value
```

**Important:** The `monkeypatch.setattr(cli, "filter_changed", spy)` calls in `test_cli.py` (in `test_changed_flag_calls_filter_changed`, `test_read_and_changed_flags`, and `test_changed_with_write_ignored`) must **remain targeting `cli`**, not `registers`. After the move, `cli.py` imports `filter_changed` from `registers` and binds it in its own namespace — `cli.main()` resolves the name from `cli`'s namespace at call time, so the monkeypatch intercepts correctly.

- [ ] **Step 5: Run tests and lint**

```bash
uv run pytest -v
uvx ruff check .
```

Expected: All tests pass. Ruff clean.

- [ ] **Step 6: Commit**

```bash
git add registers.py cli.py tui.py tests/test_cli.py
git commit -m "refactor: move format_value, validate_write_value, filter_changed to registers.py"
```

---

### Task 5: Use `parse_address_range` in `cli.py`

**Files:**
- Modify: `cli.py` (replace duplicated parsing in `_handle_scan` and `main`)

- [ ] **Step 1: Update `cli.py` imports**

Add `parse_address_range` to the `from registers import` line in `cli.py`.

- [ ] **Step 2: Replace duplicated parsing in `_handle_scan`**

In `_handle_scan`, replace the manual parsing:
```python
    parts = args.scan.split("-")
    if len(parts) != 2 or not all(p.strip().isdigit() for p in parts):
        console.print(
            f"[red]Invalid scan range '{args.scan}'. "
            f"Format: START-END (e.g. 5000-5200)[/red]"
        )
        sys.exit(1)
    start, end = int(parts[0]), int(parts[1])
```
with:
```python
    try:
        start, end = parse_address_range(args.scan)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        sys.exit(1)
```

Keep the `start > end` check that follows — `parse_address_range` doesn't validate ordering.

- [ ] **Step 3: Replace duplicated parsing in `main`**

In `main`, replace the `--address` parsing:
```python
    if args.address is not None:
        parts = args.address.split("-")
        if len(parts) != 2 or not all(p.strip().isdigit() for p in parts):
            console.print(
                f"[red]Invalid address range '{args.address}'. "
                f"Format: START-END (e.g. 5000-5050)[/red]"
            )
            sys.exit(1)
        address_range = (int(parts[0]), int(parts[1]))
```
with:
```python
    if args.address is not None:
        try:
            address_range = parse_address_range(args.address)
        except ValueError as e:
            console.print(f"[red]{e}[/red]")
            sys.exit(1)
```

- [ ] **Step 4: Run tests and lint**

```bash
uv run pytest -v
uvx ruff check .
```

Expected: All tests pass. Ruff clean.

- [ ] **Step 5: Commit**

```bash
git add cli.py
git commit -m "refactor: use parse_address_range to deduplicate address parsing"
```

---

### Task 6: Final cleanup and verification

**Files:**
- Review: all source files for unused imports

- [ ] **Step 1: Check for unused imports in `cli.py`**

After all moves, verify `cli.py` still needs each import. In particular:
- `struct` — needed for `struct.error` catch in `main()`
- `Any` from `typing` — needed for `_handle_scan(args: Any, ...)` and `_handle_write(args: Any, ...)`
- `Sequence` from `collections.abc` — needed for `filter_registers`, `build_table`, `build_scan_table`

Run `uvx ruff check .` to catch any unused imports automatically.

- [ ] **Step 2: Run full test suite and lint**

```bash
uv run pytest -v
uvx ruff check .
```

Expected: All tests pass. Ruff clean.

- [ ] **Step 3: Commit any cleanup**

Only if Step 1 found unused imports to remove:
```bash
git add -u
git commit -m "refactor: remove unused imports after extraction"
```
