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
