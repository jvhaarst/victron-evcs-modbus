# Notes Display Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `notes` field to register dataclasses (from the spec sheet "Notes" column) and expose it in the TUI via `?`, which opens a read-only modal.

**Architecture:** `notes: str = ""` added as last field on `Register` and `StringRegister`; values hardcoded from xlsx extraction. `tui.py` gains a `NotesModal` and a `?` binding.

**Tech Stack:** Python 3.12, Textual 8.1.1 (ModalScreen pattern already used for EditModal/ConfirmModal)

---

## Chunk 1: registers.py — notes field and values

### Task 1: Add notes field to dataclasses and populate all register entries

**Files:**
- Modify: `registers.py`
- Modify: `tests/test_registers.py`

- [ ] **Step 1: Write failing tests**

The import line in `tests/test_registers.py` already includes all needed names — no change required.

Add to the end of the file:

```python
def test_register_notes_defaults_to_empty():
    reg = Register(5000, "Test", "uint16", 1, "")
    assert reg.notes == ""


def test_register_notes_value():
    reg = Register(5000, "Test", "uint16", 1, "", notes="0 - stop, 1 - start")
    assert reg.notes == "0 - stop, 1 - start"


def test_string_register_notes_defaults_to_empty():
    reg = StringRegister(5001, "Test", 6)
    assert reg.notes == ""


def test_charge_mode_notes():
    reg = next(r for r in REGISTERS if r.address == 5009)
    assert reg.notes == "0 - manual, 1 - auto, 2 - scheduled"


def test_serial_id_notes():
    reg = next(r for r in STRING_REGISTERS if r.address == 5001)
    assert reg.notes == "6 registers, 12 characters"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_registers.py::test_register_notes_defaults_to_empty tests/test_registers.py::test_charge_mode_notes -v
```

Expected: FAIL — `Register` has no `notes` attribute.

- [ ] **Step 3: Add notes field to both dataclasses**

In `registers.py`, add `notes: str = ""` as the **last** field on `Register`:

```python
@dataclass(frozen=True)
class Register:
    address: int
    name: str
    data_type: Literal["uint16", "int16"]
    scale: int
    unit: str
    default: Optional[int] = None
    access: Literal["R", "R/W"] = "R"
    notes: str = ""

    def __post_init__(self) -> None:
        if self.scale <= 0:
            raise ValueError(f"scale must be > 0, got {self.scale!r}")
```

And add `notes: str = ""` as the **last** field on `StringRegister`:

```python
@dataclass(frozen=True)
class StringRegister:
    address: int
    name: str
    register_count: int
    encoding: str = "utf-8"
    access: Literal["R", "R/W"] = "R"
    notes: str = ""

    def __post_init__(self) -> None:
        if self.register_count <= 0:
            raise ValueError(f"register_count must be > 0, got {self.register_count!r}")
```

- [ ] **Step 4: Run tests to verify field addition passes**

```bash
uv run pytest tests/test_registers.py::test_register_notes_defaults_to_empty tests/test_registers.py::test_string_register_notes_defaults_to_empty -v
```

Expected: PASS

- [ ] **Step 5: Populate notes values in REGISTERS**

Update entries in `REGISTERS` to add `notes=` where the spec has non-`-` values. The complete set of updates (only entries that change):

```python
REGISTERS = [
    Register(5000, "Product ID",                  "uint16", 1,   "",        notes="0xc024 or 0xc025 or 0xc026 - const"),
    Register(5007, "FW version H",                "uint16", 1,   "",        notes="HH: major number (8bit)"),
    Register(5008, "FW version L",                "uint16", 1,   "",        notes="MM: minor number(8bit), LL: revision number(8bit)"),
    Register(5009, "Charge mode",                 "uint16", 1,   "",        default=0,  access="R/W", notes="0 - manual, 1 - auto, 2 - scheduled"),
    Register(5010, "Start/stop charging",         "uint16", 1,   "",                    access="R/W", notes="0 - stop, 1 - start"),
    Register(5011, "L1 power used",               "uint16", 1,   "W",       notes="W"),
    Register(5012, "L2 power used",               "uint16", 1,   "W",       notes="W"),
    Register(5013, "L3 power used",               "uint16", 1,   "W",       notes="W"),
    Register(5014, "Total power",                 "uint16", 1,   "W",       notes="W"),
    Register(5015, "Charger status",              "uint16", 1,   "",        notes="0 - disconnected, / 1 - connected, / 2 - charging, / 3 - charged, / 4 - waiting for sun, / 5 - waiting for RFID, / 6 - waiting for start, / 7 - low SOC, / 8 - ground test error, / 9 - welded contacts test error, / 10 - CP input test error (shorted) / 11 - Residual current detected / 12 - Undervoltage detected / 13 - Overvoltage detected / 14 - Overheating detected / 15 - Reserved / 16 - Reserved / 17 - Reserved / 18 - Reserved / 19 - Reserved / 20 - Charging limit / 21 - start charging / 22 - switching to 3 phase / 23 - switching to 1 phase / 24 - stop charging"),
    Register(5016, "Charging current",            "uint16", 1,   "A",       default=6,  access="R/W", notes="A (for manual mode)"),
    Register(5017, "Max current",                 "uint16", 1,   "A",       default=10, access="R/W", notes="A"),
    Register(5018, "Charging current actual",     "uint16", 10,  "A",       notes="A*10 (actual value of current)"),
    Register(5019, "Session charging time H",     "uint16", 1,   "s",       notes="s"),
    Register(5020, "Session charging time L",     "uint16", 1,   "s",       notes="s"),
    Register(5021, "Session energy",              "uint16", 100, "kWh",     notes="kWh*100"),
    Register(5022, "Session cost",                "uint16", 100, "currency",notes="currency*100"),
    Register(5023, "Total energy H",              "uint16", 1,   "kWh",     notes="kWh*100"),
    Register(5024, "Total energy L",              "uint16", 100, "kWh",     notes="kWh*100. Formula to calculate final value: (Total energy H * 65536 + Total energy L) / 100 = kWh"),
    Register(5025, "CP voltage",                  "uint16", 100, "V",       notes="V*100"),
    Register(5026, "Charger position",            "uint16", 1,   "",        default=0,  access="R/W", notes="0 - Inverter Ac Out, 1 - Inverter Ac Input"),
    Register(5049, "Charger autostart",           "uint16", 1,   "",        default=1,  access="R/W", notes="0 - autostart disabled, 1 - autostart enabled"),
    Register(5050, "Control via display",         "uint16", 1,   "",        default=1,  access="R/W", notes="0 - control disabled, 1 - control enabled"),
    Register(5062, "Min current",                 "uint16", 1,   "A",       default=6,  access="R/W", notes="A"),
    Register(5094, "EVCS errors L",               "uint16", 1,   "",        default=0,  notes="Bitmask for EVCS errors. 1 - active, 0 - not active. Low part."),
    Register(5095, "EVCS errors H",               "uint16", 1,   "",        default=0,  notes="Bitmask for EVCS errors. 1 - active, 0 - not active. High part"),
    Register(5109, "Detected car phases",         "uint16", 1,   "",        default=1,  notes="Detected car phases. Updated during car charging. Reset to 1 after car disconnect"),
    Register(5111, "UP-time H",                   "uint16", 1,   "s",       notes="UP-time in seconds. High part"),
    Register(5112, "UP-time L",                   "uint16", 1,   "s",       notes="UP-time in seconds. Low part"),
    Register(5113, "Reboot counter",              "uint16", 1,   "",        notes="Reboot counter"),
    Register(5121, "Onboard humidity",            "uint16", 10,  "%",       notes="%*10. for v2 only"),
    Register(5122, "Onboard temperature",         "uint16", 10,  "°C",      notes="°C*10. for v2 only"),
    Register(5127, "Power supply temperature",    "uint16", 10,  "°C",      default=0,  notes="°C*10"),
]
```

- [ ] **Step 6: Populate notes values in _NEW_REGISTERS**

Update the entries in `_NEW_REGISTERS`. Only showing entries that gain `notes=` (maintain all existing fields):

```python
_NEW_REGISTERS: list[Register] = [
    Register(5051, "Display active backlight",          "uint16", 1, "%",  default=100, access="R/W", notes="%"),
    Register(5052, "Display idle backlight",            "uint16", 1, "%",  default=7,   access="R/W", notes="%"),
    Register(5053, "Display active timeout",            "uint16", 1, "s",  default=120, access="R/W", notes="s"),
    Register(5054, "Contactor active when charged",     "uint16", 1, "",   default=0,   access="R/W", notes="0 - contactor disabled, 1 - contactor enabled"),
    Register(5055, "Manual mode phase",                 "uint16", 1, "",   default=1,   access="R/W", notes="0 - 3Phase, 1 - Single Phase. Related to 'multiple relay charging' feature."),
    Register(5056, "Auto mode phase",                   "uint16", 1, "",   default=1,   access="R/W", notes="0 - 3Phase, 1 - Single Phase, 2 - Single+3Phase. Related to 'multiple relay charging' feature."),
    Register(5057, "Power for 3phase",                  "uint16", 1, "W",  default=4800,access="R/W", notes="W. Related to 'multiple relay charging' feature."),
    Register(5058, "Power for single phase",            "uint16", 1, "W",  default=4300,access="R/W", notes="W. Related to 'multiple relay charging' feature."),
    Register(5059, "Phase switching timeout",           "uint16", 1, "s",  default=60,  access="R/W", notes="s. Related to 'multiple relay charging' feature."),
    Register(5060, "CP Calibration command",            "uint16", 1, "",               access="R/W", notes="1 - calibration start / 2 - car is connected / 3 - reserved / 4 - calibration abort"),
    Register(5061, "CP Calibration status",             "uint16", 1, "",               notes="0 - idle / 1 - in progress / 2 - successfully / 3 - failed / 4 - aborted"),
    Register(5063, "Power calibration offset",          "uint16", 1, "",   default=100, access="R/W", notes="From 0.6 to 1.4 multiplied by 100"),
    Register(5064, "EVCS reset",                        "uint16", 1, "",               access="R/W", notes="1 - reset command for EVCS"),
    Register(5065, "Auto mode type",                    "uint16", 1, "",   default=1,   access="R/W", notes="0 - Feed in, 1 - Battery powered"),
    Register(5066, "Backup battery SOC for start charging in Battery powered", "uint16", 1, "%", default=90, access="R/W", notes="%"),
    Register(5067, "Backup battery min SOC to allow charging if OFF Grid",     "uint16", 1, "%", default=20, access="R/W", notes="%"),
    Register(5068, "Backup battery emulation",          "uint16", 1, "",   default=0,   access="R/W", notes="0 - disabled, 1 - enabled"),
    Register(5069, "'Feed in'. Start delay",            "uint16", 1, "s",  default=30,  access="R/W", notes="s"),
    Register(5070, "'Feed in'. Stop delay",             "uint16", 1, "s",  default=60,  access="R/W", notes="s"),
    Register(5071, "'Feed in'. Single phase. Grid power for start",           "int16",  1, "W",  default=-500,  access="R/W", notes="W"),
    Register(5072, "'Feed in'. Multi phase. Grid power for start",            "int16",  1, "W",  default=-1400, access="R/W", notes="W"),
    Register(5073, "'Feed in'. Grid power threshold for increase",            "int16",  1, "W",  default=-250,  access="R/W", notes="W"),
    Register(5074, "'Feed in'. Grid power threshold for decrease",            "int16",  1, "W",  default=250,   access="R/W", notes="W"),
    Register(5075, "'Feed in'. Backup battery discharging power threshold",   "int16",  1, "W",  default=-100,  access="R/W", notes="W"),
    Register(5076, "'Feed in'. Current step",           "uint16", 10, "A", default=2,   access="R/W", notes="A*10"),
    Register(5077, "'Feed in'. Time step",              "uint16", 1, "ms", default=1000,access="R/W", notes="ms"),
    Register(5078, "'Battery powered'. Start delay min","uint16", 1, "s",  default=30,  access="R/W", notes="s"),
    Register(5079, "'Battery powered'. Stop delay",     "uint16", 1, "s",  default=60,  access="R/W", notes="s"),
    Register(5080, "'Battery powered'. Start abort delay",                    "uint16", 1, "s",  default=10,  access="R/W", notes="s"),
    Register(5081, "'Battery powered'. BKPB balance power",                   "uint16", 1, "W",  default=500, access="R/W", notes="W"),
    Register(5082, "'Battery powered'. BKPB balance SOC max",                 "uint16", 1, "%",  default=80,  access="R/W", notes="%"),
    Register(5083, "'Battery powered'. Available sun power threshold for start","uint16",1, "W",  default=100, access="R/W", notes="W"),
    Register(5084, "'Battery powered'. Grid power threshold for start",       "uint16", 1, "W",  default=25,  access="R/W", notes="W"),
    Register(5085, "'Battery powered'. BKPB power threshold for decrease",    "uint16", 1, "W",  default=400, access="R/W", notes="W"),
    Register(5086, "'Battery powered'. Grid power threshold for decrease",    "uint16", 1, "W",  default=400, access="R/W", notes="W"),
    Register(5087, "'Battery powered'. Discharging detect timeout",           "uint16", 1, "s",  default=7,   access="R/W", notes="s"),
    Register(5088, "'Battery powered'. Next try timeout for increase",        "uint16", 1, "s",  default=45,  access="R/W", notes="s"),
    Register(5089, "'Battery powered'. Time step",                            "uint16", 1, "s",  default=15,  access="R/W", notes="s"),
    Register(5090, "'Battery powered'. Current step",                         "uint16", 10, "A", default=10,  access="R/W", notes="A*10"),
    Register(5091, "'Battery powered'. Grid power for 'feed in' detection",   "int16",  1, "W",  default=-1500,access="R/W", notes="W"),
    Register(5092, "'Battery powered'. Start delay max",                      "uint16", 1, "s",  default=300, access="R/W", notes="s"),
    Register(5093, "ON grid detection threshold",       "uint16", 1, "W",  default=0,   access="R/W", notes="W"),
    Register(5096, "EVCS warnings L",                   "uint16", 1, "",   default=0,   notes="Bitmask for EVCS warnings. 1 - active, 0 - not active. Low part."),
    Register(5097, "EVCS warnings H",                   "uint16", 1, "",   default=0,   notes="Bitmask for EVCS warnings. 1 - active, 0 - not active. High part"),
    Register(5098, "EVCS notification code",            "uint16", 1, "",   default=0,   notes="0 - no any notification, some value - EVCS notification code"),
    Register(5099, "External lock",                     "uint16", 1, "",   default=0,   access="R/W", notes="EVCS external lock(for grid operator)"),
    Register(5100, "Multiple relay charging",           "uint16", 1, "",   default=0,   access="R/W", notes="Multiple relay charging feature. 1 - enabled, 0 - disabled"),
    Register(5101, "Multiple relay charging. Relays switching delay",         "uint16", 1, "s",  default=10,  access="R/W", notes="s, related to 'multiple relay charging' feature"),
    Register(5102, "Allow battery/grid power for auto mode",                  "uint16", 1, "",   default=0,   access="R/W", notes="1 - enabled, 0 - disabled"),
    Register(5103, "Battery/grid power timeout",        "uint16", 1, "min",default=30,  access="R/W", notes="timeout in minutes"),
    Register(5104, "Overload protection",               "uint16", 1, "",   default=0,   access="R/W", notes="1 - enabled, 0 - disabled"),
    Register(5105, "Input current limit",               "uint16", 10, "A", default=135, access="R/W", notes="A*10. Applicable only if Charger position(5026) == 1(Inverter Ac Input)"),
    Register(5106, "Overload protection ON/OFF timeout","uint16", 1, "s",  default=10,  access="R/W", notes="s. Timeout before returning back charging"),
    Register(5107, "Overload protection cut-off timeout","uint16",1, "s",  default=5,   access="R/W", notes="s. Timeout before charging cut-off."),
    Register(5108, "Relays OFF delay",                  "uint16", 1, "ms", default=2000,access="R/W", notes="ms. Delay before all relays off"),
    Register(5110, "Randomized delay max",              "uint16", 1, "",   default=600, access="R/W", notes="Randomized delay max value. Only for UK profile. The delay is applied every time the charger is operated (either from a scheduled charge or manually initiated charge) and each time the rate of charge changes."),
    Register(5114, "Last reboot reason code",           "uint16", 1, "",   notes="Last reboot reason code"),
    Register(5115, "Sys watchdog reboot counter",       "uint16", 1, "",   notes="Sys watchdog reboot counter"),
    Register(5116, "Sys watchdog last reboot reason code","uint16",1, "",  notes="Sys watchdog last reboot reason code"),
    Register(5117, "Relays statuses",                   "uint16", 1, "",   notes="Bitmask. Bit0-L1, Bit1-L2, Bit2-L3, Bit3-N(for v2). Bit0-rl1, Bit2-rl2(for v1)"),
    Register(5118, "Overload current decrease timeout", "uint16", 1, "min",default=5,   access="R/W", notes="min. Timeout for current decrease"),
    Register(5119, "Overload current decrease counter", "uint16", 1, "",   default=1,   access="R/W", notes="Counter for current decrease"),
    Register(5120, "Overload current decrease rate",    "uint16", 1, "%",  default=20,  access="R/W", notes="Rate in % for current decrease"),
    Register(5123, "Display temperature",               "uint16", 10, "°C",notes="°C*10. for v2 only"),
    Register(5124, "Car connector temperature",         "uint16", 10, "°C",notes="°C*10. for v2 only"),
    Register(5125, "Power meter temperature",           "uint16", 10, "°C",notes="°C*10. for v2 only"),
    Register(5126, "Power control temperature",         "uint16", 10, "°C",notes="°C*10. for v2 only"),
    Register(5128, "Allow low excess solar power for auto mode",              "uint16", 1, "",   default=0,   access="R/W", notes="1 - enabled, 0 - disabled"),
    Register(5129, "Charging current limit external",   "uint16", 1, "",   default=0,   access="R/W", notes="External limit for charging current. 0 - no limits. 1 - charging current limited to 6A"),
    Register(5130, "Inverter overtemperature protection","uint16",1, "",   default=1,   access="R/W", notes="1 - enabled, 0 - disabled"),
    Register(5131, "Inverter overtemperature protection. Charging current restore timeout", "uint16", 1, "s", default=60, access="R/W", notes="s. Timeout for restoring the original charging current back."),
    Register(5132, "Light ring brightness limit",       "uint16", 1, "%",  default=100, access="R/W", notes="in %. 0 - the light ring will be OFF, 100% - no limits, brightness will be according to scene configurations."),
    Register(5133, "CP auto-calibration state",         "uint16", 1, "",   default=1,   access="R/W", notes="1 - enabled, 0 - disabled"),
    Register(5134, "'Battery powered'. Low excess power threshold",           "uint16", 1, "W",  default=500, access="R/W", notes="W"),
    Register(5135, "'Battery powered'. Emulated BKPB power",                  "int16",  1, "W",  default=0,   access="R/W", notes="W"),
    Register(5136, "'Battery powered'. Emulated BKPB SoC",                   "uint16", 1, "%",  default=100, access="R/W", notes="%"),
    Register(5137, "'Battery powered'. 'feed in' detection",                  "uint16", 1, "",   default=0,   access="R/W", notes="1 - enabled, 0 - disabled"),
    Register(5138, "'Battery powered'. BKPB SoC max",                         "uint16", 1, "%",  default=99,  access="R/W", notes="%"),
    Register(5139, "Multiple relay charging. Conditions check delay",         "uint16", 1, "s",  default=10,  access="R/W", notes="s, related to 'multiple relay charging' feature"),
    Register(5140, "Online update feed",                "uint16", 1, "",   default=0,   access="R/W", notes="0 - Official release, 1 - Beta release"),
]
```

- [ ] **Step 7: Populate notes values in STRING_REGISTERS**

```python
STRING_REGISTERS: list[StringRegister] = [
    StringRegister(5001, "Serial Id",    6,  notes="6 registers, 12 characters"),
    StringRegister(5027, "Device name", 22, access="R/W", notes="UTF-8 encoded string, 22 registers, 44 bytes"),
]
```

- [ ] **Step 8: Run all register tests**

```bash
uv run pytest tests/test_registers.py -v
```

Expected: All existing tests plus 5 new ones PASS.

- [ ] **Step 9: Run full test suite to verify no regressions**

```bash
uv run pytest -q
```

Expected: All tests PASS.

- [ ] **Step 10: Commit**

```bash
git add registers.py tests/test_registers.py
git commit -m "feat: add notes field to Register and StringRegister, populate from spec"
```

---

## Chunk 2: tui.py — NotesModal and ? binding

### Task 2: Add NotesModal and action_show_notes to the TUI

**Files:**
- Modify: `tui.py`
- Modify: `tests/test_tui.py`

- [ ] **Step 1: Write failing tests**

Add to the end of `tests/test_tui.py`:

```python
@pytest.mark.asyncio
async def test_tui_question_mark_shows_notes_modal(mock_client):
    from tui import RegisterEditorApp
    reg = Register(5009, "Charge mode", "uint16", 1, "", default=0, access="R/W",
                   notes="0 - manual, 1 - auto, 2 - scheduled")
    registers = [reg]
    values = {5009: 0}
    async with RegisterEditorApp(mock_client, registers, values).run_test() as pilot:
        await pilot.press("question_mark")
        await pilot.pause()
        assert len(pilot.app.screen_stack) == 2  # notes modal pushed


@pytest.mark.asyncio
async def test_tui_notes_modal_shows_text(mock_client):
    from tui import RegisterEditorApp
    reg = Register(5009, "Charge mode", "uint16", 1, "", default=0, access="R/W",
                   notes="0 - manual, 1 - auto, 2 - scheduled")
    registers = [reg]
    values = {5009: 0}
    async with RegisterEditorApp(mock_client, registers, values).run_test() as pilot:
        await pilot.press("question_mark")
        await pilot.pause()
        from textual.widgets import Label
        labels = pilot.app.screen.query(Label)
        text = " ".join(str(label.renderable) for label in labels)
        assert "0 - manual, 1 - auto, 2 - scheduled" in text


@pytest.mark.asyncio
async def test_tui_notes_modal_no_notes_shows_placeholder(mock_client):
    from tui import RegisterEditorApp
    reg = Register(5000, "Product ID", "uint16", 1, "", notes="")
    registers = [reg]
    values = {5000: 49189}
    async with RegisterEditorApp(mock_client, registers, values).run_test() as pilot:
        await pilot.press("question_mark")
        await pilot.pause()
        from textual.widgets import Label
        labels = pilot.app.screen.query(Label)
        text = " ".join(str(label.renderable) for label in labels)
        assert "No notes available" in text
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_tui.py::test_tui_question_mark_shows_notes_modal -v
```

Expected: FAIL — no `question_mark` binding.

- [ ] **Step 3: Add NotesModal and action_show_notes to tui.py**

Add `NotesModal` class after `ConfirmModal` (before `RegisterEditorApp`):

```python
class NotesModal(ModalScreen[None]):
    """Read-only modal displaying notes for a register."""

    BINDINGS = [Binding("escape", "dismiss", "Close", show=False)]

    DEFAULT_CSS = """
    NotesModal {
        align: center middle;
    }
    #notes-dialog {
        background: $panel;
        border: tall $primary;
        padding: 1 2;
        width: 70;
        height: auto;
        max-height: 80vh;
    }
    #notes-hint {
        margin-top: 1;
        color: $text-muted;
    }
    """

    def __init__(self, reg: Register | StringRegister) -> None:
        super().__init__()
        self.reg = reg

    def compose(self) -> ComposeResult:
        text = self.reg.notes if self.reg.notes else "No notes available for this register."
        with Vertical(id="notes-dialog"):
            yield Label(f"[bold]{self.reg.name}[/bold]  [{self.reg.address}]")
            yield Label(text, id="notes-text")
            yield Label("Esc to close", id="notes-hint")
```

Add `?` binding to `RegisterEditorApp.BINDINGS`:

```python
BINDINGS = [
    Binding("ctrl+s", "write_all", "Write", show=True),
    Binding("ctrl+r", "refresh_registers", "Refresh", show=True),
    Binding("ctrl+q", "quit_app", "Quit", show=True),
    Binding("question_mark", "show_notes", "Notes", show=True),
]
```

Add `action_show_notes` method to `RegisterEditorApp` (after `action_quit_app`):

```python
def action_show_notes(self) -> None:
    table = self.query_one(DataTable)
    key = table.cursor_row_key.value  # str like "5009"
    reg = self._reg_by_key.get(key)
    if reg is None:
        return
    self.push_screen(NotesModal(reg))
```

**Note on DataTable cursor:** `table.cursor_row_key` is a `RowKey` object; `.value` gives the string key passed to `add_row(key=...)`. This is the same key format used in `_reg_by_key` (`str(reg.address)`).

- [ ] **Step 4: Run the new TUI tests**

```bash
uv run pytest tests/test_tui.py::test_tui_question_mark_shows_notes_modal tests/test_tui.py::test_tui_notes_modal_shows_text tests/test_tui.py::test_tui_notes_modal_no_notes_shows_placeholder -v
```

Expected: All 3 PASS.

- [ ] **Step 5: Run full test suite**

```bash
uv run pytest -q
```

Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add tui.py tests/test_tui.py
git commit -m "feat: add NotesModal and ? binding to TUI for register notes display"
```

- [ ] **Step 7: Push**

```bash
git push
```
