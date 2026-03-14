# Defaults Display Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "Default" column to the register table, highlight values that differ from factory defaults, and add a `--changed` flag to show only modified registers.

**Architecture:** Add an optional `default: int | None = None` field to the `Register` dataclass and populate 80 entries from the spec sheet. Update `build_table` to add a 5th column and yellow-highlight changed values. Add `filter_changed` for post-read filtering and wire it to a new `--changed` CLI flag.

**Tech Stack:** Python 3.12+, uv, pymodbus 3.12, rich, pytest

---

## Chunk 1: Register dataclass and defaults data

### Task 1: Add default field to Register and populate 80 entries

**Files:**
- Modify: `registers.py`
- Modify: `tests/test_registers.py`

- [ ] **Step 1: Write failing tests**

Add to the end of `tests/test_registers.py`:

```python
def test_register_default_is_none_by_default():
    reg = Register(5000, "Test", "uint16", 1, "")
    assert reg.default is None


def test_register_with_default():
    reg = Register(5000, "Test", "uint16", 1, "", default=6)
    assert reg.default == 6


def test_register_with_zero_default():
    reg = Register(5000, "Test", "uint16", 1, "", default=0)
    assert reg.default == 0  # 0 is valid, not None


def test_registers_with_defaults_count():
    count = sum(1 for r in REGISTERS if r.default is not None)
    assert count == 11


def test_new_registers_with_defaults_count():
    count = sum(1 for r in _NEW_REGISTERS if r.default is not None)
    assert count == 69
```

Also update the import line at the top of `tests/test_registers.py` to add `_NEW_REGISTERS`:

```python
from registers import REGISTERS, Register, StringRegister, STRING_REGISTERS, ALL_REGISTERS, _NEW_REGISTERS
```

- [ ] **Step 2: Run to confirm failure**

```bash
uv run pytest tests/test_registers.py -v -k "default"
```

Expected: `ImportError` for `_NEW_REGISTERS` (it exists but isn't exported publicly) or `AttributeError` — `Register` has no `default` attribute.

- [ ] **Step 3: Add `default` field to `Register`**

In `registers.py`, update the `Register` dataclass. The `__post_init__` must be preserved unchanged:

```python
@dataclass(frozen=True)
class Register:
    address: int
    name: str
    data_type: Literal["uint16", "int16"]
    scale: int      # divide raw value by this to get real value; must be > 0
    unit: str       # display unit string
    default: int | None = None  # factory default (None = no default in spec)

    def __post_init__(self) -> None:
        if self.scale <= 0:
            raise ValueError(f"scale must be > 0, got {self.scale!r}")
```

- [ ] **Step 4: Run dataclass tests**

```bash
uv run pytest tests/test_registers.py -v -k "default"
```

Expected: `test_register_default_is_none_by_default`, `test_register_with_default`, `test_register_with_zero_default` PASS; count tests still FAIL (0 ≠ 11, 0 ≠ 69).

- [ ] **Step 5: Add defaults to REGISTERS**

Replace the `REGISTERS` list in `registers.py` with this (11 entries gain `default=`; 22 entries are unchanged):

```python
REGISTERS = [
    Register(5000, "Product ID",                  "uint16", 1,   ""),
    Register(5007, "FW version H",                "uint16", 1,   ""),
    Register(5008, "FW version L",                "uint16", 1,   ""),
    Register(5009, "Charge mode",                 "uint16", 1,   "",        default=0),
    Register(5010, "Start/stop charging",         "uint16", 1,   ""),
    Register(5011, "L1 power used",               "uint16", 1,   "W"),
    Register(5012, "L2 power used",               "uint16", 1,   "W"),
    Register(5013, "L3 power used",               "uint16", 1,   "W"),
    Register(5014, "Total power",                 "uint16", 1,   "W"),
    Register(5015, "Charger status",              "uint16", 1,   ""),
    Register(5016, "Charging current",            "uint16", 1,   "A",       default=6),
    Register(5017, "Max current",                 "uint16", 1,   "A",       default=10),
    Register(5018, "Charging current actual",     "uint16", 10,  "A"),
    Register(5019, "Session charging time H",     "uint16", 1,   "s"),
    Register(5020, "Session charging time L",     "uint16", 1,   "s"),
    Register(5021, "Session energy",              "uint16", 100, "kWh"),
    Register(5022, "Session cost",                "uint16", 100, "currency"),
    Register(5023, "Total energy H",              "uint16", 1,   "kWh"),
    Register(5024, "Total energy L",              "uint16", 100, "kWh"),
    Register(5025, "CP voltage",                  "uint16", 100, "V"),
    Register(5026, "Charger position",            "uint16", 1,   "",        default=0),
    Register(5049, "Charger autostart",           "uint16", 1,   "",        default=1),
    Register(5050, "Control via display",         "uint16", 1,   "",        default=1),
    Register(5062, "Min current",                 "uint16", 1,   "A",       default=6),
    Register(5094, "EVCS errors L",               "uint16", 1,   "",        default=0),
    Register(5095, "EVCS errors H",               "uint16", 1,   "",        default=0),
    Register(5109, "Detected car phases",         "uint16", 1,   "",        default=1),
    Register(5111, "UP-time H",                   "uint16", 1,   "s"),
    Register(5112, "UP-time L",                   "uint16", 1,   "s"),
    Register(5113, "Reboot counter",              "uint16", 1,   ""),
    Register(5121, "Onboard humidity",            "uint16", 10,  "%"),
    Register(5122, "Onboard temperature",         "uint16", 10,  "°C"),
    Register(5127, "Power supply temperature",    "uint16", 10,  "°C",      default=0),
]
```

- [ ] **Step 6: Add defaults to _NEW_REGISTERS**

Replace the `_NEW_REGISTERS` list in `registers.py`. 69 of the 80 entries gain `default=`; 11 entries (5060, 5061, 5064, 5114, 5115, 5116, 5117, 5123, 5124, 5125, 5126) stay without a default. Note: int16 defaults are stored as signed Python ints (e.g. `-500`, not `65036`).

```python
_NEW_REGISTERS: list[Register] = [
    Register(5051, "Display active backlight",                                     "uint16", 1,   "%",    default=100),
    Register(5052, "Display idle backlight",                                       "uint16", 1,   "%",    default=7),
    Register(5053, "Display active timeout",                                       "uint16", 1,   "s",    default=120),
    Register(5054, "Contactor active when charged",                                "uint16", 1,   "",     default=0),
    Register(5055, "Manual mode phase",                                            "uint16", 1,   "",     default=1),
    Register(5056, "Auto mode phase",                                              "uint16", 1,   "",     default=1),
    Register(5057, "Power for 3phase",                                             "uint16", 1,   "W",    default=4800),
    Register(5058, "Power for single phase",                                       "uint16", 1,   "W",    default=4300),
    Register(5059, "Phase switching timeout",                                      "uint16", 1,   "s",    default=60),
    Register(5060, "CP Calibration command",                                       "uint16", 1,   ""),
    Register(5061, "CP Calibration status",                                        "uint16", 1,   ""),
    Register(5063, "Power calibration offset",                                     "uint16", 1,   "",     default=100),
    Register(5064, "EVCS reset",                                                   "uint16", 1,   ""),
    Register(5065, "Auto mode type",                                               "uint16", 1,   "",     default=1),
    Register(5066, "Backup battery SOC for start charging in Battery powered",     "uint16", 1,   "%",    default=90),
    Register(5067, "Backup battery min SOC to allow charging if OFF Grid",         "uint16", 1,   "%",    default=20),
    Register(5068, "Backup battery emulation",                                     "uint16", 1,   "",     default=0),
    Register(5069, "'Feed in'. Start delay",                                       "uint16", 1,   "s",    default=30),
    Register(5070, "'Feed in'. Stop delay",                                        "uint16", 1,   "s",    default=60),
    Register(5071, "'Feed in'. Single phase. Grid power for start",                "int16",  1,   "W",    default=-500),
    Register(5072, "'Feed in'. Multi phase. Grid power for start",                 "int16",  1,   "W",    default=-1400),
    Register(5073, "'Feed in'. Grid power threshold for increase",                 "int16",  1,   "W",    default=-250),
    Register(5074, "'Feed in'. Grid power threshold for decrease",                 "int16",  1,   "W",    default=250),
    Register(5075, "'Feed in'. Backup battery discharging power threshold",        "int16",  1,   "W",    default=-100),
    Register(5076, "'Feed in'. Current step",                                      "uint16", 10,  "A",    default=2),
    Register(5077, "'Feed in'. Time step",                                         "uint16", 1,   "ms",   default=1000),
    Register(5078, "'Battery powered'. Start delay min",                           "uint16", 1,   "s",    default=30),
    Register(5079, "'Battery powered'. Stop delay",                                "uint16", 1,   "s",    default=60),
    Register(5080, "'Battery powered'. Start abort delay",                         "uint16", 1,   "s",    default=10),
    Register(5081, "'Battery powered'. BKPB balance power",                        "uint16", 1,   "W",    default=500),
    Register(5082, "'Battery powered'. BKPB balance SOC max",                      "uint16", 1,   "%",    default=80),
    Register(5083, "'Battery powered'. Available sun power threshold for start",   "uint16", 1,   "W",    default=100),
    Register(5084, "'Battery powered'. Grid power threshold for start",            "uint16", 1,   "W",    default=25),
    Register(5085, "'Battery powered'. BKPB power threshold for decrease",         "uint16", 1,   "W",    default=400),
    Register(5086, "'Battery powered'. Grid power threshold for decrease",         "uint16", 1,   "W",    default=400),
    Register(5087, "'Battery powered'. Discharging detect timeout",                "uint16", 1,   "s",    default=7),
    Register(5088, "'Battery powered'. Next try timeout for increase",             "uint16", 1,   "s",    default=45),
    Register(5089, "'Battery powered'. Time step",                                 "uint16", 1,   "s",    default=15),
    Register(5090, "'Battery powered'. Current step",                              "uint16", 10,  "A",    default=10),
    Register(5091, "'Battery powered'. Grid power for 'feed in' detection",        "int16",  1,   "W",    default=-1500),
    Register(5092, "'Battery powered'. Start delay max",                           "uint16", 1,   "s",    default=300),
    Register(5093, "ON grid detection threshold",                                  "uint16", 1,   "W",    default=0),
    Register(5096, "EVCS warnings L",                                              "uint16", 1,   "",     default=0),
    Register(5097, "EVCS warnings H",                                              "uint16", 1,   "",     default=0),
    Register(5098, "EVCS notification code",                                       "uint16", 1,   "",     default=0),
    Register(5099, "External lock",                                                "uint16", 1,   "",     default=0),
    Register(5100, "Multiple relay charging",                                      "uint16", 1,   "",     default=0),
    Register(5101, "Multiple relay charging. Relays switching delay",              "uint16", 1,   "s",    default=10),
    Register(5102, "Allow battery/grid power for auto mode",                       "uint16", 1,   "",     default=0),
    Register(5103, "Battery/grid power timeout",                                   "uint16", 1,   "min",  default=30),
    Register(5104, "Overload protection",                                          "uint16", 1,   "",     default=0),
    Register(5105, "Input current limit",                                          "uint16", 10,  "A",    default=135),
    Register(5106, "Overload protection ON/OFF timeout",                           "uint16", 1,   "s",    default=10),
    Register(5107, "Overload protection cut-off timeout",                          "uint16", 1,   "s",    default=5),
    Register(5108, "Relays OFF delay",                                             "uint16", 1,   "ms",   default=2000),
    Register(5110, "Randomized delay max",                                         "uint16", 1,   "",     default=600),
    Register(5114, "Last reboot reason code",                                      "uint16", 1,   ""),
    Register(5115, "Sys watchdog reboot counter",                                  "uint16", 1,   ""),
    Register(5116, "Sys watchdog last reboot reason code",                         "uint16", 1,   ""),
    Register(5117, "Relays statuses",                                              "uint16", 1,   ""),
    Register(5118, "Overload current decrease timeout",                            "uint16", 1,   "min",  default=5),
    Register(5119, "Overload current decrease counter",                            "uint16", 1,   "",     default=1),
    Register(5120, "Overload current decrease rate",                               "uint16", 1,   "%",    default=20),
    Register(5123, "Display temperature",                                          "uint16", 10,  "°C"),
    Register(5124, "Car connector temperature",                                    "uint16", 10,  "°C"),
    Register(5125, "Power meter temperature",                                      "uint16", 10,  "°C"),
    Register(5126, "Power control temperature",                                    "uint16", 10,  "°C"),
    Register(5128, "Allow low excess solar power for auto mode",                   "uint16", 1,   "",     default=0),
    Register(5129, "Charging current limit external",                              "uint16", 1,   "",     default=0),
    Register(5130, "Inverter overtemperature protection",                          "uint16", 1,   "",     default=1),
    Register(5131, "Inverter overtemperature protection. Charging current restore timeout", "uint16", 1, "s", default=60),
    Register(5132, "Light ring brightness limit",                                  "uint16", 1,   "%",    default=100),
    Register(5133, "CP auto-calibration state",                                    "uint16", 1,   "",     default=1),
    Register(5134, "'Battery powered'. Low excess power threshold",                "uint16", 1,   "W",    default=500),
    Register(5135, "'Battery powered'. Emulated BKPB power",                      "int16",  1,   "W",    default=0),
    Register(5136, "'Battery powered'. Emulated BKPB SoC",                        "uint16", 1,   "%",    default=100),
    Register(5137, "'Battery powered'. 'feed in' detection",                       "uint16", 1,   "",     default=0),
    Register(5138, "'Battery powered'. BKPB SoC max",                             "uint16", 1,   "%",    default=99),
    Register(5139, "Multiple relay charging. Conditions check delay",              "uint16", 1,   "s",    default=10),
    Register(5140, "Online update feed",                                           "uint16", 1,   "",     default=0),
]
```

- [ ] **Step 7: Run all register tests**

```bash
uv run pytest tests/test_registers.py -v
```

Expected: all 18 tests PASS (13 existing + 5 new).

- [ ] **Step 8: Run full suite**

```bash
uv run pytest -v
```

Expected: all 35 tests PASS.

- [ ] **Step 9: Commit**

```bash
git add registers.py tests/test_registers.py
git commit -m "feat: add default field to Register and populate 80 factory defaults"
```

---

## Chunk 2: Reader changes

### Task 2: Update build_table, add filter_changed, add --changed flag

**Files:**
- Modify: `reader.py`
- Modify: `tests/test_reader.py`

- [ ] **Step 1: Write failing tests**

In `tests/test_reader.py`, update the two existing column-count assertions from `== 4` to `== 5`:

```python
# test_build_table_string_register: change assert len(table.columns) == 4
assert len(table.columns) == 5

# test_build_table_string_register_none: change assert len(table.columns) == 4
assert len(table.columns) == 5
```

Then add the following imports at the top (merge into existing imports):

```python
from reader import read_registers, build_table, format_value, filter_registers, filter_changed
```

Then add these new tests and fixtures after the existing tests:

```python
# --- build_table default column tests ---

def test_build_table_has_default_column():
    reg = Register(5016, "Charging current", "uint16", 1, "A", default=6)
    values = {5016: 10}
    table = build_table([reg], values)
    assert len(table.columns) == 5


def test_build_table_shows_formatted_default():
    reg = Register(5016, "Charging current", "uint16", 1, "A", default=6)
    values = {5016: 10}
    table = build_table([reg], values)
    # Value differs from default → yellow markup in value cell
    rendered = table.columns[2]._cells[0]  # Value column, first row
    assert "[yellow]" in rendered
    # Default column shows formatted default
    default_cell = table.columns[4]._cells[0]  # Default column, first row
    assert default_cell == "6"


def test_build_table_zero_default_shows_zero():
    reg = Register(5009, "Charge mode", "uint16", 1, "", default=0)
    values = {5009: 0}
    table = build_table([reg], values)
    default_cell = table.columns[4]._cells[0]
    assert default_cell == "0"
    value_cell = table.columns[2]._cells[0]
    assert "[yellow]" not in value_cell  # values match, no highlight


def test_build_table_no_default_shows_blank():
    reg = Register(5000, "Product ID", "uint16", 1, "")
    values = {5000: 49189}
    table = build_table([reg], values)
    default_cell = table.columns[4]._cells[0]
    assert default_cell == ""


def test_build_table_value_matches_default_no_highlight():
    reg = Register(5016, "Charging current", "uint16", 1, "A", default=6)
    values = {5016: 6}
    table = build_table([reg], values)
    value_cell = table.columns[2]._cells[0]
    assert "[yellow]" not in value_cell


# --- filter_changed tests ---

def test_filter_changed_returns_changed():
    reg = Register(5016, "Charging current", "uint16", 1, "A", default=6)
    result = filter_changed([reg], {5016: 10})
    assert reg in result


def test_filter_changed_excludes_matching():
    reg = Register(5016, "Charging current", "uint16", 1, "A", default=6)
    result = filter_changed([reg], {5016: 6})
    assert result == []


def test_filter_changed_excludes_no_default():
    reg = Register(5000, "Product ID", "uint16", 1, "")
    result = filter_changed([reg], {5000: 999})
    assert result == []


def test_filter_changed_excludes_error():
    reg = Register(5016, "Charging current", "uint16", 1, "A", default=6)
    result = filter_changed([reg], {5016: None})
    assert result == []


def test_filter_changed_excludes_string_registers():
    str_reg = StringRegister(5001, "Serial Id", 6)
    result = filter_changed([str_reg], {5001: "ABC123"})
    assert result == []


def test_changed_flag_calls_filter_changed(monkeypatch):
    """--changed flag causes filter_changed to be called in main()."""
    import reader

    calls = []
    orig = reader.filter_changed

    def spy(registers, values):
        calls.append(True)
        return orig(registers, values)

    monkeypatch.setattr(reader, "filter_changed", spy)

    mock_client = MagicMock()
    mock_client.connect.return_value = True
    response = MagicMock()
    response.isError.return_value = False
    response.registers = [0] * 200
    mock_client.read_holding_registers.return_value = response
    monkeypatch.setattr(reader, "ModbusTcpClient", lambda **kw: mock_client)

    import sys
    sys.argv = ["reader.py", "127.0.0.1", "--changed"]
    reader.main()

    assert calls, "filter_changed was not called when --changed flag is set"
```

- [ ] **Step 2: Run to confirm failures**

```bash
uv run pytest tests/test_reader.py -v -k "default or changed or filter_changed"
```

Expected: failures — `filter_changed` not importable, column count wrong, etc.

- [ ] **Step 3: Update reader.py**

Replace the full content of `reader.py` with:

```python
"""Victron EVCS Modbus TCP register reader."""
from __future__ import annotations

import argparse
import struct
import sys
from typing import Any, TYPE_CHECKING

from pymodbus.client import ModbusTcpClient
from rich.console import Console
from rich.table import Table

from registers import ALL_REGISTERS, Register, StringRegister

if TYPE_CHECKING:
    from collections.abc import Sequence


def format_value(raw: int, scale: int) -> str:
    # scale=1 → integer, scale>1 → decimal with appropriate precision
    if scale == 1:
        return str(raw)
    return str(round(raw / scale, max(0, len(str(scale)) - 1)))


def read_registers(
    client: Any, registers: Sequence[Register | StringRegister]
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
        addresses = sorted(r.address for r in scalar_regs)
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
                address=start_addr, count=count, device_id=1
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
                        reg = next(r for r in scalar_regs if r.address == addr)
                        if reg.data_type == "int16" and raw > 32767:
                            raw -= 65536
                    result[addr] = raw
            chunk_start = chunk_end + 1

    # Read string registers individually
    for reg in string_regs:
        response = client.read_holding_registers(
            address=reg.address, count=reg.register_count, device_id=1
        )
        if response.isError():
            result[reg.address] = None
        else:
            raw_bytes = struct.pack(f">{reg.register_count}H", *response.registers)
            result[reg.address] = raw_bytes.rstrip(b"\x00").decode(reg.encoding)

    return result


def build_table(
    registers: Sequence[Register | StringRegister],
    values: dict[int, int | str | None],
) -> Table:
    """Build a Rich table displaying register addresses, names, scaled values, units, and defaults."""
    table = Table(title="Victron EVCS Register Values", show_header=True)
    table.add_column("Address", style="cyan", justify="right")
    table.add_column("Name", style="white")
    table.add_column("Value", style="green", justify="right")
    table.add_column("Unit", style="yellow")
    table.add_column("Default", style="dim", justify="right")

    for reg in registers:
        raw = values.get(reg.address)
        if raw is None:
            value_str = "[red]error[/red]"
            unit_str = ""
            default_str = ""
        elif isinstance(reg, StringRegister):
            value_str = str(raw)
            unit_str = ""
            default_str = ""
        else:
            if reg.default is not None and raw != reg.default:
                value_str = f"[yellow]{format_value(raw, reg.scale)}[/yellow]"
            else:
                value_str = format_value(raw, reg.scale)
            unit_str = reg.unit
            default_str = format_value(reg.default, reg.scale) if reg.default is not None else ""
        table.add_row(str(reg.address), reg.name, value_str, unit_str, default_str)

    return table


def filter_registers(
    registers: Sequence[Register | StringRegister],
    *,
    category: str | None = None,
    address_range: tuple[int, int] | None = None,
    name: str | None = None,
) -> list[Register | StringRegister]:
    """Filter registers by category, address range, and/or name substring.

    Multiple filters combine as AND (intersection).
    Returns all registers if no filters specified.
    """
    from categories import CATEGORIES

    result = list(registers)

    if category is not None:
        if category not in CATEGORIES:
            raise ValueError(
                f"Unknown category {category!r}. "
                f"Available: {', '.join(sorted(CATEGORIES))}"
            )
        allowed = set(CATEGORIES[category])
        result = [r for r in result if r.address in allowed]

    if address_range is not None:
        start, end = address_range
        result = [r for r in result if start <= r.address <= end]

    if name is not None:
        name_lower = name.lower()
        result = [r for r in result if name_lower in r.name.lower()]

    return result


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
        and values.get(reg.address) is not None
        and values.get(reg.address) != reg.default
    ]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Read Victron EVCS registers over Modbus TCP"
    )
    parser.add_argument("host", help="IP address or hostname of the EVCS")
    parser.add_argument("--port", type=int, default=502, help="Modbus TCP port (default: 502)")
    parser.add_argument("--category", help="Filter by category (e.g. sensors, status, config)")
    parser.add_argument("--address", help="Filter by address range, e.g. 5000-5050")
    parser.add_argument("--name", help="Filter by name substring (case-insensitive)")
    parser.add_argument(
        "--changed",
        action="store_true",
        help="Show only registers that differ from their factory default",
    )
    args = parser.parse_args()

    console = Console()

    from categories import CATEGORIES

    if args.category is not None and args.category not in CATEGORIES:
        console.print(
            f"[red]Unknown category '{args.category}'. "
            f"Available: {', '.join(sorted(CATEGORIES))}[/red]"
        )
        sys.exit(1)

    address_range = None
    if args.address is not None:
        parts = args.address.split("-")
        if len(parts) != 2 or not all(p.strip().isdigit() for p in parts):
            console.print(
                f"[red]Invalid address range '{args.address}'. "
                f"Format: START-END (e.g. 5000-5050)[/red]"
            )
            sys.exit(1)
        address_range = (int(parts[0]), int(parts[1]))

    registers = filter_registers(
        ALL_REGISTERS,
        category=args.category,
        address_range=address_range,
        name=args.name,
    )

    client = ModbusTcpClient(host=args.host, port=args.port)
    if not client.connect():
        console.print(f"[red]Failed to connect to {args.host}:{args.port}[/red]")
        sys.exit(1)

    try:
        values = read_registers(client, registers)
    finally:
        client.close()

    registers_to_display = filter_changed(registers, values) if args.changed else registers
    table = build_table(registers_to_display, values)
    console.print(table)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run new tests**

```bash
uv run pytest tests/test_reader.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Run full suite**

```bash
uv run pytest -v
```

Expected: all 51 tests PASS (35 existing + 5 register tests + 2 updated + 11 new reader tests = 51 - wait, let me count: 35 existing + 5 new register tests = 40, then 2 existing updated + 11 new reader tests added = 46 total reader tests from 16 + 11 new = 27. So total = 13 registers + 6 categories + 27 reader = 46 tests).

> Note on exact test count: existing total is 35 (13 register + 6 category + 16 reader). Adding 5 register tests → 18 register. Adding 11 reader tests → 27 reader. Total: 18 + 6 + 27 = **51 tests**.

- [ ] **Step 6: Commit**

```bash
git add reader.py tests/test_reader.py
git commit -m "feat: add Default column, highlight changed values, add --changed flag"
```

---

### Task 3: Smoke test

**Files:** none

- [ ] **Step 1: Verify --changed appears in help**

```bash
uv run python reader.py --help
```

Expected output includes `--changed`.

- [ ] **Step 2: Smoke test against live device (optional, skip if device unreachable)**

```bash
# See all registers with defaults column
uv run python reader.py 192.168.0.128

# See only registers that differ from factory defaults
uv run python reader.py 192.168.0.128 --changed

# Combined: changed auto_mode registers only
uv run python reader.py 192.168.0.128 --changed --category auto_mode
```

- [ ] **Step 3: Push**

```bash
git pull --rebase
git push
```
