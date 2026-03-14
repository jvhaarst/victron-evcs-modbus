# Range Validation Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Validate user-supplied write values against the device's documented register range before sending to the device, rejecting out-of-range values with a descriptive error.

**Architecture:** Add `range: tuple[float, float] | None = None` to `Register` (after `notes`). Values are display floats (raw ÷ scale). `validate_write_value()` in `cli.py` checks the range after parsing display_val and before multiplying by scale. 59 R/W registers receive range tuples; the rest remain `None`.

**Tech Stack:** Python 3.12, frozen dataclasses, pytest

---

## Chunk 1: Add range field + validation logic

### Task 1: Add range field to Register, add range check to validate_write_value(), add 6 tests

**Files:**
- Modify: `registers.py` (add `range` field to `Register` dataclass)
- Modify: `cli.py` (add range check in `validate_write_value()`)
- Modify: `tests/test_cli.py` (6 new tests)

**Background for the implementer:**
- `registers.py` has a frozen dataclass `Register` starting at line 9. Add `range: tuple[float, float] | None = None` as the last field, after `notes: str = ""`. The `# noqa: A003` comment suppresses the linter warning about shadowing the built-in `range` — include it.
- `cli.py` has `validate_write_value()` at line 178. After `display_val = float(input_str)` (line 195), add the range check before `raw = round(display_val * reg.scale)` (line 198).
- Existing tests construct `Register(...)` without a `range` parameter — they continue to work because `range` defaults to `None`. No existing tests need changes.

- [ ] **Step 1: Write 6 new failing tests**

Add after `test_validate_write_value_string_too_long` (after line 315) in `tests/test_cli.py`:

```python
# --- validate_write_value range tests ---

def test_validate_write_value_range_ok():
    reg = Register(5016, "Charging current", "uint16", 1, "A", access="R/W", range=(6.0, 32.0))
    assert validate_write_value(reg, "10") == 10


def test_validate_write_value_range_boundary_low():
    reg = Register(5016, "Charging current", "uint16", 1, "A", access="R/W", range=(6.0, 32.0))
    assert validate_write_value(reg, "6") == 6


def test_validate_write_value_range_boundary_high():
    reg = Register(5016, "Charging current", "uint16", 1, "A", access="R/W", range=(6.0, 32.0))
    assert validate_write_value(reg, "32") == 32


def test_validate_write_value_range_too_low():
    reg = Register(5016, "Charging current", "uint16", 1, "A", access="R/W", range=(6.0, 32.0))
    with pytest.raises(ValueError, match="out of range"):
        validate_write_value(reg, "5")


def test_validate_write_value_range_too_high():
    reg = Register(5016, "Charging current", "uint16", 1, "A", access="R/W", range=(6.0, 32.0))
    with pytest.raises(ValueError, match="out of range"):
        validate_write_value(reg, "33")


def test_validate_write_value_no_range():
    # range=None means no range constraint beyond type bounds
    reg = Register(5016, "Charging current", "uint16", 1, "A", access="R/W")
    assert validate_write_value(reg, "1000") == 1000
```

- [ ] **Step 2: Run new tests to verify they fail**

```bash
uv run pytest tests/test_cli.py::test_validate_write_value_range_ok tests/test_cli.py::test_validate_write_value_range_too_low -v
```

Expected: FAIL — `Register` does not accept `range` parameter.

- [ ] **Step 3: Add range field to Register dataclass**

In `registers.py`, replace the `Register` dataclass (lines 9–22):

```python
@dataclass(frozen=True)
class Register:
    address: int
    name: str
    data_type: Literal["uint16", "int16"]
    scale: int      # divide raw value by this to get real value; must be > 0
    unit: str       # display unit string
    default: Optional[int] = None  # factory default (None = no default in spec)
    access: Literal["R", "R/W"] = "R"
    notes: str = ""
    range: tuple[float, float] | None = None  # display-value range (raw ÷ scale); None = no constraint  # noqa: A003

    def __post_init__(self) -> None:
        if self.scale <= 0:
            raise ValueError(f"scale must be > 0, got {self.scale!r}")
```

- [ ] **Step 4: Add range check to validate_write_value()**

In `cli.py`, replace the body of `validate_write_value()` (lines 178–209) with:

```python
def validate_write_value(reg: Register | StringRegister, input_str: str) -> int | str:
    """Parse and validate a human-readable display value for writing to reg.

    For Register: parses as float, checks device range, multiplies by scale,
    rounds to int, validates type bounds. Returns raw int ready for write_register.
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
    if reg.range is not None:
        lo, hi = reg.range
        if not (lo <= display_val <= hi):
            raise ValueError(
                f"Value out of range: {display_val} is not between {lo} and {hi}"
            )
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
```

- [ ] **Step 5: Run all 6 new tests to verify they pass**

```bash
uv run pytest tests/test_cli.py::test_validate_write_value_range_ok tests/test_cli.py::test_validate_write_value_range_boundary_low tests/test_cli.py::test_validate_write_value_range_boundary_high tests/test_cli.py::test_validate_write_value_range_too_low tests/test_cli.py::test_validate_write_value_range_too_high tests/test_cli.py::test_validate_write_value_no_range -v
```

Expected: All 6 PASS.

- [ ] **Step 6: Run full test suite**

```bash
uv run pytest -q
```

Expected: All tests PASS (no regressions — existing tests construct `Register` without `range`, which defaults to `None`).

- [ ] **Step 7: Commit**

```bash
git add registers.py cli.py tests/test_cli.py
git commit -m "feat: add range field to Register, validate in validate_write_value()"
```

---

## Chunk 2: Populate range data

### Task 2: Add range tuples to 59 R/W registers in registers.py

**Files:**
- Modify: `registers.py` (add `range=` kwargs to matching `Register(...)` calls)

**Background for the implementer:**
- Registers live in two lists: `REGISTERS` (lines 25–59) and `_NEW_REGISTERS` (lines 81–162).
- Add `range=(lo, hi)` as the last keyword argument to each matching `Register(...)` call. Do not change any other fields.
- Range values are display floats (raw ÷ scale). For registers with scale=1, display == raw. For scale=10, divide by 10.
- 17 R/W registers are intentionally excluded (keep `range=None`, no change needed):

| Address | Name | Reason excluded |
|---------|------|-----------------|
| 5064 | EVCS reset | xlsx range `"1.0"` is a single value; this is a command register |
| 5071 | 'Feed in'. Single phase. Grid power for start | xlsx range `"-32768 to +32767"` = full int16 bounds, adds no constraint |
| 5072 | 'Feed in'. Multi phase. Grid power for start | same |
| 5073 | 'Feed in'. Grid power threshold for increase | same |
| 5074 | 'Feed in'. Grid power threshold for decrease | same |
| 5075 | 'Feed in'. Backup battery discharging power threshold | same |
| 5081 | 'Battery powered'. BKPB balance power | xlsx range `"0 to 65535"` = full uint16 bounds |
| 5083 | 'Battery powered'. Available sun power threshold for start | same |
| 5084 | 'Battery powered'. Grid power threshold for start | same |
| 5093 | ON grid detection threshold | same |
| 5108 | Relays OFF delay | xlsx range `"0 - 65535"` = full uint16 bounds |
| 5110 | Randomized delay max | same |
| 5128 | Allow low excess solar power for auto mode | same |
| 5129 | Charging current limit external | same |
| 5130 | Inverter overtemperature protection | same |
| 5131 | Inverter overtemperature protection. Charging current restore timeout | same |
| 5135 | 'Battery powered'. Emulated BKPB power | xlsx range `"-32768 to 32767"` = full int16 bounds |

**Complete address → range tuple mapping:**

**In REGISTERS (lines 25–59):**

| Address | Name | range |
|---------|------|-------|
| 5009 | Charge mode | `(0.0, 2.0)` |
| 5010 | Start/stop charging | `(0.0, 1.0)` |
| 5016 | Charging current | `(6.0, 32.0)` |
| 5017 | Max current | `(6.0, 32.0)` |
| 5026 | Charger position | `(0.0, 1.0)` |
| 5049 | Charger autostart | `(0.0, 1.0)` |
| 5050 | Control via display | `(0.0, 1.0)` |
| 5062 | Min current | `(6.0, 31.0)` |

**In _NEW_REGISTERS (lines 81–162):**

| Address | Name | range |
|---------|------|-------|
| 5051 | Display active backlight | `(1.0, 100.0)` |
| 5052 | Display idle backlight | `(1.0, 100.0)` |
| 5053 | Display active timeout | `(1.0, 65535.0)` |
| 5054 | Contactor active when charged | `(0.0, 1.0)` |
| 5055 | Manual mode phase | `(0.0, 1.0)` |
| 5056 | Auto mode phase | `(0.0, 2.0)` |
| 5057 | Power for 3phase | `(1.0, 65535.0)` |
| 5058 | Power for single phase | `(1.0, 65535.0)` |
| 5059 | Phase switching timeout | `(1.0, 65535.0)` |
| 5060 | CP Calibration command | `(1.0, 4.0)` |
| 5063 | Power calibration offset | `(60.0, 140.0)` |
| 5065 | Auto mode type | `(0.0, 1.0)` |
| 5066 | Backup battery SOC for start charging in Battery powered | `(1.0, 100.0)` |
| 5067 | Backup battery min SOC to allow charging if OFF Grid | `(1.0, 100.0)` |
| 5068 | Backup battery emulation | `(0.0, 1.0)` |
| 5069 | 'Feed in'. Start delay | `(1.0, 65535.0)` |
| 5070 | 'Feed in'. Stop delay | `(1.0, 65535.0)` |
| 5076 | 'Feed in'. Current step | `(0.1, 6553.5)` |
| 5077 | 'Feed in'. Time step | `(1.0, 65535.0)` |
| 5078 | 'Battery powered'. Start delay min | `(1.0, 65535.0)` |
| 5079 | 'Battery powered'. Stop delay | `(1.0, 65535.0)` |
| 5080 | 'Battery powered'. Start abort delay | `(1.0, 65535.0)` |
| 5082 | 'Battery powered'. BKPB balance SOC max | `(1.0, 100.0)` |
| 5085 | 'Battery powered'. BKPB power threshold for decrease | `(1.0, 65535.0)` |
| 5086 | 'Battery powered'. Grid power threshold for decrease | `(1.0, 65535.0)` |
| 5087 | 'Battery powered'. Discharging detect timeout | `(1.0, 65535.0)` |
| 5088 | 'Battery powered'. Next try timeout for increase | `(1.0, 65535.0)` |
| 5089 | 'Battery powered'. Time step | `(1.0, 65535.0)` |
| 5090 | 'Battery powered'. Current step | `(0.1, 6553.5)` |
| 5091 | 'Battery powered'. Grid power for 'feed in' detection | `(-32768.0, -1.0)` |
| 5092 | 'Battery powered'. Start delay max | `(1.0, 65535.0)` |
| 5099 | External lock | `(0.0, 1.0)` |
| 5100 | Multiple relay charging | `(0.0, 1.0)` |
| 5101 | Multiple relay charging. Relays switching delay | `(1.0, 65535.0)` |
| 5102 | Allow battery/grid power for auto mode | `(0.0, 1.0)` |
| 5103 | Battery/grid power timeout | `(5.0, 65535.0)` |
| 5104 | Overload protection | `(0.0, 1.0)` |
| 5105 | Input current limit | `(0.1, 6553.5)` |
| 5106 | Overload protection ON/OFF timeout | `(1.0, 65535.0)` |
| 5107 | Overload protection cut-off timeout | `(1.0, 65535.0)` |
| 5118 | Overload current decrease timeout | `(1.0, 65535.0)` |
| 5119 | Overload current decrease counter | `(1.0, 65535.0)` |
| 5120 | Overload current decrease rate | `(1.0, 65535.0)` |
| 5132 | Light ring brightness limit | `(0.0, 100.0)` |
| 5133 | CP auto-calibration state | `(0.0, 1.0)` |
| 5134 | 'Battery powered'. Low excess power threshold | `(1.0, 65535.0)` |
| 5136 | 'Battery powered'. Emulated BKPB SoC | `(0.0, 100.0)` |
| 5137 | 'Battery powered'. 'feed in' detection | `(0.0, 1.0)` |
| 5138 | 'Battery powered'. BKPB SoC max | `(1.0, 100.0)` |
| 5139 | Multiple relay charging. Conditions check delay | `(1.0, 65535.0)` |
| 5140 | Online update feed | `(0.0, 1.0)` |

**Example transformation** — before:
```python
Register(5016, "Charging current", "uint16", 1, "A", default=6, access="R/W", notes="A (for manual mode)"),
```

After:
```python
Register(5016, "Charging current", "uint16", 1, "A", default=6, access="R/W", notes="A (for manual mode)", range=(6.0, 32.0)),
```

- [ ] **Step 1: Add range tuples to the 8 registers in REGISTERS**

Open `registers.py`. Find each of the 8 addresses listed in the REGISTERS table above (5009, 5010, 5016, 5017, 5026, 5049, 5050, 5062) and append `, range=(lo, hi)` before the closing `)` of each `Register(...)` call, using the tuple from the table.

- [ ] **Step 2: Add range tuples to the 51 registers in _NEW_REGISTERS**

Find each of the 51 addresses listed in the _NEW_REGISTERS table above and append `, range=(lo, hi)` similarly.

- [ ] **Step 3: Run the full test suite**

```bash
uv run pytest -q
```

Expected: All tests PASS. The data-only changes add `range=` kwargs; no existing behavior changes.

- [ ] **Step 4: Verify count**

```bash
uv run python3 -c "
from registers import ALL_REGISTERS
from registers import Register
rw_with_range = [r for r in ALL_REGISTERS if isinstance(r, Register) and r.access == 'R/W' and r.range is not None]
print(f'R/W registers with range: {len(rw_with_range)}')
assert len(rw_with_range) == 59, f'Expected 59, got {len(rw_with_range)}'
print('OK')
"
```

Expected output:
```
R/W registers with range: 59
OK
```

- [ ] **Step 5: Commit**

```bash
git add registers.py
git commit -m "feat: populate range tuples for 59 R/W registers from xlsx spec"
```
