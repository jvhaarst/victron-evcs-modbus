"""Category definitions for Victron EVCS holding registers.

Maps category names to lists of register addresses. Registers may appear
in multiple categories. Categories are separate from register definitions.
"""

CATEGORIES: dict[str, list[int]] = {
    "status": [
        5009,  # Charge mode
        5010,  # Start/stop charging
        5011,  # L1 power used
        5012,  # L2 power used
        5013,  # L3 power used
        5014,  # Total power
        5015,  # Charger status
        5016,  # Charging current
        5017,  # Max current
        5018,  # Charging current actual
        5094,  # EVCS errors L
        5095,  # EVCS errors H
        5096,  # EVCS warnings L
        5097,  # EVCS warnings H
        5098,  # EVCS notification code
        5099,  # External lock
        5109,  # Detected car phases
        5117,  # Relays statuses
    ],
    "session": [
        5019,  # Session charging time H
        5020,  # Session charging time L
        5021,  # Session energy
        5022,  # Session cost
        5023,  # Total energy H
        5024,  # Total energy L
        5141,  # Session saved cost
    ],
    "device": [
        5000,  # Product ID
        5001,  # Serial Id
        5007,  # FW version H
        5008,  # FW version L
        5027,  # Device name
        5049,  # Charger autostart
        5050,  # Control via display
        5051,  # Display active backlight
        5052,  # Display idle backlight
        5053,  # Display active timeout
        5113,  # Reboot counter
        5114,  # Last reboot reason code
        5132,  # Light ring brightness limit
    ],
    "config": [
        5026,  # Charger position
        5054,  # Contactor active when charged
        5055,  # Manual mode phase
        5056,  # Auto mode phase
        5057,  # Power for 3phase
        5058,  # Power for single phase
        5059,  # Phase switching timeout
        5062,  # Min current
        5063,  # Power calibration offset
        5064,  # EVCS reset
        5065,  # Auto mode type
        5099,  # External lock
        5100,  # Multiple relay charging
        5101,  # Multiple relay charging. Relays switching delay
        5102,  # Allow battery/grid power for auto mode
        5103,  # Battery/grid power timeout
        5104,  # Overload protection
        5105,  # Input current limit
        5106,  # Overload protection ON/OFF timeout
        5107,  # Overload protection cut-off timeout
        5108,  # Relays OFF delay
        5110,  # Randomized delay max
        5128,  # Allow low excess solar power for auto mode
        5129,  # Charging current limit external
        5130,  # Inverter overtemperature protection
        5131,  # Inverter overtemperature protection. Charging current restore timeout
        5133,  # CP auto-calibration state
        5139,  # Multiple relay charging. Conditions check delay
        5142,  # Energy price per kWh H
        5143,  # Energy price per kWh L
    ],
    "auto_mode": [
        5065,  # Auto mode type
        5066,  # Backup battery SOC for start charging in Battery powered
        5067,  # Backup battery min SOC to allow charging if OFF Grid
        5068,  # Backup battery emulation
        5069,  # 'Feed in'. Start delay
        5070,  # 'Feed in'. Stop delay
        5071,  # 'Feed in'. Single phase. Grid power for start
        5072,  # 'Feed in'. Multi phase. Grid power for start
        5073,  # 'Feed in'. Grid power threshold for increase
        5074,  # 'Feed in'. Grid power threshold for decrease
        5075,  # 'Feed in'. Backup battery discharging power threshold
        5076,  # 'Feed in'. Current step
        5077,  # 'Feed in'. Time step
        5078,  # 'Battery powered'. Start delay min
        5079,  # 'Battery powered'. Stop delay
        5080,  # 'Battery powered'. Start abort delay
        5081,  # 'Battery powered'. BKPB balance power
        5082,  # 'Battery powered'. BKPB balance SOC max
        5083,  # 'Battery powered'. Available sun power threshold for start
        5084,  # 'Battery powered'. Grid power threshold for start
        5085,  # 'Battery powered'. BKPB power threshold for decrease
        5086,  # 'Battery powered'. Grid power threshold for decrease
        5087,  # 'Battery powered'. Discharging detect timeout
        5088,  # 'Battery powered'. Next try timeout for increase
        5089,  # 'Battery powered'. Time step
        5090,  # 'Battery powered'. Current step
        5091,  # 'Battery powered'. Grid power for 'feed in' detection
        5092,  # 'Battery powered'. Start delay max
        5093,  # ON grid detection threshold
        5134,  # 'Battery powered'. Low excess power threshold
        5135,  # 'Battery powered'. Emulated BKPB power
        5136,  # 'Battery powered'. Emulated BKPB SoC
        5137,  # 'Battery powered'. 'feed in' detection
        5138,  # 'Battery powered'. BKPB SoC max
    ],
    "sensors": [
        5121,  # Onboard humidity
        5122,  # Onboard temperature
        5123,  # Display temperature
        5124,  # Car connector temperature
        5125,  # Power meter temperature
        5126,  # Power control temperature
        5127,  # Power supply temperature
    ],
    "diagnostics": [
        5025,  # CP voltage
        5060,  # CP Calibration command
        5061,  # CP Calibration status
        5111,  # UP-time H
        5112,  # UP-time L
        5113,  # Reboot counter
        5114,  # Last reboot reason code
        5115,  # Sys watchdog reboot counter
        5116,  # Sys watchdog last reboot reason code
        5117,  # Relays statuses
        5118,  # Overload current decrease timeout
        5119,  # Overload current decrease counter
        5120,  # Overload current decrease rate
    ],
}
