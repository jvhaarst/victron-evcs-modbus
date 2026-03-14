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
            raw_bytes = struct.pack(f"<{reg.register_count}H", *response.registers)
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
        and (raw := values.get(reg.address)) is not None
        and raw != reg.default
    ]


def validate_write_value(reg: Register | StringRegister, input_str: str) -> int | str:
    """Parse and validate a human-readable display value for writing to reg.

    For Register: parses as float, multiplies by scale, rounds to int, validates
    type bounds. Returns raw int ready for write_register.
    For StringRegister: validates UTF-8 byte length. Returns input_str unchanged.
    Raises ValueError with a descriptive message on invalid input.
    """
    if isinstance(reg, StringRegister):
        encoded = input_str.encode("utf-8")
        max_bytes = reg.register_count * 2
        if len(encoded) > max_bytes:
            raise ValueError(
                f"String too long: {len(encoded)} bytes, max {max_bytes}"
            )
        return input_str
    try:
        display_val = float(input_str)
    except ValueError:
        raise ValueError(f"Invalid number: {input_str!r}")
    raw = round(display_val * reg.scale)
    if reg.data_type == "uint16":
        if not (0 <= raw <= 65535):
            raise ValueError(
                f"Value out of range for uint16 (0–65535 raw, got {raw})"
            )
    else:  # int16
        if not (-32768 <= raw <= 32767):
            raise ValueError(
                f"Value out of range for int16 (-32768–32767 raw, got {raw})"
            )
    return raw


def write_register(
    client: Any,
    reg: Register | StringRegister,
    value: int | str,
) -> bool:
    """Write a single register via Modbus FC6 (scalar) or FC16 (string).

    value must be a validated raw int (Register) or str (StringRegister).
    For int16 registers, value is a signed Python int (e.g. -500); wire
    encoding (adding 65536) is handled internally.
    Returns True on success, False on any failure (Modbus error or exception).
    """
    try:
        if isinstance(reg, StringRegister):
            raw_bytes = value.encode(reg.encoding)
            padded = raw_bytes.ljust(reg.register_count * 2, b"\x00")
            words = list(struct.unpack(f"<{reg.register_count}H", padded))
            response = client.write_registers(
                address=reg.address, values=words, device_id=1
            )
        else:
            if not isinstance(value, int):
                return False
            wire_value = (value + 65536) if value < 0 else value
            response = client.write_register(
                address=reg.address, value=wire_value, device_id=1
            )
        return not response.isError()
    except Exception:
        return False


def _handle_write(args: Any, console: "Console") -> None:
    """Handle the --write CLI flow."""
    addr_str, value_str = args.write
    try:
        address = int(addr_str)
    except ValueError:
        console.print(f"[red]Invalid address: {addr_str!r}[/red]")
        sys.exit(1)

    reg = next((r for r in ALL_REGISTERS if r.address == address), None)
    if reg is None:
        console.print(f"[red]Address {address} not found in register list[/red]")
        sys.exit(1)

    if reg.access != "R/W":
        console.print(f"[red]Register {address} ({reg.name}) is read-only[/red]")
        sys.exit(1)

    try:
        raw_value = validate_write_value(reg, value_str)
    except ValueError as e:
        console.print(f"[red]Invalid value: {e}[/red]")
        sys.exit(1)

    client = ModbusTcpClient(host=args.host, port=args.port)
    if not client.connect():
        console.print(f"[red]Failed to connect to {args.host}:{args.port}[/red]")
        sys.exit(1)

    try:
        success = write_register(client, reg, raw_value)
    finally:
        client.close()

    if success:
        if isinstance(reg, StringRegister):
            display = str(raw_value)
            unit = ""
        else:
            display = format_value(raw_value, reg.scale)
            unit = f" {reg.unit}" if reg.unit else ""
        console.print(f"[green]Written {address} ({reg.name}): {display}{unit}[/green]")
    else:
        console.print(f"[red]Write failed for address {address}[/red]")
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Read Victron EVCS registers over Modbus TCP"
    )
    parser.add_argument("host", help="IP address or hostname of the EVCS")
    parser.add_argument("--port", type=int, default=502, help="Modbus TCP port (default: 502)")
    parser.add_argument("--category", help="Filter by category (e.g. sensors, status, config)")
    parser.add_argument("--address", help="Filter by address range, e.g. 5000-5050")
    parser.add_argument("--name", help="Filter by name substring (case-insensitive)")

    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--changed", action="store_true",
        help="Show only registers that differ from their factory default",
    )
    mode_group.add_argument(
        "--write", nargs=2, metavar=("ADDRESS", "VALUE"),
        help="Write VALUE to register at ADDRESS (e.g. --write 5016 10)",
    )
    mode_group.add_argument(
        "--interactive", action="store_true",
        help="Launch interactive TUI editor",
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

    if args.write:
        _handle_write(args, console)
        return

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
    except Exception as e:
        client.close()
        console.print(f"[red]Failed to read registers: {e}[/red]")
        sys.exit(1)

    if args.interactive:
        from tui import RegisterEditorApp
        try:
            RegisterEditorApp(client, registers, values).run()
        finally:
            client.close()
        return

    client.close()
    registers_to_display = filter_changed(registers, values) if args.changed else registers
    table = build_table(registers_to_display, values)
    console.print(table)


if __name__ == "__main__":
    main()
