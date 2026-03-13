# EVCS Modbus TCP Reader Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** A simple Python CLI tool that connects to a Victron EVCS over Modbus TCP and displays all holding register values as a formatted table.

**Architecture:** A `registers.py` module holds the static register definitions (address, name, type, scale, unit). A `reader.py` module connects via Modbus TCP using `pymodbus`, reads all registers, and prints a `rich` table to stdout. Entry point is `main.py` invoked via `uv run`.

**Tech Stack:** Python 3.12+, uv (venv + deps), pymodbus 3.x (Modbus TCP), rich (table output), pytest + pytest-mock (tests)

---

## Context: Register Map

The Excel file `EVCS-Modbus-TCP-register-list-v3.8.xlsx` (sheet: "Holding registers") defines:
- **Unit ID:** 1
- **Addresses:** 5000–5140 (contiguous; many empty after 5140)
- **Types:** `uint16`, `int16`, `string` (multi-register)
- **Scaled values:** e.g. `A*10`, `kWh*100`, `V*100`, `°C*10` — stored in Notes column
- **Multi-register:** Serial Id (5001–5006, 6 regs), Device name (5027–5048, 22 regs)

For this first iteration, **skip string registers** (Serial Id, Device name) — read only single uint16/int16 registers. They can be added later.

Registers to implement (address → name → unit → scale):

| Address | Name                          | Type   | Unit    | Scale |
|---------|-------------------------------|--------|---------|-------|
| 5000    | Product ID                    | uint16 | —       | 1     |
| 5007    | FW version H                  | uint16 | —       | 1     |
| 5008    | FW version L                  | uint16 | —       | 1     |
| 5009    | Charge mode                   | uint16 | —       | 1     |
| 5010    | Start/stop charging           | uint16 | —       | 1     |
| 5011    | L1 power used                 | uint16 | W       | 1     |
| 5012    | L2 power used                 | uint16 | W       | 1     |
| 5013    | L3 power used                 | uint16 | W       | 1     |
| 5014    | Total power                   | uint16 | W       | 1     |
| 5015    | Charger status                | uint16 | —       | 1     |
| 5016    | Charging current              | uint16 | A       | 1     |
| 5017    | Max current                   | uint16 | A       | 1     |
| 5018    | Charging current actual       | uint16 | A       | 10    |
| 5019    | Session charging time H       | uint16 | s       | 1     |
| 5020    | Session charging time L       | uint16 | s       | 1     |
| 5021    | Session energy                | uint16 | kWh     | 100   |
| 5022    | Session cost                  | uint16 | currency| 100   |
| 5023    | Total energy H                | uint16 | kWh     | 1     |
| 5024    | Total energy L                | uint16 | kWh     | 100   |
| 5025    | CP voltage                    | uint16 | V       | 100   |
| 5026    | Charger position              | uint16 | —       | 1     |
| 5049    | Charger autostart             | uint16 | —       | 1     |
| 5050    | Control via display           | uint16 | —       | 1     |
| 5062    | Min current                   | uint16 | A       | 1     |
| 5094    | EVCS errors L                 | uint16 | —       | 1     |
| 5095    | EVCS errors H                 | uint16 | —       | 1     |
| 5109    | Detected car phases           | uint16 | —       | 1     |
| 5111    | UP-time H                     | uint16 | s       | 1     |
| 5112    | UP-time L                     | uint16 | s       | 1     |
| 5113    | Reboot counter                | uint16 | —       | 1     |
| 5121    | Onboard humidity              | uint16 | %       | 10    |
| 5122    | Onboard temperature           | uint16 | °C      | 10    |
| 5127    | Power supply temperature      | uint16 | °C      | 10    |

---

## Task 1: Initialize UV project

**Files:**
- Create: `pyproject.toml`

**Step 1: Create pyproject.toml**

```toml
[project]
name = "victron-evcs-modbus"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "pymodbus>=3.7",
    "rich>=13.0",
]

[dependency-groups]
dev = [
    "pytest>=8.0",
    "pytest-mock>=3.12",
]

[project.scripts]
evcs-reader = "reader:main"
```

**Step 2: Create the virtual environment and install deps**

```bash
uv sync --dev
```

Expected output: `Resolved N packages` and a `.venv` directory created.

**Step 3: Verify**

```bash
uv run python -c "import pymodbus; import rich; print('OK')"
```

Expected: `OK`

**Step 4: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "chore: initialize uv project with pymodbus and rich"
```

---

## Task 2: Register definitions module

**Files:**
- Create: `registers.py`
- Create: `tests/test_registers.py`

**Step 1: Write failing tests**

Create `tests/__init__.py` (empty) and `tests/test_registers.py`:

```python
from registers import REGISTERS, Register


def test_register_list_is_not_empty():
    assert len(REGISTERS) > 0


def test_register_has_required_fields():
    reg = REGISTERS[0]
    assert isinstance(reg.address, int)
    assert isinstance(reg.name, str)
    assert reg.data_type in ("uint16", "int16")
    assert isinstance(reg.scale, int)
    assert isinstance(reg.unit, str)


def test_product_id_register():
    reg = next(r for r in REGISTERS if r.address == 5000)
    assert reg.name == "Product ID"
    assert reg.data_type == "uint16"
    assert reg.scale == 1
    assert reg.unit == ""


def test_charging_current_actual_has_scale_10():
    reg = next(r for r in REGISTERS if r.address == 5018)
    assert reg.scale == 10
    assert reg.unit == "A"


def test_addresses_are_unique():
    addresses = [r.address for r in REGISTERS]
    assert len(addresses) == len(set(addresses))
```

**Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_registers.py -v
```

Expected: `ImportError` or `ModuleNotFoundError` — registers.py doesn't exist yet.

**Step 3: Create registers.py**

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class Register:
    address: int
    name: str
    data_type: str  # "uint16" or "int16"
    scale: int      # divide raw value by this to get real value
    unit: str       # display unit string


REGISTERS = [
    Register(5000, "Product ID",                  "uint16", 1,   ""),
    Register(5007, "FW version H",                "uint16", 1,   ""),
    Register(5008, "FW version L",                "uint16", 1,   ""),
    Register(5009, "Charge mode",                 "uint16", 1,   ""),
    Register(5010, "Start/stop charging",         "uint16", 1,   ""),
    Register(5011, "L1 power used",               "uint16", 1,   "W"),
    Register(5012, "L2 power used",               "uint16", 1,   "W"),
    Register(5013, "L3 power used",               "uint16", 1,   "W"),
    Register(5014, "Total power",                 "uint16", 1,   "W"),
    Register(5015, "Charger status",              "uint16", 1,   ""),
    Register(5016, "Charging current",            "uint16", 1,   "A"),
    Register(5017, "Max current",                 "uint16", 1,   "A"),
    Register(5018, "Charging current actual",     "uint16", 10,  "A"),
    Register(5019, "Session charging time H",     "uint16", 1,   "s"),
    Register(5020, "Session charging time L",     "uint16", 1,   "s"),
    Register(5021, "Session energy",              "uint16", 100, "kWh"),
    Register(5022, "Session cost",                "uint16", 100, "currency"),
    Register(5023, "Total energy H",              "uint16", 1,   "kWh"),
    Register(5024, "Total energy L",              "uint16", 100, "kWh"),
    Register(5025, "CP voltage",                  "uint16", 100, "V"),
    Register(5026, "Charger position",            "uint16", 1,   ""),
    Register(5049, "Charger autostart",           "uint16", 1,   ""),
    Register(5050, "Control via display",         "uint16", 1,   ""),
    Register(5062, "Min current",                 "uint16", 1,   "A"),
    Register(5094, "EVCS errors L",               "uint16", 1,   ""),
    Register(5095, "EVCS errors H",               "uint16", 1,   ""),
    Register(5109, "Detected car phases",         "uint16", 1,   ""),
    Register(5111, "UP-time H",                   "uint16", 1,   "s"),
    Register(5112, "UP-time L",                   "uint16", 1,   "s"),
    Register(5113, "Reboot counter",              "uint16", 1,   ""),
    Register(5121, "Onboard humidity",            "uint16", 10,  "%"),
    Register(5122, "Onboard temperature",         "uint16", 10,  "°C"),
    Register(5127, "Power supply temperature",    "uint16", 10,  "°C"),
]
```

**Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_registers.py -v
```

Expected: all 5 tests PASS.

**Step 5: Commit**

```bash
git add registers.py tests/__init__.py tests/test_registers.py
git commit -m "feat: add register definitions with dataclass"
```

---

## Task 3: Modbus reader module

**Files:**
- Create: `reader.py`
- Create: `tests/test_reader.py`

**Step 1: Write failing tests**

Create `tests/test_reader.py`:

```python
from unittest.mock import MagicMock, patch
import pytest
from reader import read_registers, format_value


# --- format_value tests (pure, no mocking needed) ---

def test_format_value_no_scale():
    assert format_value(42, scale=1) == "42"


def test_format_value_with_scale():
    assert format_value(185, scale=10) == "18.5"


def test_format_value_exact_division():
    assert format_value(1500, scale=100) == "15.0"


# --- read_registers tests (mock pymodbus) ---

def test_read_registers_returns_dict(mock_modbus_client):
    from registers import REGISTERS
    result = read_registers(mock_modbus_client, REGISTERS)
    assert isinstance(result, dict)
    assert 5000 in result


def test_read_registers_handles_error_response(mock_modbus_client_error):
    from registers import REGISTERS
    result = read_registers(mock_modbus_client_error, REGISTERS)
    assert result[5000] is None


@pytest.fixture
def mock_modbus_client():
    client = MagicMock()
    response = MagicMock()
    response.isError.return_value = False
    response.registers = [0xC024] + [0] * 127  # 128 registers worth of zeros
    client.read_holding_registers.return_value = response
    return client


@pytest.fixture
def mock_modbus_client_error():
    client = MagicMock()
    response = MagicMock()
    response.isError.return_value = True
    client.read_holding_registers.return_value = response
    return client
```

**Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_reader.py -v
```

Expected: `ImportError` — reader.py doesn't exist yet.

**Step 3: Create reader.py**

```python
from __future__ import annotations

import argparse
import sys
from typing import TYPE_CHECKING

from pymodbus.client import ModbusTcpClient
from rich.console import Console
from rich.table import Table

from registers import REGISTERS, Register

if TYPE_CHECKING:
    from collections.abc import Sequence


def format_value(raw: int, scale: int) -> str:
    if scale == 1:
        return str(raw)
    return str(round(raw / scale, max(0, len(str(scale)) - 1)))


def read_registers(client, registers: Sequence[Register]) -> dict[int, int | None]:
    """Read all registers in one batch request where possible.

    Returns a dict mapping address -> raw value (or None on error).
    """
    if not registers:
        return {}

    addresses = sorted(r.address for r in registers)
    start = addresses[0]
    count = addresses[-1] - start + 1

    response = client.read_holding_registers(address=start, count=count, slave=1)

    if response.isError():
        return {addr: None for addr in addresses}

    raw_values = response.registers
    result = {}
    for addr in addresses:
        offset = addr - start
        if offset < len(raw_values):
            result[addr] = raw_values[offset]
        else:
            result[addr] = None
    return result


def build_table(registers: Sequence[Register], values: dict[int, int | None]) -> Table:
    table = Table(title="Victron EVCS Register Values", show_header=True)
    table.add_column("Address", style="cyan", justify="right")
    table.add_column("Name", style="white")
    table.add_column("Value", style="green", justify="right")
    table.add_column("Unit", style="yellow")

    for reg in registers:
        raw = values.get(reg.address)
        if raw is None:
            value_str = "[red]error[/red]"
        else:
            value_str = format_value(raw, reg.scale)
        table.add_row(str(reg.address), reg.name, value_str, reg.unit)

    return table


def main() -> None:
    parser = argparse.ArgumentParser(description="Read Victron EVCS registers over Modbus TCP")
    parser.add_argument("host", help="IP address or hostname of the EVCS")
    parser.add_argument("--port", type=int, default=502, help="Modbus TCP port (default: 502)")
    args = parser.parse_args()

    console = Console()

    client = ModbusTcpClient(host=args.host, port=args.port)
    if not client.connect():
        console.print(f"[red]Failed to connect to {args.host}:{args.port}[/red]")
        sys.exit(1)

    try:
        values = read_registers(client, REGISTERS)
    finally:
        client.close()

    table = build_table(REGISTERS, values)
    console.print(table)


if __name__ == "__main__":
    main()
```

**Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_reader.py -v
```

Expected: all tests PASS.

**Step 5: Run full test suite**

```bash
uv run pytest -v
```

Expected: all tests PASS.

**Step 6: Commit**

```bash
git add reader.py tests/test_reader.py
git commit -m "feat: add modbus reader with table output"
```

---

## Task 4: Smoke test & beads cleanup

**Step 1: Verify CLI help works**

```bash
uv run python reader.py --help
```

Expected output:
```
usage: reader.py [-h] [--port PORT] host
...
```

**Step 2: Run full test suite one final time**

```bash
uv run pytest -v
```

Expected: all tests PASS.

**Step 3: Create beads issues for follow-up work**

```bash
bd create "Add string register support (Serial Id, Device name)" \
  --description="Serial Id spans 5001-5006 (6 regs, 12 chars), Device name spans 5027-5048 (22 regs, 44 bytes UTF-8). Add multi-register string reads to reader." \
  -t feature -p 2 --json

bd create "Add scaled value formatting for int16 signed registers" \
  --description="int16 registers (e.g. Feed-in power thresholds 5071-5075) need signed interpretation. pymodbus returns uint16; need to convert values > 32767 to negative." \
  -t feature -p 2 --json

bd create "Add --unit-id CLI argument" \
  --description="Modbus unit/slave ID is hardcoded to 1. Make it a CLI argument with default 1." \
  -t feature -p 3 --json
```

**Step 4: Commit docs and sync beads**

```bash
git add docs/
bd sync
git add .beads/issues.jsonl
git commit -m "docs: add implementation plan and beads follow-up issues"
```

**Step 5: Push**

```bash
git pull --rebase
git push
git status
```

Expected: `Your branch is up to date with 'origin/...'`

---

## Usage (after implementation)

```bash
# Connect to EVCS at 192.168.1.100
uv run python reader.py 192.168.1.100

# With custom port
uv run python reader.py 192.168.1.100 --port 502
```

Expected output: a rich table like:

```
          Victron EVCS Register Values
┌─────────┬───────────────────────────┬───────┬──────────┐
│ Address │ Name                      │ Value │ Unit     │
├─────────┼───────────────────────────┼───────┼──────────┤
│    5000 │ Product ID                │ 49188 │          │
│    5009 │ Charge mode               │     1 │          │
│    5014 │ Total power               │   350 │ W        │
│    5015 │ Charger status            │     2 │          │
│    5018 │ Charging current actual   │  16.0 │ A        │
│    ...  │ ...                       │   ... │ ...      │
└─────────┴───────────────────────────┴───────┴──────────┘
```
