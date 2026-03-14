# victron-evcs-modbus

A Python CLI for reading and writing holding registers on a [Victron EV Charging Station (EVCS)](https://www.victronenergy.com/ev-charging) over Modbus TCP.

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
uv run python reader.py <host> [options]
```

### Read registers (default)

```bash
# All 115 registers
uv run python reader.py 192.168.0.128

# Filter by category
uv run python reader.py 192.168.0.128 --category config

# Filter by address range
uv run python reader.py 192.168.0.128 --address 5009-5026

# Filter by name substring (case-insensitive)
uv run python reader.py 192.168.0.128 --name "feed in"

# Show only registers that differ from their factory default
uv run python reader.py 192.168.0.128 --changed
```

**Example output:**

```
                      Victron EVCS Register Values
┏━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━┳━━━━━━━━━┓
┃ Address ┃ Name                           ┃  Value ┃ Unit ┃ Default ┃
┡━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━╇━━━━━━━━━┩
│    5009 │ Charge mode                    │      0 │      │       0 │
│    5016 │ Charging current               │     16 │ A    │       6 │  ← yellow if differs from default
│    5017 │ Max current                    │     10 │ A    │      10 │
│    5018 │ Charging current actual        │   16.0 │ A    │         │
│     ... │ ...                            │    ... │      │     ... │
└─────────┴────────────────────────────────┴────────┴──────┴─────────┘
```

Values that differ from their factory default are highlighted in yellow.

### Write a register

```bash
# Write a single value (non-interactive)
uv run python reader.py <host> --write <address> <value>

# Examples
uv run python reader.py 192.168.0.128 --write 5016 10       # set charging current to 10 A
uv run python reader.py 192.168.0.128 --write 5027 "My EV"  # set device name
uv run python reader.py 192.168.0.128 --write 5071 -500     # negative int16 value
```

On success: `Written 5016 (Charging current): 10 A`

Only R/W registers can be written. Writing a read-only address or an out-of-range value exits with an error.

### Interactive TUI

```bash
uv run python reader.py <host> --interactive [--category ...] [--address ...] [--name ...]
```

Launches a full-screen register editor:

```
 Victron EVCS Register Editor
 Address │ Name                  │ Value  │ Unit │ Default │ Access
─────────────────────────────────────────────────────────────────────
   5009  │ Charge mode           │ 0      │      │ 0       │ R/W
 ► 5016  │ Charging current      │[ 16  ] │ A    │ 6       │ R/W   ← editing
   5017  │ Max current           │ 10     │ A    │ 10      │ R/W
   5018  │ Charging current act. │ 16.0   │ A    │         │ R     ← dimmed
 * 5026  │ Charger position      │ 1      │      │ 0       │ R/W   ← pending
─────────────────────────────────────────────────────────────────────
 3 pending  ^S Write  ^R Refresh  ^Q Quit
```

| Key | Action |
|-----|--------|
| Arrow keys | Navigate |
| Enter | Edit (R/W rows only) |
| Escape | Cancel edit |
| Ctrl+S | Write all pending changes |
| Ctrl+R | Re-read all registers |
| Ctrl+Q | Quit (prompts if pending writes) |

## Registers

115 holding registers sourced from the official Victron spec:
[`docs/specs/EVCS-Modbus-TCP-register-list-v3.8.xlsx`](docs/specs/EVCS-Modbus-TCP-register-list-v3.8.xlsx)

Modbus unit-id: **1**, addresses: **5000–5140**. Scaled values (e.g. `A×10`, `kWh×100`, `°C×10`) are automatically converted for display and input.

## Development

```bash
# Install dev dependencies
uv sync --dev

# Run tests
uv run pytest -v
```
