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
uv run python cli.py <host> [options]
```

## Settings for Victron EVCS — 1P/3P Phase Switching

See [Victron EVCS — 1P/3P Phase Switching via Modbus TCP](./Victron-EVCS-1P-3P-Phase-Switching-via-Modbus-TCP.md)

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--port PORT` | `502` | Modbus TCP port |
| `--unit-id ID` | `1` | Modbus unit/slave ID |
| `--category CAT` | — | Filter by category |
| `--address START-END` | — | Filter by address range |
| `--name SUBSTR` | — | Filter by name substring |
| `--read` | — | Print register table and exit (default: launch TUI) |
| `--changed` | — | Show only registers that differ from factory default (implies `--read`) |
| `--write ADDR VALUE` | — | Write a value to a register |
| `--scan START-END` | — | Scan raw register values for every address in range |

### Read registers (table output)

```bash
# All 115 registers
uv run python cli.py 192.168.0.128 --read

# Filter by category
uv run python cli.py 192.168.0.128 --read --category config

# Filter by address range
uv run python cli.py 192.168.0.128 --read --address 5009-5026

# Filter by name substring (case-insensitive)
uv run python cli.py 192.168.0.128 --read --name "feed in"

# Show only registers that differ from their factory default (--changed implies --read)
uv run python cli.py 192.168.0.128 --changed

# Use a non-default Modbus unit ID
uv run python cli.py 192.168.0.128 --unit-id 2 --read
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
uv run python cli.py <host> --write <address> <value>

# Examples
uv run python cli.py 192.168.0.128 --write 5016 10       # set charging current to 10 A
uv run python cli.py 192.168.0.128 --write 5027 "My EV"  # set device name
uv run python cli.py 192.168.0.128 --write 5071 -500     # negative int16 value
```

On success: `Written 5016 (Charging current): 10 A`

After each write the register is read back to confirm the device accepted the value. If the device clamped it, a warning is printed:

```
Written 5016 (Charging current): 10 A
Warning: read-back value differs — device may have clamped the value
```

Only R/W registers can be written. Values outside the register's documented range are rejected before sending.

### Scan raw registers

```bash
uv run python cli.py 192.168.0.128 --scan 5000-5200
```

Reads every address in the given range as a raw uint16, regardless of whether it appears in the spec sheet. Useful for discovering undocumented registers.

**Example output:**

```
           Register Scan 5000–5010
┏━━━━━━━━━┳━━━━━━━━┳━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━┓
┃ Address ┃ Hex    ┃   Dec ┃ Hex value ┃ Known name        ┃
┡━━━━━━━━━╇━━━━━━━━╇━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━┩
│    5000 │ 0x1388 │ 41061 │ 0xA065    │ Product ID        │
│    5001 │ 0x1389 │   ...  │ ...       │ Serial ID         │
│    5010 │ 0x138A │     0 │ 0x0000    │                   │  ← unknown
└─────────┴────────┴───────┴───────────┴───────────────────┘
```

The **Known name** column is populated where the address matches a register in the spec; blank rows are undocumented. Addresses that return a Modbus error are shown as `error`.

### Interactive TUI (default)

```bash
# Default: launches TUI editor
uv run python cli.py <host> [--category ...] [--address ...] [--name ...]
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
| ? | Show notes for the focused register |

## Registers

117 holding registers sourced from the official Victron spec:
[`docs/specs/EVCS-Modbus-TCP-register-list-v3.9.xlsx`](docs/specs/EVCS-Modbus-TCP-register-list-v3.9.xlsx)
This was downloaded through https://www.victronenergy.com/support-and-downloads/technical-information

Modbus unit-id: **1** (configurable via `--unit-id`), addresses: **5000–5143**. Scaled values (e.g. `A×10`, `kWh×100`, `°C×10`) are automatically converted for display and input. R/W registers enforce the documented valid range at input time.

## Development

```bash
# Install dev dependencies
uv sync --dev

# Run tests
uv run pytest -v
```
