# Notes Display Design

**Date:** 2026-03-14
**Status:** Approved

## Goal

Add a `notes` field to register dataclasses (populated from the "Notes" column of the spec sheet) and expose it in the TUI via the `?` key, which opens a read-only modal showing the full notes text for the selected register.

## Current State

- `Register` has 7 fields: `address`, `name`, `data_type`, `scale`, `unit`, `default`, `access`
- `StringRegister` has 5 fields: `address`, `name`, `register_count`, `encoding`, `access`
- No notes text exists anywhere in the codebase
- The TUI (`tui.py`) has bindings for Ctrl+S, Ctrl+R, Ctrl+Q only

## Architecture

### Data Model (`registers.py`)

Add `notes: str = ""` as the last field on both dataclasses.

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
    notes: str = ""          # ← new 8th field

    def __post_init__(self) -> None:
        if self.scale <= 0:
            raise ValueError(f"scale must be > 0, got {self.scale!r}")
```

```python
@dataclass(frozen=True)
class StringRegister:
    address: int
    name: str
    register_count: int
    encoding: str = "utf-8"
    access: Literal["R", "R/W"] = "R"
    notes: str = ""          # ← new 6th field

    def __post_init__(self) -> None:
        if self.register_count <= 0:
            raise ValueError(f"register_count must be > 0, got {self.register_count!r}")
```

Default `""` keeps all existing constructors valid with no changes.

### Notes values

All notes are sourced from the "Notes" column of `docs/specs/EVCS-Modbus-TCP-register-list-v3.8.xlsx` (sheet "Holding registers"). Multi-line cell values are normalized: internal newlines replaced with ` / `.

Registers with `-` in the Notes column keep `notes=""`.

Notable non-trivial examples:
- `5009`: `"0 - manual, 1 - auto, 2 - scheduled"`
- `5015`: `"0 - disconnected, / 1 - connected, / 2 - charging, / 3 - charged, / 4 - waiting for sun, / ..."` (multi-line enum, newlines replaced with ` / `)
- `5024`: `"kWh*100. Formula to calculate final value: (Total energy H * 65536 + Total energy L) / 100 = kWh"`
- `5110`: `"Randomized delay max value. Only for UK profile. The delay is applied every time the charger is operated..."` (long single-line)

String registers:
- `StringRegister(5001, ...)`: `notes="6 registers, 12 characters"`
- `StringRegister(5027, ...)`: `notes="UTF-8 encoded string, 22 registers, 44 bytes"`

### TUI Changes (`tui.py`)

**Key binding**: `?` → `action_show_notes()`

Add to `BINDINGS`:
```python
Binding("question_mark", "show_notes", "Notes", show=True),
```

**`action_show_notes()`**: Gets the register for the currently highlighted row. Use `table.cursor_row_key.value` (a `str` like `"5009"`) to look up the register in `_reg_by_key`. Call `self.push_screen(NotesModal(reg))` with no callback (the modal only dismisses, no return value is needed).

**`NotesModal(ModalScreen[None])`**: Read-only modal (no return value; Escape calls `self.dismiss()` with no argument).
- Title line: `"[bold]{reg.name}[/bold]  [{reg.address}]"`
- Body: `reg.notes` if non-empty, else `"No notes available for this register."`
- Escape dismisses (only action needed)

```
┌─ Notes ──────────────────────────────────────┐
│ Charge mode  [5009]                          │
│                                              │
│ 0 - manual, 1 - auto, 2 - scheduled         │
│                                              │
│ Esc to close                                 │
└──────────────────────────────────────────────┘
```

## Testing

### `tests/test_registers.py` additions (5 tests)

- `test_register_notes_defaults_to_empty` — `Register(...)` without `notes=` has `.notes == ""`
- `test_register_notes_value` — `Register(..., notes="0 - stop, 1 - start")` has correct `.notes`
- `test_string_register_notes_defaults_to_empty` — `StringRegister(...)` without `notes=` has `.notes == ""`
- `test_charge_mode_notes` — `REGISTERS` entry at address 5009 has `.notes == "0 - manual, 1 - auto, 2 - scheduled"`
- `test_serial_id_notes` — `STRING_REGISTERS` entry at address 5001 has `.notes == "6 registers, 12 characters"`

### `tests/test_tui.py` additions (3 tests)

Each test constructs its registers inline (no shared fixture needed):

- `test_tui_question_mark_shows_notes_modal` — register with `notes="0 - manual, 1 - auto, 2 - scheduled"`, press `?` → `len(screen_stack) == 2`
- `test_tui_notes_modal_shows_text` — same register, press `?`, query all `Label` widgets in current screen → text contains `"0 - manual, 1 - auto, 2 - scheduled"`
- `test_tui_notes_modal_no_notes_shows_placeholder` — register with `notes=""`, press `?` → text contains `"No notes available"`

## Files Touched

| File | Change |
|------|--------|
| `registers.py` | Add `notes` field to `Register` and `StringRegister`; populate values |
| `tui.py` | Add `NotesModal`, `?` binding, `action_show_notes()` |
| `tests/test_registers.py` | 2 new tests |
| `tests/test_tui.py` | 3 new tests |

## Out of Scope

- Notes in the CLI table output
- Searching/filtering by notes content
- Editing notes
