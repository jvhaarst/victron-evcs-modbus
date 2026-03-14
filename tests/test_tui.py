import pytest
from unittest.mock import MagicMock
from registers import Register, StringRegister
from cli import format_value


@pytest.fixture
def rw_reg():
    return Register(5016, "Charging current", "uint16", 1, "A", default=6, access="R/W")


@pytest.fixture
def ro_reg():
    return Register(5000, "Product ID", "uint16", 1, "", access="R")


@pytest.fixture
def mock_client():
    client = MagicMock()
    response = MagicMock()
    response.isError.return_value = False
    client.write_register.return_value = response
    client.write_registers.return_value = response
    return client


@pytest.mark.asyncio
async def test_tui_loads(rw_reg, ro_reg, mock_client):
    from tui import RegisterEditorApp
    registers = [ro_reg, rw_reg]
    values = {5000: 49189, 5016: 10}
    async with RegisterEditorApp(mock_client, registers, values).run_test() as pilot:
        from textual.widgets import DataTable
        table = pilot.app.query_one(DataTable)
        assert table.row_count == 2


@pytest.mark.asyncio
async def test_tui_enter_on_readonly_does_nothing(ro_reg, mock_client):
    from tui import RegisterEditorApp
    from textual.widgets import DataTable
    registers = [ro_reg]
    values = {5000: 49189}
    async with RegisterEditorApp(mock_client, registers, values).run_test() as pilot:
        await pilot.press("enter")
        # No modal pushed — screen stack has only the main screen
        assert len(pilot.app.screen_stack) == 1


@pytest.mark.asyncio
async def test_tui_enter_edit_escape_restores(rw_reg, mock_client):
    from tui import RegisterEditorApp
    from textual.widgets import DataTable
    registers = [rw_reg]
    values = {5016: 10}
    async with RegisterEditorApp(mock_client, registers, values).run_test() as pilot:
        await pilot.press("enter")
        assert len(pilot.app.screen_stack) == 2  # edit modal pushed
        await pilot.press("escape")
        await pilot.pause()
        assert len(pilot.app.screen_stack) == 1  # modal dismissed
        assert 5016 not in pilot.app.pending  # no pending change
        # Original value still displayed (no * prefix)
        table = pilot.app.query_one(DataTable)
        cell_value = table.get_cell("5016", "Value")
        assert cell_value == "10"  # original value, no * marker


@pytest.mark.asyncio
async def test_tui_edit_marks_pending(rw_reg, mock_client):
    from tui import RegisterEditorApp
    registers = [rw_reg]
    values = {5016: 10}
    async with RegisterEditorApp(mock_client, registers, values).run_test() as pilot:
        await pilot.press("enter")         # open edit modal
        await pilot.press("ctrl+shift+a")  # select all
        await pilot.press("1", "6")        # type new value (replaces selection)
        await pilot.press("enter")         # confirm edit
        await pilot.pause()
        assert 5016 in pilot.app.pending
        assert pilot.app.pending[5016] == 16


@pytest.mark.asyncio
async def test_tui_ctrl_s_calls_write(rw_reg, mock_client):
    from tui import RegisterEditorApp
    registers = [rw_reg]
    values = {5016: 10}
    async with RegisterEditorApp(mock_client, registers, values).run_test() as pilot:
        # Inject a pending write directly
        pilot.app.pending[5016] = 16
        await pilot.press("ctrl+s")
        await pilot.pause()
        mock_client.write_register.assert_called_once_with(address=5016, value=16, device_id=1)
        assert 5016 not in pilot.app.pending


@pytest.mark.asyncio
async def test_tui_ctrl_q_with_pending_shows_dialog(rw_reg, mock_client):
    from tui import RegisterEditorApp
    registers = [rw_reg]
    values = {5016: 10}
    async with RegisterEditorApp(mock_client, registers, values).run_test() as pilot:
        pilot.app.pending[5016] = 16
        await pilot.press("ctrl+q")
        await pilot.pause()
        assert len(pilot.app.screen_stack) == 2  # confirm dialog pushed


@pytest.mark.asyncio
async def test_tui_ctrl_q_dialog_no_discards(rw_reg, mock_client):
    from tui import RegisterEditorApp
    from textual.widgets import Button
    registers = [rw_reg]
    values = {5016: 10}
    async with RegisterEditorApp(mock_client, registers, values).run_test() as pilot:
        pilot.app.pending[5016] = 16
        await pilot.press("ctrl+q")
        await pilot.pause()
        # Click "No" button
        await pilot.click("#btn-no")
        await pilot.pause()
        mock_client.write_register.assert_not_called()
        assert not pilot.app.is_running  # app exited without writing


@pytest.mark.asyncio
async def test_tui_ctrl_q_dialog_cancel_returns(rw_reg, mock_client):
    from tui import RegisterEditorApp
    registers = [rw_reg]
    values = {5016: 10}
    async with RegisterEditorApp(mock_client, registers, values).run_test() as pilot:
        pilot.app.pending[5016] = 16
        await pilot.press("ctrl+q")
        await pilot.pause()
        await pilot.click("#btn-cancel")
        await pilot.pause()
        # TUI still active (not exited)
        assert len(pilot.app.screen_stack) == 1
        assert 5016 in pilot.app.pending  # changes preserved


@pytest.mark.asyncio
async def test_tui_ctrl_r_with_pending_shows_dialog(rw_reg, mock_client):
    from tui import RegisterEditorApp
    registers = [rw_reg]
    values = {5016: 10}
    async with RegisterEditorApp(mock_client, registers, values).run_test() as pilot:
        pilot.app.pending[5016] = 16
        await pilot.press("ctrl+r")
        await pilot.pause()
        assert len(pilot.app.screen_stack) == 2  # refresh confirm dialog pushed


@pytest.mark.asyncio
async def test_tui_ctrl_s_write_failure_shows_error(rw_reg, mock_client):
    from tui import RegisterEditorApp
    error_response = MagicMock()
    error_response.isError.return_value = True
    mock_client.write_register.return_value = error_response
    registers = [rw_reg]
    values = {5016: 10}
    async with RegisterEditorApp(mock_client, registers, values).run_test() as pilot:
        pilot.app.pending[5016] = 16
        notifications = []
        original_notify = pilot.app.notify
        pilot.app.notify = lambda msg, **kw: notifications.append((msg, kw)) or original_notify(msg, **kw)
        await pilot.press("ctrl+s")
        await pilot.pause()
        # Row stays pending (write failed)
        assert 5016 in pilot.app.pending
        # Error notification was raised
        assert any("5016" in msg or "failed" in msg.lower() for msg, _ in notifications)


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
        text = " ".join(str(label.content) for label in labels)
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
        text = " ".join(str(label.content) for label in labels)
        assert "No notes available" in text


@pytest.mark.asyncio
async def test_tui_unit_id_passed_to_write(mock_client):
    from tui import RegisterEditorApp
    reg = Register(5016, "Charging current", "uint16", 1, "A", default=6, access="R/W")
    registers = [reg]
    values = {5016: 10}
    async with RegisterEditorApp(mock_client, registers, values, unit_id=3).run_test() as pilot:
        pilot.app.pending[5016] = 16
        await pilot.press("ctrl+s")
        await pilot.pause()
        mock_client.write_register.assert_called_once_with(address=5016, value=16, device_id=3)


@pytest.mark.asyncio
async def test_tui_write_mismatch_notification(mock_client):
    from tui import RegisterEditorApp
    reg = Register(5016, "Charging current", "uint16", 1, "A", default=6, access="R/W")
    registers = [reg]
    values = {5016: 10}
    # Configure read-back to return a different value (device clamped to 6)
    rb_response = MagicMock()
    rb_response.isError.return_value = False
    rb_response.registers = [6]
    mock_client.read_holding_registers.return_value = rb_response
    notifications = []
    async with RegisterEditorApp(mock_client, registers, values).run_test() as pilot:
        pilot.app.pending[5016] = 16
        original_notify = pilot.app.notify
        pilot.app.notify = lambda msg, **kw: notifications.append((msg, kw)) or original_notify(msg, **kw)
        await pilot.press("ctrl+s")
        await pilot.pause()
        assert any("mismatch" in msg.lower() for msg, _ in notifications)
