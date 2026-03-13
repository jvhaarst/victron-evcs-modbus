# Full Register Support Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the EVCS Modbus reader to cover all 115 holding registers, with string register support, signed int16 handling, and CLI filtering by category, address range, and name.

**Architecture:** `registers.py` gains `StringRegister`, 80 new scalar entries, and `ALL_REGISTERS`. A new `categories.py` maps category names to address lists. `reader.py` is extended with int16 sign conversion, individual string reads, a `filter_registers` function, and three new CLI arguments (`--category`, `--address`, `--name`).

**Tech Stack:** Python 3.12+, uv, pymodbus 3.12, rich, pytest, struct (stdlib)

---

## Chunk 1: Extend registers.py

### Task 1: Add StringRegister dataclass and string registers

**Files:**
- Modify: `registers.py`
- Modify: `tests/test_registers.py`

- [ ] **Step 1: Write failing tests**

**Replace** the existing `from registers import REGISTERS, Register` line at the top of `tests/test_registers.py` with:

```python
from registers import REGISTERS, Register, StringRegister, STRING_REGISTERS, ALL_REGISTERS


def test_string_register_fields():
    reg = StringRegister(5001, "Serial Id", 6)
    assert reg.address == 5001
    assert reg.name == "Serial Id"
    assert reg.register_count == 6
    assert reg.encoding == "utf-8"


def test_string_register_custom_encoding():
    reg = StringRegister(5001, "Test", 6, encoding="ascii")
    assert reg.encoding == "ascii"


def test_string_registers_list():
    assert len(STRING_REGISTERS) == 2
    addrs = [r.address for r in STRING_REGISTERS]
    assert 5001 in addrs  # Serial Id
    assert 5027 in addrs  # Device name


def test_all_registers_count():
    assert len(ALL_REGISTERS) == 115


def test_no_duplicate_addresses_across_all():
    addrs = [r.address for r in ALL_REGISTERS]
    assert len(addrs) == len(set(addrs))
```

- [ ] **Step 2: Run to confirm failure**

```bash
uv run pytest tests/test_registers.py -v -k "string_register or all_registers or duplicate_addresses_across"
```

Expected: `ImportError` — `StringRegister` not yet defined.

- [ ] **Step 3: Add StringRegister, STRING_REGISTERS, ALL_REGISTERS to registers.py**

Add after the existing `REGISTERS` list:

```python
@dataclass(frozen=True)
class StringRegister:
    address: int          # start address
    name: str
    register_count: int   # number of Modbus registers (each holds 2 bytes)
    encoding: str = "utf-8"


STRING_REGISTERS: list[StringRegister] = [
    StringRegister(5001, "Serial Id",    6),   # 6 regs, 12 chars
    StringRegister(5027, "Device name", 22),   # 22 regs, 44 bytes UTF-8
]

ALL_REGISTERS: list[Register | StringRegister] = (
    [REGISTERS[0]]                    # 5000
    + STRING_REGISTERS[:1]            # 5001 (Serial Id)
    + REGISTERS[1:21]                 # 5007-5026 (indices 1-20, i.e. REGISTERS[1] is 5007, REGISTERS[20] is 5026)
    + STRING_REGISTERS[1:]            # 5027 (Device name)
    + REGISTERS[21:]                  # 5049 onwards (index 21 = address 5049)
    # new scalar registers inserted below in Task 2
)
```

> **Note:** `ALL_REGISTERS` will be rebuilt in Task 2 once the 80 new scalar registers are added. This intermediate version is just to make the dataclass/string tests pass now.

- [ ] **Step 4: Run to confirm tests pass**

```bash
uv run pytest tests/test_registers.py -v -k "string_register or string_registers_list"
```

Expected: 3 tests PASS. (`all_registers_count` will still fail — fixed in Task 2.)

- [ ] **Step 5: Commit**

```bash
git add registers.py tests/test_registers.py
git commit -m "feat: add StringRegister dataclass and string register entries"
```

---

### Task 2: Add 80 new scalar registers and finalize ALL_REGISTERS

**Files:**
- Modify: `registers.py`

- [ ] **Step 1: Replace ALL_REGISTERS with the complete ordered list**

Replace the interim `ALL_REGISTERS` definition added in Task 1 with the following. This inserts the 80 new scalar registers in address order and interleaves the string registers at their correct positions (5001 and 5027).

First, add the 80 new `Register` entries to `registers.py` as a new list `_NEW_REGISTERS`. Insert it **immediately after the `STRING_REGISTERS` definition and before `ALL_REGISTERS`**:

```python
_NEW_REGISTERS: list[Register] = [
    Register(5051, "Display active backlight",                                     "uint16", 1,   "%"),
    Register(5052, "Display idle backlight",                                       "uint16", 1,   "%"),
    Register(5053, "Display active timeout",                                       "uint16", 1,   "s"),
    Register(5054, "Contactor active when charged",                                "uint16", 1,   ""),
    Register(5055, "Manual mode phase",                                            "uint16", 1,   ""),
    Register(5056, "Auto mode phase",                                              "uint16", 1,   ""),
    Register(5057, "Power for 3phase",                                             "uint16", 1,   "W"),
    Register(5058, "Power for single phase",                                       "uint16", 1,   "W"),
    Register(5059, "Phase switching timeout",                                      "uint16", 1,   "s"),
    Register(5060, "CP Calibration command",                                       "uint16", 1,   ""),
    Register(5061, "CP Calibration status",                                        "uint16", 1,   ""),
    Register(5063, "Power calibration offset",                                     "uint16", 1,   ""),
    Register(5064, "EVCS reset",                                                   "uint16", 1,   ""),
    Register(5065, "Auto mode type",                                               "uint16", 1,   ""),
    Register(5066, "Backup battery SOC for start charging in Battery powered",     "uint16", 1,   "%"),
    Register(5067, "Backup battery min SOC to allow charging if OFF Grid",         "uint16", 1,   "%"),
    Register(5068, "Backup battery emulation",                                     "uint16", 1,   ""),
    Register(5069, "'Feed in'. Start delay",                                       "uint16", 1,   "s"),
    Register(5070, "'Feed in'. Stop delay",                                        "uint16", 1,   "s"),
    Register(5071, "'Feed in'. Single phase. Grid power for start",                "int16",  1,   "W"),
    Register(5072, "'Feed in'. Multi phase. Grid power for start",                 "int16",  1,   "W"),
    Register(5073, "'Feed in'. Grid power threshold for increase",                 "int16",  1,   "W"),
    Register(5074, "'Feed in'. Grid power threshold for decrease",                 "int16",  1,   "W"),
    Register(5075, "'Feed in'. Backup battery discharging power threshold",        "int16",  1,   "W"),
    Register(5076, "'Feed in'. Current step",                                      "uint16", 10,  "A"),
    Register(5077, "'Feed in'. Time step",                                         "uint16", 1,   "ms"),
    Register(5078, "'Battery powered'. Start delay min",                           "uint16", 1,   "s"),
    Register(5079, "'Battery powered'. Stop delay",                                "uint16", 1,   "s"),
    Register(5080, "'Battery powered'. Start abort delay",                         "uint16", 1,   "s"),
    Register(5081, "'Battery powered'. BKPB balance power",                        "uint16", 1,   "W"),
    Register(5082, "'Battery powered'. BKPB balance SOC max",                      "uint16", 1,   "%"),
    Register(5083, "'Battery powered'. Available sun power threshold for start",   "uint16", 1,   "W"),
    Register(5084, "'Battery powered'. Grid power threshold for start",            "uint16", 1,   "W"),
    Register(5085, "'Battery powered'. BKPB power threshold for decrease",         "uint16", 1,   "W"),
    Register(5086, "'Battery powered'. Grid power threshold for decrease",         "uint16", 1,   "W"),
    Register(5087, "'Battery powered'. Discharging detect timeout",                "uint16", 1,   "s"),
    Register(5088, "'Battery powered'. Next try timeout for increase",             "uint16", 1,   "s"),
    Register(5089, "'Battery powered'. Time step",                                 "uint16", 1,   "s"),
    Register(5090, "'Battery powered'. Current step",                              "uint16", 10,  "A"),
    Register(5091, "'Battery powered'. Grid power for 'feed in' detection",        "int16",  1,   "W"),
    Register(5092, "'Battery powered'. Start delay max",                           "uint16", 1,   "s"),
    Register(5093, "ON grid detection threshold",                                  "uint16", 1,   "W"),
    Register(5096, "EVCS warnings L",                                              "uint16", 1,   ""),
    Register(5097, "EVCS warnings H",                                              "uint16", 1,   ""),
    Register(5098, "EVCS notification code",                                       "uint16", 1,   ""),
    Register(5099, "External lock",                                                "uint16", 1,   ""),
    Register(5100, "Multiple relay charging",                                      "uint16", 1,   ""),
    Register(5101, "Multiple relay charging. Relays switching delay",              "uint16", 1,   "s"),
    Register(5102, "Allow battery/grid power for auto mode",                       "uint16", 1,   ""),
    Register(5103, "Battery/grid power timeout",                                   "uint16", 1,   "min"),
    Register(5104, "Overload protection",                                          "uint16", 1,   ""),
    Register(5105, "Input current limit",                                          "uint16", 10,  "A"),
    Register(5106, "Overload protection ON/OFF timeout",                           "uint16", 1,   "s"),
    Register(5107, "Overload protection cut-off timeout",                          "uint16", 1,   "s"),
    Register(5108, "Relays OFF delay",                                             "uint16", 1,   "ms"),
    Register(5110, "Randomized delay max",                                         "uint16", 1,   ""),
    Register(5114, "Last reboot reason code",                                      "uint16", 1,   ""),
    Register(5115, "Sys watchdog reboot counter",                                  "uint16", 1,   ""),
    Register(5116, "Sys watchdog last reboot reason code",                         "uint16", 1,   ""),
    Register(5117, "Relays statuses",                                              "uint16", 1,   ""),
    Register(5118, "Overload current decrease timeout",                            "uint16", 1,   "min"),
    Register(5119, "Overload current decrease counter",                            "uint16", 1,   ""),
    Register(5120, "Overload current decrease rate",                               "uint16", 1,   "%"),
    Register(5123, "Display temperature",                                          "uint16", 10,  "°C"),
    Register(5124, "Car connector temperature",                                    "uint16", 10,  "°C"),
    Register(5125, "Power meter temperature",                                      "uint16", 10,  "°C"),
    Register(5126, "Power control temperature",                                    "uint16", 10,  "°C"),
    Register(5128, "Allow low excess solar power for auto mode",                   "uint16", 1,   ""),
    Register(5129, "Charging current limit external",                              "uint16", 1,   ""),
    Register(5130, "Inverter overtemperature protection",                          "uint16", 1,   ""),
    Register(5131, "Inverter overtemperature protection. Charging current restore timeout", "uint16", 1, "s"),
    Register(5132, "Light ring brightness limit",                                  "uint16", 1,   "%"),
    Register(5133, "CP auto-calibration state",                                    "uint16", 1,   ""),
    Register(5134, "'Battery powered'. Low excess power threshold",                "uint16", 1,   "W"),
    Register(5135, "'Battery powered'. Emulated BKPB power",                      "int16",  1,   "W"),
    Register(5136, "'Battery powered'. Emulated BKPB SoC",                        "uint16", 1,   "%"),
    Register(5137, "'Battery powered'. 'feed in' detection",                       "uint16", 1,   ""),
    Register(5138, "'Battery powered'. BKPB SoC max",                             "uint16", 1,   "%"),
    Register(5139, "Multiple relay charging. Conditions check delay",              "uint16", 1,   "s"),
    Register(5140, "Online update feed",                                           "uint16", 1,   ""),
]
```

Then replace the interim `ALL_REGISTERS` with the final sorted version:

```python
ALL_REGISTERS: list[Register | StringRegister] = sorted(
    list(REGISTERS) + list(_NEW_REGISTERS) + list(STRING_REGISTERS),
    key=lambda r: r.address,
)
```

- [ ] **Step 2: Run all register tests**

```bash
uv run pytest tests/test_registers.py -v
```

Expected: all tests PASS including `test_all_registers_count` (115 entries) and `test_no_duplicate_addresses_across_all`.

- [ ] **Step 3: Commit**

```bash
git add registers.py
git commit -m "feat: add 80 new scalar registers and finalize ALL_REGISTERS"
```

---

## Chunk 2: Categories

### Task 3: Create categories.py

**Files:**
- Create: `categories.py`
- Create: `tests/test_categories.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_categories.py`:

```python
from categories import CATEGORIES
from registers import ALL_REGISTERS

_ALL_ADDRESSES = {r.address for r in ALL_REGISTERS}
_VALID_CATEGORIES = {"status", "session", "device", "config", "auto_mode", "sensors", "diagnostics"}


def test_categories_has_expected_keys():
    assert set(CATEGORIES.keys()) == _VALID_CATEGORIES


def test_all_category_addresses_exist_in_all_registers():
    for cat, addresses in CATEGORIES.items():
        for addr in addresses:
            assert addr in _ALL_ADDRESSES, f"Category '{cat}' has address {addr} not in ALL_REGISTERS"


def test_sensors_contains_humidity():
    assert 5121 in CATEGORIES["sensors"]


def test_sensors_contains_all_temperatures():
    for addr in [5122, 5123, 5124, 5125, 5126, 5127]:
        assert addr in CATEGORIES["sensors"], f"Address {addr} not in sensors category"


def test_status_contains_charger_status():
    assert 5015 in CATEGORIES["status"]


def test_no_empty_categories():
    for cat, addresses in CATEGORIES.items():
        assert len(addresses) > 0, f"Category '{cat}' is empty"
```

- [ ] **Step 2: Run to confirm failure**

```bash
uv run pytest tests/test_categories.py -v
```

Expected: `ImportError` — `categories.py` doesn't exist yet.

- [ ] **Step 3: Create categories.py**

```python
"""Category definitions for Victron EVCS holding registers.

Maps category names to lists of register addresses. Registers may appear
in multiple categories. Categories are separate from register definitions.
"""

CATEGORIES: dict[str, list[int]] = {
    "status": [
        5009,  # Charge mode
        5010,  # Start/stop charging
        5011,  # L1 power used
        5012,  # L2 power used
        5013,  # L3 power used
        5014,  # Total power
        5015,  # Charger status
        5016,  # Charging current
        5017,  # Max current
        5018,  # Charging current actual
        5094,  # EVCS errors L
        5095,  # EVCS errors H
        5096,  # EVCS warnings L
        5097,  # EVCS warnings H
        5098,  # EVCS notification code
        5099,  # External lock
        5109,  # Detected car phases
        5117,  # Relays statuses
    ],
    "session": [
        5019,  # Session charging time H
        5020,  # Session charging time L
        5021,  # Session energy
        5022,  # Session cost
        5023,  # Total energy H
        5024,  # Total energy L
    ],
    "device": [
        5000,  # Product ID
        5001,  # Serial Id
        5007,  # FW version H
        5008,  # FW version L
        5027,  # Device name
        5049,  # Charger autostart
        5050,  # Control via display
        5051,  # Display active backlight
        5052,  # Display idle backlight
        5053,  # Display active timeout
        5113,  # Reboot counter
        5114,  # Last reboot reason code
        5132,  # Light ring brightness limit
        5140,  # Online update feed
    ],
    "config": [
        5026,  # Charger position
        5054,  # Contactor active when charged
        5055,  # Manual mode phase
        5056,  # Auto mode phase
        5057,  # Power for 3phase
        5058,  # Power for single phase
        5059,  # Phase switching timeout
        5062,  # Min current
        5063,  # Power calibration offset
        5064,  # EVCS reset
        5065,  # Auto mode type
        5099,  # External lock
        5100,  # Multiple relay charging
        5101,  # Multiple relay charging. Relays switching delay
        5102,  # Allow battery/grid power for auto mode
        5103,  # Battery/grid power timeout
        5104,  # Overload protection
        5105,  # Input current limit
        5106,  # Overload protection ON/OFF timeout
        5107,  # Overload protection cut-off timeout
        5108,  # Relays OFF delay
        5110,  # Randomized delay max
        5128,  # Allow low excess solar power for auto mode
        5129,  # Charging current limit external
        5130,  # Inverter overtemperature protection
        5131,  # Inverter overtemperature protection. Charging current restore timeout
        5133,  # CP auto-calibration state
        5139,  # Multiple relay charging. Conditions check delay
    ],
    "auto_mode": [
        5065,  # Auto mode type
        5066,  # Backup battery SOC for start charging in Battery powered
        5067,  # Backup battery min SOC to allow charging if OFF Grid
        5068,  # Backup battery emulation
        5069,  # 'Feed in'. Start delay
        5070,  # 'Feed in'. Stop delay
        5071,  # 'Feed in'. Single phase. Grid power for start
        5072,  # 'Feed in'. Multi phase. Grid power for start
        5073,  # 'Feed in'. Grid power threshold for increase
        5074,  # 'Feed in'. Grid power threshold for decrease
        5075,  # 'Feed in'. Backup battery discharging power threshold
        5076,  # 'Feed in'. Current step
        5077,  # 'Feed in'. Time step
        5078,  # 'Battery powered'. Start delay min
        5079,  # 'Battery powered'. Stop delay
        5080,  # 'Battery powered'. Start abort delay
        5081,  # 'Battery powered'. BKPB balance power
        5082,  # 'Battery powered'. BKPB balance SOC max
        5083,  # 'Battery powered'. Available sun power threshold for start
        5084,  # 'Battery powered'. Grid power threshold for start
        5085,  # 'Battery powered'. BKPB power threshold for decrease
        5086,  # 'Battery powered'. Grid power threshold for decrease
        5087,  # 'Battery powered'. Discharging detect timeout
        5088,  # 'Battery powered'. Next try timeout for increase
        5089,  # 'Battery powered'. Time step
        5090,  # 'Battery powered'. Current step
        5091,  # 'Battery powered'. Grid power for 'feed in' detection
        5092,  # 'Battery powered'. Start delay max
        5093,  # ON grid detection threshold
        5134,  # 'Battery powered'. Low excess power threshold
        5135,  # 'Battery powered'. Emulated BKPB power
        5136,  # 'Battery powered'. Emulated BKPB SoC
        5137,  # 'Battery powered'. 'feed in' detection
        5138,  # 'Battery powered'. BKPB SoC max
    ],
    "sensors": [
        5121,  # Onboard humidity
        5122,  # Onboard temperature
        5123,  # Display temperature
        5124,  # Car connector temperature
        5125,  # Power meter temperature
        5126,  # Power control temperature
        5127,  # Power supply temperature
    ],
    "diagnostics": [
        5025,  # CP voltage
        5060,  # CP Calibration command
        5061,  # CP Calibration status
        5111,  # UP-time H
        5112,  # UP-time L
        5113,  # Reboot counter
        5114,  # Last reboot reason code
        5115,  # Sys watchdog reboot counter
        5116,  # Sys watchdog last reboot reason code
        5117,  # Relays statuses
        5118,  # Overload current decrease timeout
        5119,  # Overload current decrease counter
        5120,  # Overload current decrease rate
    ],
}
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_categories.py -v
```

Expected: all 6 tests PASS.

- [ ] **Step 5: Run full suite**

```bash
uv run pytest -v
```

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add categories.py tests/test_categories.py
git commit -m "feat: add categories module with 7 register categories"
```

---

## Chunk 3: Reader updates and CLI

### Task 4: Update reader.py — int16, string reads, build_table

**Files:**
- Modify: `reader.py`
- Modify: `tests/test_reader.py`

- [ ] **Step 1: Write failing tests for new reader behaviour**

Add to `tests/test_reader.py`:

```python
import struct
from registers import Register, StringRegister
from reader import read_registers, build_table, format_value


def test_int16_sign_conversion(mock_modbus_client_signed):
    # Use a minimal register list with just one int16 register
    int16_reg = Register(5071, "Test int16", "int16", 1, "W")
    result = read_registers(mock_modbus_client_signed, [int16_reg])
    assert result[5071] == -500


def test_string_register_decode(mock_modbus_client_string):
    str_reg = StringRegister(5001, "Serial Id", 6)
    result = read_registers(mock_modbus_client_string, [str_reg])
    assert result[5001] == "MyDevice"


def test_build_table_string_register():
    str_reg = StringRegister(5001, "Serial Id", 6)
    values = {5001: "ABC123"}
    table = build_table([str_reg], values)
    # Table should render without error and have 4 columns
    assert table.column_count == 4


def test_build_table_string_register_none():
    str_reg = StringRegister(5001, "Serial Id", 6)
    values = {5001: None}
    table = build_table([str_reg], values)
    assert table.column_count == 4


@pytest.fixture
def mock_modbus_client_signed():
    """Returns raw value 65036 for address 5071 (= -500 as int16)."""
    client = MagicMock()
    response = MagicMock()
    response.isError.return_value = False
    # Single register at 5071 with raw value 65036
    response.registers = [65036]
    client.read_holding_registers.return_value = response
    return client


@pytest.fixture
def mock_modbus_client_string():
    """Returns uint16 words spelling 'MyDevice' + null padding for a 6-register string."""
    client = MagicMock()
    response = MagicMock()
    response.isError.return_value = False
    # "MyDevice" = 0x4D79, 0x4465, 0x7669, 0x6365, then two null words
    response.registers = [0x4D79, 0x4465, 0x7669, 0x6365, 0x0000, 0x0000]
    client.read_holding_registers.return_value = response
    return client
```

- [ ] **Step 2: Run to confirm failure**

```bash
uv run pytest tests/test_reader.py -v -k "int16 or string_register or build_table_string"
```

Expected: `ImportError` or `AttributeError` — new fixtures and functions not yet in place.

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
    """Build a Rich table displaying register addresses, names, scaled values, and units."""
    table = Table(title="Victron EVCS Register Values", show_header=True)
    table.add_column("Address", style="cyan", justify="right")
    table.add_column("Name", style="white")
    table.add_column("Value", style="green", justify="right")
    table.add_column("Unit", style="yellow")

    for reg in registers:
        raw = values.get(reg.address)
        if raw is None:
            value_str = "[red]error[/red]"
            unit_str = ""
        elif isinstance(reg, StringRegister):
            value_str = str(raw)
            unit_str = ""
        else:
            value_str = format_value(raw, reg.scale)
            unit_str = reg.unit
        table.add_row(str(reg.address), reg.name, value_str, unit_str)

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
        allowed = set(CATEGORIES[category])
        result = [r for r in result if r.address in allowed]

    if address_range is not None:
        start, end = address_range
        result = [r for r in result if start <= r.address <= end]

    if name is not None:
        name_lower = name.lower()
        result = [r for r in result if name_lower in r.name.lower()]

    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Read Victron EVCS registers over Modbus TCP"
    )
    parser.add_argument("host", help="IP address or hostname of the EVCS")
    parser.add_argument("--port", type=int, default=502, help="Modbus TCP port (default: 502)")
    parser.add_argument("--category", help="Filter by category (e.g. sensors, status, config)")
    parser.add_argument("--address", help="Filter by address range, e.g. 5000-5050")
    parser.add_argument("--name", help="Filter by name substring (case-insensitive)")
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

    table = build_table(registers, values)
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

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add reader.py tests/test_reader.py
git commit -m "feat: add int16 conversion, string reads, filter_registers, and CLI filter args"
```

---

### Task 5: Add filter_registers tests

**Files:**
- Modify: `tests/test_reader.py`

- [ ] **Step 1: Write filter tests**

Add to `tests/test_reader.py`. **Merge the two new import lines into the existing import block at the top of the file** (do not append them at the bottom):

```python
from reader import filter_registers
from registers import ALL_REGISTERS, Register, StringRegister


def test_filter_no_filters_returns_all():
    result = filter_registers(ALL_REGISTERS)
    assert len(result) == 115


def test_filter_by_category_sensors():
    result = filter_registers(ALL_REGISTERS, category="sensors")
    addresses = {r.address for r in result}
    assert 5121 in addresses  # humidity
    assert 5127 in addresses  # power supply temp
    assert 5015 not in addresses  # charger status — not in sensors


def test_filter_by_address_range():
    result = filter_registers(ALL_REGISTERS, address_range=(5000, 5010))
    addresses = {r.address for r in result}
    assert all(5000 <= a <= 5010 for a in addresses)
    assert 5014 not in addresses


def test_filter_by_name():
    result = filter_registers(ALL_REGISTERS, name="power")
    assert all("power" in r.name.lower() for r in result)
    assert len(result) > 0


def test_filter_combined_and():
    result = filter_registers(
        ALL_REGISTERS,
        category="sensors",
        name="temperature",
    )
    addresses = {r.address for r in result}
    assert 5121 not in addresses  # humidity — not "temperature"
    assert 5122 in addresses      # "Onboard temperature"


def test_filter_string_registers_included_in_address_range():
    result = filter_registers(ALL_REGISTERS, address_range=(5000, 5010))
    addresses = {r.address for r in result}
    assert 5001 in addresses  # Serial Id (StringRegister)
```

- [ ] **Step 2: Run**

> Note: `filter_registers` is already implemented by Task 4, so these tests will pass immediately rather than fail first. That is expected for this task.

```bash
uv run pytest tests/test_reader.py -v -k "filter"
```

Expected: all filter tests PASS.

- [ ] **Step 3: Run full suite**

```bash
uv run pytest -v
```

Expected: all tests PASS.

- [ ] **Step 4: Commit**

```bash
git add tests/test_reader.py
git commit -m "test: add filter_registers tests"
```

---

### Task 6: Smoke test and beads cleanup

**Files:** none

- [ ] **Step 1: Verify CLI help shows new arguments**

```bash
uv run python reader.py --help
```

Expected output includes `--category`, `--address`, `--name`.

- [ ] **Step 2: Smoke test filter against live device (optional)**

```bash
uv run python reader.py 192.168.0.128 --category sensors
uv run python reader.py 192.168.0.128 --address 5000-5020
uv run python reader.py 192.168.0.128 --name power
```

- [ ] **Step 3: Close resolved beads issues**

```bash
bd close victron_evcs_modbus-603 --reason "String register support implemented (Serial Id, Device name)" --json
bd close victron_evcs_modbus-7un --reason "int16 signed register handling implemented" --json
```

- [ ] **Step 4: Sync beads and push**

```bash
bd sync
git add .beads/issues.jsonl
git commit -m "chore: close beads issues for string and int16 register support"
git pull --rebase
git push
git status
```

Expected: `Your branch is up to date with 'origin/main'`.
