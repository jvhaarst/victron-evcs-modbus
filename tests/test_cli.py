"""Tests for CLI orchestration (build_table, filter_registers, build_scan_table, main)."""
import sys
from io import StringIO
from unittest.mock import MagicMock

import pytest
from rich.console import Console as _RichConsole

from cli import build_scan_table, build_table, filter_registers
from registers import ALL_REGISTERS, Register, StringRegister


def _render(table) -> str:
    """Render a Rich table to plain text for assertions."""
    buf = StringIO()
    _RichConsole(file=buf, force_terminal=False, no_color=True, width=200).print(table)
    return buf.getvalue()


# --- build_table tests ---


def test_build_table_string_register():
    str_reg = StringRegister(5001, "Serial Id", 6)
    values = {5001: "ABC123"}
    table = build_table([str_reg], values)
    # Table should render without error and have 5 columns
    assert len(table.columns) == 5


def test_build_table_string_register_none():
    str_reg = StringRegister(5001, "Serial Id", 6)
    values = {5001: None}
    table = build_table([str_reg], values)
    assert len(table.columns) == 5


def test_build_table_has_default_column():
    reg = Register(5016, "Charging current", "uint16", 1, "A", default=6)
    values = {5016: 10}
    table = build_table([reg], values)
    assert len(table.columns) == 5


def test_build_table_shows_formatted_default():
    reg = Register(5016, "Charging current", "uint16", 1, "A", default=6)
    values = {5016: 10}
    table = build_table([reg], values)
    output = _render(table)
    assert "10" in output   # value shown
    assert "6" in output    # default shown
    # _cells stores the raw Rich markup string; no clean public API for this check
    assert "[yellow]" in table.columns[2]._cells[0]  # value highlighted (differs from default)


def test_build_table_zero_default_shows_zero():
    reg = Register(5009, "Charge mode", "uint16", 1, "", default=0)
    values = {5009: 0}
    table = build_table([reg], values)
    output = _render(table)
    assert "0" in output    # zero default rendered (not blank)
    assert "[yellow]" not in table.columns[2]._cells[0]  # matching value — no highlight


def test_build_table_no_default_shows_blank():
    reg = Register(5000, "Product ID", "uint16", 1, "")
    values = {5000: 49189}
    table = build_table([reg], values)
    output = _render(table)
    assert "49189" in output    # value shown
    assert table.columns[4]._cells[0] == ""  # no default → blank cell


def test_build_table_value_matches_default_no_highlight():
    reg = Register(5016, "Charging current", "uint16", 1, "A", default=6)
    values = {5016: 6}
    table = build_table([reg], values)
    assert "[yellow]" not in table.columns[2]._cells[0]  # matching value — no highlight


# --- filter_registers tests ---


def test_filter_no_filters_returns_all():
    result = filter_registers(ALL_REGISTERS)
    assert len(result) == len(ALL_REGISTERS)


def test_filter_by_category_sensors():
    result = filter_registers(ALL_REGISTERS, category="sensors")
    addresses = {r.address for r in result}
    assert 5121 in addresses  # humidity
    assert 5127 in addresses  # power supply temp
    assert 5015 not in addresses  # charger status — not in sensors


def test_filter_by_address_range():
    result = filter_registers(ALL_REGISTERS, address_range=(5000, 5010))
    addresses = {r.address for r in result}
    assert all(5000 <= a <= 5010 for a in addresses)
    assert 5014 not in addresses


def test_filter_by_name():
    result = filter_registers(ALL_REGISTERS, name="power")
    assert all("power" in r.name.lower() for r in result)
    assert len(result) > 0


def test_filter_combined_and():
    result = filter_registers(
        ALL_REGISTERS,
        category="sensors",
        name="temperature",
    )
    addresses = {r.address for r in result}
    assert 5121 not in addresses  # humidity — not "temperature"
    assert 5122 in addresses      # "Onboard temperature"


def test_filter_string_registers_included_in_address_range():
    result = filter_registers(ALL_REGISTERS, address_range=(5000, 5010))
    addresses = {r.address for r in result}
    assert 5001 in addresses  # Serial Id (StringRegister)


def test_filter_invalid_category_raises():
    with pytest.raises(ValueError, match="Unknown category"):
        filter_registers(ALL_REGISTERS, category="nonexistent")


# --- build_scan_table tests ---


def test_build_scan_table_basic():
    values = {5000: 0xC024, 5001: 42}
    known = [Register(5000, "Product ID", "uint16", 1, "")]
    table = build_scan_table(5000, 5001, values, known)
    text = _render(table)
    assert "5000" in text
    assert "0x1388" in text  # hex of 5000
    assert "49188" in text  # decimal of 0xC024
    assert "0xC024" in text  # hex value
    assert "Product ID" in text
    assert "5001" in text


def test_build_scan_table_error_value():
    values = {5000: None}
    table = build_scan_table(5000, 5000, values, [])
    text = _render(table)
    assert "error" in text


def test_build_scan_table_unknown_register():
    values = {9999: 1}
    table = build_scan_table(9999, 9999, values, [])
    text = _render(table)
    assert "9999" in text
    # Known name column should be empty for unknown registers
    assert "Product ID" not in text


# --- CLI integration tests ---


def test_changed_flag_calls_filter_changed(monkeypatch):
    """--changed flag causes filter_changed to be called in main()."""
    import cli

    calls = []
    orig = cli.filter_changed

    def spy(registers, values):
        calls.append(True)
        return orig(registers, values)

    monkeypatch.setattr(cli, "filter_changed", spy)

    mock_client = MagicMock()
    mock_client.connect.return_value = True

    # Create a response that works for both scalar and string registers
    def mock_read_holding_registers(address, count, device_id):
        response = MagicMock()
        response.isError.return_value = False
        response.registers = [0] * count  # Return exactly as many registers as requested
        return response

    mock_client.read_holding_registers.side_effect = mock_read_holding_registers
    monkeypatch.setattr(cli, "ModbusTcpClient", lambda **kw: mock_client)

    monkeypatch.setattr(sys, "argv", ["cli.py", "127.0.0.1", "--changed"])
    cli.main()

    assert calls, "filter_changed was not called when --changed flag is set"


def test_write_cli_flag(monkeypatch):
    import cli
    mock_client = MagicMock()
    mock_client.connect.return_value = True
    response = MagicMock()
    response.isError.return_value = False
    response.registers = [10]
    mock_client.write_register.return_value = response
    mock_client.read_holding_registers.return_value = response
    monkeypatch.setattr(cli, "ModbusTcpClient", lambda **kw: mock_client)
    monkeypatch.setattr(sys, "argv", ["cli.py", "127.0.0.1", "--write", "5016", "10"])
    cli.main()
    mock_client.write_register.assert_called_once_with(address=5016, value=10, device_id=1)
    mock_client.read_holding_registers.assert_called_once_with(address=5016, count=1, device_id=1)


def test_write_cli_invalid_address(monkeypatch, capsys):
    import cli
    monkeypatch.setattr(sys, "argv", ["cli.py", "127.0.0.1", "--write", "9999", "10"])
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 1


def test_write_cli_readonly_address(monkeypatch, capsys):
    import cli
    # 5000 (Product ID) is R-only
    monkeypatch.setattr(sys, "argv", ["cli.py", "127.0.0.1", "--write", "5000", "10"])
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 1


def test_write_cli_out_of_range(monkeypatch, capsys):
    import cli
    monkeypatch.setattr(sys, "argv", ["cli.py", "127.0.0.1", "--write", "5016", "70000"])
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 1


def test_unit_id_cli_flag(monkeypatch):
    import cli
    mock_client = MagicMock()
    mock_client.connect.return_value = True

    def mock_read(address, count, device_id):
        response = MagicMock()
        response.isError.return_value = False
        response.registers = [0] * count
        return response

    mock_client.read_holding_registers.side_effect = mock_read
    monkeypatch.setattr(cli, "ModbusTcpClient", lambda **kw: mock_client)
    monkeypatch.setattr(sys, "argv", ["cli.py", "127.0.0.1", "--unit-id", "3", "--read"])
    cli.main()
    for call in mock_client.read_holding_registers.call_args_list:
        assert call[1]["device_id"] == 3


def test_write_cli_verify_mismatch_prints_warning(monkeypatch, capsys):
    import cli
    mock_client = MagicMock()
    mock_client.connect.return_value = True
    write_resp = MagicMock()
    write_resp.isError.return_value = False
    mock_client.write_register.return_value = write_resp
    read_resp = MagicMock()
    read_resp.isError.return_value = False
    read_resp.registers = [6]  # device returned 6, not 10
    mock_client.read_holding_registers.return_value = read_resp
    monkeypatch.setattr(cli, "ModbusTcpClient", lambda **kw: mock_client)
    monkeypatch.setattr(sys, "argv", ["cli.py", "127.0.0.1", "--write", "5016", "10"])
    cli.main()
    captured = capsys.readouterr()
    assert "Warning" in captured.out or "warning" in captured.out.lower()


def test_main_invalid_category_exits(monkeypatch):
    import cli
    monkeypatch.setattr(sys, "argv", ["cli.py", "127.0.0.1", "--read", "--category", "nonexistent"])
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 1


def test_main_invalid_address_range_exits(monkeypatch, capsys):
    import cli
    monkeypatch.setattr(sys, "argv", ["cli.py", "127.0.0.1", "--read", "--address", "bad-range"])
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 1


def test_write_cli_success_message(monkeypatch, capsys):
    import cli
    mock_client = MagicMock()
    mock_client.connect.return_value = True
    response = MagicMock()
    response.isError.return_value = False
    response.registers = [10]
    mock_client.write_register.return_value = response
    mock_client.read_holding_registers.return_value = response
    monkeypatch.setattr(cli, "ModbusTcpClient", lambda **kw: mock_client)
    monkeypatch.setattr(sys, "argv", ["cli.py", "127.0.0.1", "--write", "5016", "10"])
    cli.main()
    captured = capsys.readouterr()
    assert "5016" in captured.out
    assert "10" in captured.out
    assert "A" in captured.out


# --- interactive-default mode tests ---


def test_default_mode_launches_tui(monkeypatch):
    """No mode flag → TUI launched."""
    import cli
    mock_client = MagicMock()
    mock_client.connect.return_value = True

    def mock_read(address, count, device_id):
        response = MagicMock()
        response.isError.return_value = False
        response.registers = [0] * count
        return response

    mock_client.read_holding_registers.side_effect = mock_read
    monkeypatch.setattr(cli, "ModbusTcpClient", lambda **kw: mock_client)

    mock_app_instance = MagicMock()
    mock_app_class = MagicMock(return_value=mock_app_instance)
    mock_tui_module = MagicMock()
    mock_tui_module.RegisterEditorApp = mock_app_class
    monkeypatch.setitem(sys.modules, "tui", mock_tui_module)

    monkeypatch.setattr(sys, "argv", ["cli.py", "127.0.0.1"])
    cli.main()

    mock_app_instance.run.assert_called_once()


def test_read_flag_prints_table(monkeypatch):
    """--read flag → table path taken, TUI not launched."""
    import cli
    mock_client = MagicMock()
    mock_client.connect.return_value = True

    def mock_read(address, count, device_id):
        response = MagicMock()
        response.isError.return_value = False
        response.registers = [0] * count
        return response

    mock_client.read_holding_registers.side_effect = mock_read
    monkeypatch.setattr(cli, "ModbusTcpClient", lambda **kw: mock_client)

    # If TUI path is taken, this will cause ImportError — confirms we stayed in table mode
    monkeypatch.setitem(sys.modules, "tui", None)

    monkeypatch.setattr(sys, "argv", ["cli.py", "127.0.0.1", "--read"])
    cli.main()  # Must succeed without TUI


def test_read_and_changed_flags(monkeypatch):
    """--read --changed → filter_changed called, table printed."""
    import cli
    calls = []
    orig = cli.filter_changed

    def spy(registers, values):
        calls.append(True)
        return orig(registers, values)

    monkeypatch.setattr(cli, "filter_changed", spy)

    mock_client = MagicMock()
    mock_client.connect.return_value = True

    def mock_read(address, count, device_id):
        response = MagicMock()
        response.isError.return_value = False
        response.registers = [0] * count
        return response

    mock_client.read_holding_registers.side_effect = mock_read
    monkeypatch.setattr(cli, "ModbusTcpClient", lambda **kw: mock_client)
    monkeypatch.setitem(sys.modules, "tui", None)

    monkeypatch.setattr(sys, "argv", ["cli.py", "127.0.0.1", "--read", "--changed"])
    cli.main()

    assert calls, "filter_changed was not called with --read --changed"


def test_changed_flag_implies_read(monkeypatch):
    """--changed alone (no --read) → table path taken, not TUI.

    sys.modules["tui"] = None means importing `tui` raises ImportError,
    which would happen if the TUI branch were taken. If this test passes,
    the --changed flag correctly routed to table mode without touching tui.
    """
    import cli
    mock_client = MagicMock()
    mock_client.connect.return_value = True

    def mock_read(address, count, device_id):
        response = MagicMock()
        response.isError.return_value = False
        response.registers = [0] * count
        return response

    mock_client.read_holding_registers.side_effect = mock_read
    monkeypatch.setattr(cli, "ModbusTcpClient", lambda **kw: mock_client)

    # If TUI path is taken, ImportError — confirms we stayed in table mode
    monkeypatch.setitem(sys.modules, "tui", None)

    monkeypatch.setattr(sys, "argv", ["cli.py", "127.0.0.1", "--changed"])
    cli.main()  # Must succeed without TUI


def test_changed_with_write_ignored(monkeypatch):
    """--changed --write → write succeeds, filter_changed not called."""
    import cli
    calls = []
    orig = cli.filter_changed

    def spy(registers, values):
        calls.append(True)
        return orig(registers, values)

    monkeypatch.setattr(cli, "filter_changed", spy)

    mock_client = MagicMock()
    mock_client.connect.return_value = True
    write_resp = MagicMock()
    write_resp.isError.return_value = False
    mock_client.write_register.return_value = write_resp
    monkeypatch.setattr(cli, "ModbusTcpClient", lambda **kw: mock_client)

    monkeypatch.setattr(sys, "argv", ["cli.py", "127.0.0.1", "--changed", "--write", "5016", "10"])
    cli.main()

    assert not calls, "filter_changed must not be called when --write is present"
