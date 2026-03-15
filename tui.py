"""Interactive TUI for browsing and editing Victron EVCS registers."""
from __future__ import annotations

from typing import Any

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Footer, Header, Input, Label

from modbus import read_registers, write_register
from registers import Register, StringRegister, format_value, validate_write_value


class EditModal(ModalScreen[int | str | None]):
    """Modal screen for editing a single register value."""

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    DEFAULT_CSS = """
    EditModal {
        align: center middle;
    }
    #edit-dialog {
        background: $panel;
        border: tall $primary;
        padding: 1 2;
        width: 60;
        height: auto;
    }
    #edit-hint {
        margin-top: 1;
        color: $text-muted;
    }
    """

    def __init__(self, reg: Register | StringRegister, current_display: str) -> None:
        super().__init__()
        self.reg = reg
        self.current_display = current_display

    def compose(self) -> ComposeResult:
        unit = getattr(self.reg, "unit", "")
        unit_str = f"  [{unit}]" if unit else ""
        with Vertical(id="edit-dialog"):
            yield Label(f"[bold]{self.reg.name}[/bold]{unit_str}")
            yield Label(f"Address: {self.reg.address}")
            yield Input(value=self.current_display, id="edit-input")
            yield Label("Enter to confirm  •  Esc to cancel", id="edit-hint")

    def on_mount(self) -> None:
        self.query_one("#edit-input", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        try:
            raw = validate_write_value(self.reg, event.value)
            self.dismiss(raw)
        except ValueError as e:
            self.query_one("#edit-hint", Label).update(f"[red]{e}[/red]")

    def action_cancel(self) -> None:
        self.dismiss(None)


class ConfirmModal(ModalScreen[str]):
    """Generic confirmation modal with configurable buttons."""

    DEFAULT_CSS = """
    ConfirmModal {
        align: center middle;
    }
    #confirm-dialog {
        background: $panel;
        border: tall $warning;
        padding: 1 2;
        width: 52;
        height: auto;
    }
    #confirm-buttons {
        margin-top: 1;
        height: auto;
        align: center middle;
    }
    Button {
        margin: 0 1;
    }
    """

    def __init__(self, message: str, buttons: list[str]) -> None:
        super().__init__()
        self.message = message
        self._buttons = buttons

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm-dialog"):
            yield Label(self.message)
            with Horizontal(id="confirm-buttons"):
                for label in self._buttons:
                    btn_id = f"btn-{label.lower()}"
                    variant = "primary" if label == "Yes" else "default"
                    yield Button(label, id=btn_id, variant=variant)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        label = event.button.label.plain
        self.dismiss(label)


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
        text = self.reg.notes or "No notes available for this register."
        with Vertical(id="notes-dialog"):
            yield Label(f"[bold]{self.reg.name}[/bold]  [{self.reg.address}]")
            yield Label(text, id="notes-text")
            yield Label("Esc to close", id="notes-hint")


class RegisterEditorApp(App):
    """Full-screen Textual app for browsing and editing Victron EVCS registers."""

    BINDINGS = [
        Binding("ctrl+s", "write_all", "Write", show=True),
        Binding("ctrl+r", "refresh_registers", "Refresh", show=True),
        Binding("ctrl+q", "quit_app", "Quit", show=True),
        Binding("question_mark", "show_notes", "Notes", show=True),
    ]

    DEFAULT_CSS = """
    DataTable {
        height: 1fr;
    }
    DataTable > .datatable--cursor {
        background: $accent 50%;
    }
    """

    def __init__(
        self,
        client: Any,
        registers: list[Register | StringRegister],
        values: dict[int, int | str | None],
        unit_id: int = 1,
    ) -> None:
        super().__init__()
        self.modbus_client = client
        self.registers = registers
        self.values: dict[int, int | str | None] = dict(values)
        self.pending: dict[int, int | str] = {}
        self._reg_by_key: dict[str, Register | StringRegister] = {}
        self.unit_id = unit_id

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield DataTable(cursor_type="row", id="reg-table")
        yield Footer()

    def on_mount(self) -> None:
        self.title = "Victron EVCS Register Editor"
        self._rebuild_table()

    def _rebuild_table(self) -> None:
        table = self.query_one(DataTable)
        table.clear(columns=True)
        table.add_columns(
            ("Address", "Address"),
            ("Name", "Name"),
            ("Value", "Value"),
            ("Unit", "Unit"),
            ("Default", "Default"),
            ("Access", "Access"),
        )
        self._reg_by_key.clear()
        for reg in self.registers:
            key = str(reg.address)
            self._reg_by_key[key] = reg
            table.add_row(
                str(reg.address),
                reg.name,
                self._value_cell(reg),
                getattr(reg, "unit", ""),
                self._default_cell(reg),
                reg.access,
                key=key,
            )
        self._update_subtitle()

    def _value_cell(self, reg: Register | StringRegister) -> str:
        address = reg.address
        raw = self.pending.get(address, self.values.get(address))
        marker = "* " if address in self.pending else ""
        if raw is None:
            return f"{marker}[red]error[/red]"
        if isinstance(reg, StringRegister):
            return f"{marker}{raw}"
        return f"{marker}{format_value(raw, reg.scale)}"

    def _default_cell(self, reg: Register | StringRegister) -> str:
        if isinstance(reg, StringRegister):
            return ""
        return format_value(reg.default, reg.scale) if reg.default is not None else ""

    def _refresh_row(self, address: int) -> None:
        reg = self._reg_by_key.get(str(address))
        if reg is None:
            return
        table = self.query_one(DataTable)
        table.update_cell(str(address), "Value", self._value_cell(reg), update_width=True)

    def _update_subtitle(self) -> None:
        count = len(self.pending)
        self.sub_title = f"{count} pending" if count else ""

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        key = event.row_key.value
        reg = self._reg_by_key.get(key)
        if reg is None or reg.access != "R/W":
            return
        raw = self.pending.get(reg.address, self.values.get(reg.address))
        if raw is None:
            current_display = ""
        elif isinstance(reg, StringRegister):
            current_display = str(raw)
        else:
            current_display = format_value(raw, reg.scale)

        def handle_edit(result: int | str | None) -> None:
            if result is not None:
                self.pending[reg.address] = result
                self._refresh_row(reg.address)
                self._update_subtitle()

        self.push_screen(EditModal(reg, current_display), handle_edit)

    def action_write_all(self) -> None:
        if not self.pending:
            self.notify("Nothing to write", severity="information")
            return
        failed_address = None
        written: list[int] = []
        mismatch_count = 0
        for address, raw_value in list(self.pending.items()):
            reg = self._reg_by_key.get(str(address))
            if reg is None:
                continue
            success, verified = write_register(
                self.modbus_client, reg, raw_value, unit_id=self.unit_id, verify=True
            )
            if success:
                self.values[address] = raw_value
                del self.pending[address]
                written.append(address)
                self._refresh_row(address)
                if verified is False:
                    mismatch_count += 1
            else:
                failed_address = address
                break
        self._update_subtitle()
        if failed_address is not None:
            self.notify(
                f"Write failed at address {failed_address} — check connection",
                severity="error",
            )
        elif written:
            if mismatch_count:
                self.notify(
                    f"Written {len(written)} register(s) — ⚠ {mismatch_count} read-back mismatch(es)",
                    severity="warning",
                )
            else:
                self.notify(f"Written {len(written)} register(s)", severity="information")

    def action_refresh_registers(self) -> None:
        if not self.pending:
            self._do_refresh()
            return

        def handle_confirm(choice: str) -> None:
            if choice == "Yes":
                self.pending.clear()
                self._do_refresh()

        self.push_screen(
            ConfirmModal(
                f"Refreshing will discard {len(self.pending)} unsaved change(s). Continue?",
                ["Yes", "No"],
            ),
            handle_confirm,
        )

    def _do_refresh(self) -> None:
        try:
            new_values = read_registers(self.modbus_client, self.registers, unit_id=self.unit_id)
            self.values = new_values
            self._rebuild_table()
            self.notify("Refreshed", severity="information")
        except OSError as e:
            self.notify(f"Refresh failed: {e}", severity="error")

    def action_show_notes(self) -> None:
        table = self.query_one(DataTable)
        row_index = table.cursor_row
        rows = table.ordered_rows
        if not rows or row_index >= len(rows):
            return
        key = rows[row_index].key.value  # str like "5009"
        reg = self._reg_by_key.get(key)
        if reg is None:
            return
        self.push_screen(NotesModal(reg))

    def action_quit_app(self) -> None:
        if not self.pending:
            self.exit()
            return

        def handle_confirm(choice: str) -> None:
            if choice == "Yes":
                self.action_write_all()
                if not self.pending:  # all writes succeeded
                    self.exit()
                # else: write failed, stay in TUI (error notification already shown)
            elif choice == "No":
                self.exit()
            # Cancel: do nothing (modal already dismissed)

        self.push_screen(
            ConfirmModal(
                f"You have {len(self.pending)} unsaved change(s). Write before quitting?",
                ["Yes", "No", "Cancel"],
            ),
            handle_confirm,
        )
