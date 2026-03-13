from __future__ import annotations

import argparse
import sys
from typing import Any, TYPE_CHECKING

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


def read_registers(client: Any, registers: Sequence[Register]) -> dict[int, int | None]:
    """Read registers in batch requests (max 125 per FC3 call).

    Returns a dict mapping address -> raw value (or None on error).
    """
    if not registers:
        return {}

    addresses = sorted(r.address for r in registers)
    result: dict[int, int | None] = {}

    # Split into chunks of 125 to stay within the Modbus FC3 limit
    chunk_start = 0
    while chunk_start < len(addresses):
        start_addr = addresses[chunk_start]
        # Find how many consecutive addresses fit in one 125-register window
        chunk_end = chunk_start
        while chunk_end + 1 < len(addresses) and addresses[chunk_end + 1] - start_addr < 125:
            chunk_end += 1

        end_addr = addresses[chunk_end]
        count = end_addr - start_addr + 1

        response = client.read_holding_registers(address=start_addr, count=count, slave=1)

        if response.isError():
            for addr in addresses[chunk_start:chunk_end + 1]:
                result[addr] = None
        else:
            raw_values = response.registers
            for addr in addresses[chunk_start:chunk_end + 1]:
                offset = addr - start_addr
                result[addr] = raw_values[offset] if offset < len(raw_values) else None

        chunk_start = chunk_end + 1

    return result


def build_table(registers: Sequence[Register], values: dict[int, int | None]) -> Table:
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
