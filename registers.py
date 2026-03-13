"""Holding register definitions for Victron EVCS Modbus TCP (unit-id 1).

Source: EVCS-Modbus-TCP-register-list-v3.8.xlsx, sheet "Holding registers".
"""
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class Register:
    address: int
    name: str
    data_type: Literal["uint16", "int16"]
    scale: int      # divide raw value by this to get real value; must be > 0
    unit: str       # display unit string

    def __post_init__(self) -> None:
        if self.scale <= 0:
            raise ValueError(f"scale must be > 0, got {self.scale!r}")


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


@dataclass(frozen=True)
class StringRegister:
    address: int          # start address
    name: str
    register_count: int   # number of Modbus registers (each holds 2 bytes)
    encoding: str = "utf-8"

    def __post_init__(self) -> None:
        if self.register_count <= 0:
            raise ValueError(f"register_count must be > 0, got {self.register_count!r}")


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
    # new scalar registers inserted in Task 2
)
