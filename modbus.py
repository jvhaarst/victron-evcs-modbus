"""Modbus TCP I/O operations for Victron EVCS registers."""
from __future__ import annotations

import struct
from typing import TYPE_CHECKING, Any

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
