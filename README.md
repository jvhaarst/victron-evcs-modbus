# victron-evcs-modbus

A small Python CLI that reads holding registers from a [Victron EV Charging Station (EVCS)](https://www.victronenergy.com/ev-charging) over Modbus TCP and displays them as a formatted table.

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- Victron EVCS reachable on the network with Modbus TCP enabled (default port 502)

## Installation

```bash
git clone https://github.com/jvhaarst/victron-evcs-modbus
cd victron-evcs-modbus
uv sync
```

## Usage

```bash
uv run python reader.py <host> [--port PORT]
```

**Examples:**

```bash
# Connect to EVCS at 192.168.0.128 on default port 502
uv run python reader.py 192.168.0.128

# Custom port
uv run python reader.py 192.168.0.128 --port 5020
```

**Example output:**

```
               Victron EVCS Register Values
┏━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━┓
┃ Address ┃ Name                     ┃  Value ┃ Unit     ┃
┡━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━┩
│    5000 │ Product ID               │  49189 │          │
│    5009 │ Charge mode              │      0 │          │
│    5014 │ Total power              │      0 │ W        │
│    5015 │ Charger status           │      0 │          │
│    5018 │ Charging current actual  │    0.0 │ A        │
│    5024 │ Total energy L           │ 117.88 │ kWh      │
│    5127 │ Power supply temperature │   21.5 │ °C       │
│    ...  │ ...                      │    ... │ ...      │
└─────────┴──────────────────────────┴────────┴──────────┘
```

33 registers are read in total — see [`registers.py`](registers.py) for the full list.

## Registers

The register definitions are sourced from the official Victron spec:
[`docs/specs/EVCS-Modbus-TCP-register-list-v3.8.xlsx`](docs/specs/EVCS-Modbus-TCP-register-list-v3.8.xlsx)

Modbus unit-id: **1**, addresses: **5000–5127**.

Registers with scaling (e.g. `A*10`, `kWh*100`, `°C*10`) are automatically divided and displayed as real values.

## Development

```bash
# Install dev dependencies
uv sync --dev

# Run tests
uv run pytest -v
```

## Roadmap

- Add string register support (Serial Id, Device name)
- Handle `int16` signed registers (Feed-in power thresholds)
- Add `--unit-id` CLI argument
