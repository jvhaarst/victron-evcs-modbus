"""Holding register definitions for Victron EVCS Modbus TCP (unit-id 1).

Source: EVCS-Modbus-TCP-register-list-v3.8.xlsx, sheet "Holding registers".
"""
from dataclasses import dataclass
from typing import Literal, Optional


@dataclass(frozen=True)
class Register:
    address: int
    name: str
    data_type: Literal["uint16", "int16"]
    scale: int      # divide raw value by this to get real value; must be > 0
    unit: str       # display unit string
    default: Optional[int] = None  # factory default (None = no default in spec)
    access: Literal["R", "R/W"] = "R"

    def __post_init__(self) -> None:
        if self.scale <= 0:
            raise ValueError(f"scale must be > 0, got {self.scale!r}")


REGISTERS = [
    Register(5000, "Product ID",                  "uint16", 1,   ""),
    Register(5007, "FW version H",                "uint16", 1,   ""),
    Register(5008, "FW version L",                "uint16", 1,   ""),
    Register(5009, "Charge mode",                 "uint16", 1,   "",        default=0,  access="R/W"),
    Register(5010, "Start/stop charging",         "uint16", 1,   "",                    access="R/W"),
    Register(5011, "L1 power used",               "uint16", 1,   "W"),
    Register(5012, "L2 power used",               "uint16", 1,   "W"),
    Register(5013, "L3 power used",               "uint16", 1,   "W"),
    Register(5014, "Total power",                 "uint16", 1,   "W"),
    Register(5015, "Charger status",              "uint16", 1,   ""),
    Register(5016, "Charging current",            "uint16", 1,   "A",       default=6,  access="R/W"),
    Register(5017, "Max current",                 "uint16", 1,   "A",       default=10, access="R/W"),
    Register(5018, "Charging current actual",     "uint16", 10,  "A"),
    Register(5019, "Session charging time H",     "uint16", 1,   "s"),
    Register(5020, "Session charging time L",     "uint16", 1,   "s"),
    Register(5021, "Session energy",              "uint16", 100, "kWh"),
    Register(5022, "Session cost",                "uint16", 100, "currency"),
    Register(5023, "Total energy H",              "uint16", 1,   "kWh"),
    Register(5024, "Total energy L",              "uint16", 100, "kWh"),
    Register(5025, "CP voltage",                  "uint16", 100, "V"),
    Register(5026, "Charger position",            "uint16", 1,   "",        default=0,  access="R/W"),
    Register(5049, "Charger autostart",           "uint16", 1,   "",        default=1,  access="R/W"),
    Register(5050, "Control via display",         "uint16", 1,   "",        default=1,  access="R/W"),
    Register(5062, "Min current",                 "uint16", 1,   "A",       default=6,  access="R/W"),
    Register(5094, "EVCS errors L",               "uint16", 1,   "",        default=0),
    Register(5095, "EVCS errors H",               "uint16", 1,   "",        default=0),
    Register(5109, "Detected car phases",         "uint16", 1,   "",        default=1),
    Register(5111, "UP-time H",                   "uint16", 1,   "s"),
    Register(5112, "UP-time L",                   "uint16", 1,   "s"),
    Register(5113, "Reboot counter",              "uint16", 1,   ""),
    Register(5121, "Onboard humidity",            "uint16", 10,  "%"),
    Register(5122, "Onboard temperature",         "uint16", 10,  "°C"),
    Register(5127, "Power supply temperature",    "uint16", 10,  "°C",      default=0),
]


@dataclass(frozen=True)
class StringRegister:
    address: int          # start address
    name: str
    register_count: int   # number of Modbus registers (each holds 2 bytes)
    encoding: str = "utf-8"
    access: Literal["R", "R/W"] = "R"

    def __post_init__(self) -> None:
        if self.register_count <= 0:
            raise ValueError(f"register_count must be > 0, got {self.register_count!r}")


STRING_REGISTERS: list[StringRegister] = [
    StringRegister(5001, "Serial Id",    6),                    # R (default)
    StringRegister(5027, "Device name", 22, access="R/W"),
]

_NEW_REGISTERS: list[Register] = [
    Register(5051, "Display active backlight",                                     "uint16", 1,   "%",    default=100,   access="R/W"),
    Register(5052, "Display idle backlight",                                       "uint16", 1,   "%",    default=7,     access="R/W"),
    Register(5053, "Display active timeout",                                       "uint16", 1,   "s",    default=120,   access="R/W"),
    Register(5054, "Contactor active when charged",                                "uint16", 1,   "",     default=0,     access="R/W"),
    Register(5055, "Manual mode phase",                                            "uint16", 1,   "",     default=1,     access="R/W"),
    Register(5056, "Auto mode phase",                                              "uint16", 1,   "",     default=1,     access="R/W"),
    Register(5057, "Power for 3phase",                                             "uint16", 1,   "W",    default=4800,  access="R/W"),
    Register(5058, "Power for single phase",                                       "uint16", 1,   "W",    default=4300,  access="R/W"),
    Register(5059, "Phase switching timeout",                                      "uint16", 1,   "s",    default=60,    access="R/W"),
    Register(5060, "CP Calibration command",                                       "uint16", 1,   "",                    access="R/W"),
    Register(5061, "CP Calibration status",                                        "uint16", 1,   ""),
    Register(5063, "Power calibration offset",                                     "uint16", 1,   "",     default=100,   access="R/W"),
    Register(5064, "EVCS reset",                                                   "uint16", 1,   "",                    access="R/W"),
    Register(5065, "Auto mode type",                                               "uint16", 1,   "",     default=1,     access="R/W"),
    Register(5066, "Backup battery SOC for start charging in Battery powered",     "uint16", 1,   "%",    default=90,    access="R/W"),
    Register(5067, "Backup battery min SOC to allow charging if OFF Grid",         "uint16", 1,   "%",    default=20,    access="R/W"),
    Register(5068, "Backup battery emulation",                                     "uint16", 1,   "",     default=0,     access="R/W"),
    Register(5069, "'Feed in'. Start delay",                                       "uint16", 1,   "s",    default=30,    access="R/W"),
    Register(5070, "'Feed in'. Stop delay",                                        "uint16", 1,   "s",    default=60,    access="R/W"),
    Register(5071, "'Feed in'. Single phase. Grid power for start",                "int16",  1,   "W",    default=-500,  access="R/W"),
    Register(5072, "'Feed in'. Multi phase. Grid power for start",                 "int16",  1,   "W",    default=-1400, access="R/W"),
    Register(5073, "'Feed in'. Grid power threshold for increase",                 "int16",  1,   "W",    default=-250,  access="R/W"),
    Register(5074, "'Feed in'. Grid power threshold for decrease",                 "int16",  1,   "W",    default=250,   access="R/W"),
    Register(5075, "'Feed in'. Backup battery discharging power threshold",        "int16",  1,   "W",    default=-100,  access="R/W"),
    Register(5076, "'Feed in'. Current step",                                      "uint16", 10,  "A",    default=2,     access="R/W"),
    Register(5077, "'Feed in'. Time step",                                         "uint16", 1,   "ms",   default=1000,  access="R/W"),
    Register(5078, "'Battery powered'. Start delay min",                           "uint16", 1,   "s",    default=30,    access="R/W"),
    Register(5079, "'Battery powered'. Stop delay",                                "uint16", 1,   "s",    default=60,    access="R/W"),
    Register(5080, "'Battery powered'. Start abort delay",                         "uint16", 1,   "s",    default=10,    access="R/W"),
    Register(5081, "'Battery powered'. BKPB balance power",                        "uint16", 1,   "W",    default=500,   access="R/W"),
    Register(5082, "'Battery powered'. BKPB balance SOC max",                      "uint16", 1,   "%",    default=80,    access="R/W"),
    Register(5083, "'Battery powered'. Available sun power threshold for start",   "uint16", 1,   "W",    default=100,   access="R/W"),
    Register(5084, "'Battery powered'. Grid power threshold for start",            "uint16", 1,   "W",    default=25,    access="R/W"),
    Register(5085, "'Battery powered'. BKPB power threshold for decrease",         "uint16", 1,   "W",    default=400,   access="R/W"),
    Register(5086, "'Battery powered'. Grid power threshold for decrease",         "uint16", 1,   "W",    default=400,   access="R/W"),
    Register(5087, "'Battery powered'. Discharging detect timeout",                "uint16", 1,   "s",    default=7,     access="R/W"),
    Register(5088, "'Battery powered'. Next try timeout for increase",             "uint16", 1,   "s",    default=45,    access="R/W"),
    Register(5089, "'Battery powered'. Time step",                                 "uint16", 1,   "s",    default=15,    access="R/W"),
    Register(5090, "'Battery powered'. Current step",                              "uint16", 10,  "A",    default=10,    access="R/W"),
    Register(5091, "'Battery powered'. Grid power for 'feed in' detection",        "int16",  1,   "W",    default=-1500, access="R/W"),
    Register(5092, "'Battery powered'. Start delay max",                           "uint16", 1,   "s",    default=300,   access="R/W"),
    Register(5093, "ON grid detection threshold",                                  "uint16", 1,   "W",    default=0,     access="R/W"),
    Register(5096, "EVCS warnings L",                                              "uint16", 1,   "",     default=0),
    Register(5097, "EVCS warnings H",                                              "uint16", 1,   "",     default=0),
    Register(5098, "EVCS notification code",                                       "uint16", 1,   "",     default=0),
    Register(5099, "External lock",                                                "uint16", 1,   "",     default=0,     access="R/W"),
    Register(5100, "Multiple relay charging",                                      "uint16", 1,   "",     default=0,     access="R/W"),
    Register(5101, "Multiple relay charging. Relays switching delay",              "uint16", 1,   "s",    default=10,    access="R/W"),
    Register(5102, "Allow battery/grid power for auto mode",                       "uint16", 1,   "",     default=0,     access="R/W"),
    Register(5103, "Battery/grid power timeout",                                   "uint16", 1,   "min",  default=30,    access="R/W"),
    Register(5104, "Overload protection",                                          "uint16", 1,   "",     default=0,     access="R/W"),
    Register(5105, "Input current limit",                                          "uint16", 10,  "A",    default=135,   access="R/W"),
    Register(5106, "Overload protection ON/OFF timeout",                           "uint16", 1,   "s",    default=10,    access="R/W"),
    Register(5107, "Overload protection cut-off timeout",                          "uint16", 1,   "s",    default=5,     access="R/W"),
    Register(5108, "Relays OFF delay",                                             "uint16", 1,   "ms",   default=2000,  access="R/W"),
    Register(5110, "Randomized delay max",                                         "uint16", 1,   "",     default=600,   access="R/W"),
    Register(5114, "Last reboot reason code",                                      "uint16", 1,   ""),
    Register(5115, "Sys watchdog reboot counter",                                  "uint16", 1,   ""),
    Register(5116, "Sys watchdog last reboot reason code",                         "uint16", 1,   ""),
    Register(5117, "Relays statuses",                                              "uint16", 1,   ""),
    Register(5118, "Overload current decrease timeout",                            "uint16", 1,   "min",  default=5,     access="R/W"),
    Register(5119, "Overload current decrease counter",                            "uint16", 1,   "",     default=1,     access="R/W"),
    Register(5120, "Overload current decrease rate",                               "uint16", 1,   "%",    default=20,    access="R/W"),
    Register(5123, "Display temperature",                                          "uint16", 10,  "°C"),
    Register(5124, "Car connector temperature",                                    "uint16", 10,  "°C"),
    Register(5125, "Power meter temperature",                                      "uint16", 10,  "°C"),
    Register(5126, "Power control temperature",                                    "uint16", 10,  "°C"),
    Register(5128, "Allow low excess solar power for auto mode",                   "uint16", 1,   "",     default=0,     access="R/W"),
    Register(5129, "Charging current limit external",                              "uint16", 1,   "",     default=0,     access="R/W"),
    Register(5130, "Inverter overtemperature protection",                          "uint16", 1,   "",     default=1,     access="R/W"),
    Register(5131, "Inverter overtemperature protection. Charging current restore timeout", "uint16", 1, "s", default=60, access="R/W"),
    Register(5132, "Light ring brightness limit",                                  "uint16", 1,   "%",    default=100,   access="R/W"),
    Register(5133, "CP auto-calibration state",                                    "uint16", 1,   "",     default=1,     access="R/W"),
    Register(5134, "'Battery powered'. Low excess power threshold",                "uint16", 1,   "W",    default=500,   access="R/W"),
    Register(5135, "'Battery powered'. Emulated BKPB power",                      "int16",  1,   "W",    default=0,     access="R/W"),
    Register(5136, "'Battery powered'. Emulated BKPB SoC",                        "uint16", 1,   "%",    default=100,   access="R/W"),
    Register(5137, "'Battery powered'. 'feed in' detection",                       "uint16", 1,   "",     default=0,     access="R/W"),
    Register(5138, "'Battery powered'. BKPB SoC max",                             "uint16", 1,   "%",    default=99,    access="R/W"),
    Register(5139, "Multiple relay charging. Conditions check delay",              "uint16", 1,   "s",    default=10,    access="R/W"),
    Register(5140, "Online update feed",                                           "uint16", 1,   "",     default=0,     access="R/W"),
]

ALL_REGISTERS: list[Register | StringRegister] = sorted(
    list(REGISTERS) + list(_NEW_REGISTERS) + list(STRING_REGISTERS),
    key=lambda r: r.address,
)
