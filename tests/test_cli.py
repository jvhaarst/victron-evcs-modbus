import struct
import sys
from unittest.mock import MagicMock
import pytest
from registers import Register, StringRegister, ALL_REGISTERS
from cli import read_registers, build_table, format_value, filter_registers, filter_changed, validate_write_value, write_register


# --- format_value tests (pure, no mocking needed) ---

def test_format_value_no_scale():
    assert format_value(42, scale=1) == "42"


def test_format_value_with_scale():
    assert format_value(185, scale=10) == "18.5"


def test_format_value_exact_division():
    assert format_value(1500, scale=100) == "15.0"


# --- read_registers tests (mock pymodbus) ---

def test_read_registers_returns_dict(mock_modbus_client):
    from registers import REGISTERS
    result = read_registers(mock_modbus_client, REGISTERS)
    assert isinstance(result, dict)
    assert 5000 in result
    assert result[5000] == 0xC024


def test_read_registers_handles_error_response(mock_modbus_client_error):
    from registers import REGISTERS
    result = read_registers(mock_modbus_client_error, REGISTERS)
    assert result[5000] is None


@pytest.fixture
def mock_modbus_client():
    client = MagicMock()
    # Chunk 1: address=5000, count=123 (registers 5000-5122)
    response1 = MagicMock()
    response1.isError.return_value = False
    response1.registers = [0xC024] + [0] * 122  # 123 registers

    # Chunk 2: address=5127, count=1 (register 5127 only)
    response2 = MagicMock()
    response2.isError.return_value = False
    response2.registers = [0] * 1  # 1 register

    client.read_holding_registers.side_effect = [response1, response2]
    return client


@pytest.fixture
def mock_modbus_client_error():
    client = MagicMock()
    response = MagicMock()
    response.isError.return_value = True
    # Return error for both chunks
    client.read_holding_registers.return_value = response
    return client


def test_int16_sign_conversion(mock_modbus_client_signed):
    # Use a minimal register list with just one int16 register
    int16_reg = Register(5071, "Test int16", "int16", 1, "W")
    result = read_registers(mock_modbus_client_signed, [int16_reg])
    assert result[5071] == -500


def test_string_register_decode(mock_modbus_client_string):
    str_reg = StringRegister(5001, "Serial Id", 6)
    result = read_registers(mock_modbus_client_string, [str_reg])
    assert result[5001] == "MyDevice"


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


@pytest.fixture
def mock_modbus_client_signed():
    """Returns raw value 65036 for address 5071 (= -500 as int16)."""
    client = MagicMock()
    response = MagicMock()
    response.isError.return_value = False
    # Single register at 5071 with raw value 65036
    response.registers = [65036]
    client.read_holding_registers.return_value = response
    return client


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


@pytest.fixture
def mock_modbus_client_string():
    """Returns uint16 words spelling 'MyDevice' + null padding for a 6-register string."""
    client = MagicMock()
    response = MagicMock()
    response.isError.return_value = False
    # "MyDevice" little-endian per word: struct.unpack("<H", b"My")=0x794D, etc.
    response.registers = [0x794D, 0x6544, 0x6976, 0x6563, 0x0000, 0x0000]
    client.read_holding_registers.return_value = response
    return client


# --- build_table default column tests ---

def test_build_table_has_default_column():
    reg = Register(5016, "Charging current", "uint16", 1, "A", default=6)
    values = {5016: 10}
    table = build_table([reg], values)
    assert len(table.columns) == 5


def test_build_table_shows_formatted_default():
    reg = Register(5016, "Charging current", "uint16", 1, "A", default=6)
    values = {5016: 10}
    table = build_table([reg], values)
    # Value differs from default → yellow markup in value cell
    rendered = table.columns[2]._cells[0]  # Value column, first row
    assert "[yellow]" in rendered
    # Default column shows formatted default
    default_cell = table.columns[4]._cells[0]  # Default column, first row
    assert default_cell == "6"


def test_build_table_zero_default_shows_zero():
    reg = Register(5009, "Charge mode", "uint16", 1, "", default=0)
    values = {5009: 0}
    table = build_table([reg], values)
    default_cell = table.columns[4]._cells[0]
    assert default_cell == "0"
    value_cell = table.columns[2]._cells[0]
    assert "[yellow]" not in value_cell  # values match, no highlight


def test_build_table_no_default_shows_blank():
    reg = Register(5000, "Product ID", "uint16", 1, "")
    values = {5000: 49189}
    table = build_table([reg], values)
    default_cell = table.columns[4]._cells[0]
    assert default_cell == ""


def test_build_table_value_matches_default_no_highlight():
    reg = Register(5016, "Charging current", "uint16", 1, "A", default=6)
    values = {5016: 6}
    table = build_table([reg], values)
    value_cell = table.columns[2]._cells[0]
    assert "[yellow]" not in value_cell


# --- filter_changed tests ---

def test_filter_changed_returns_changed():
    reg = Register(5016, "Charging current", "uint16", 1, "A", default=6)
    result = filter_changed([reg], {5016: 10})
    assert reg in result


def test_filter_changed_excludes_matching():
    reg = Register(5016, "Charging current", "uint16", 1, "A", default=6)
    result = filter_changed([reg], {5016: 6})
    assert result == []


def test_filter_changed_excludes_no_default():
    reg = Register(5000, "Product ID", "uint16", 1, "")
    result = filter_changed([reg], {5000: 999})
    assert result == []


def test_filter_changed_excludes_error():
    reg = Register(5016, "Charging current", "uint16", 1, "A", default=6)
    result = filter_changed([reg], {5016: None})
    assert result == []


def test_filter_changed_excludes_string_registers():
    str_reg = StringRegister(5001, "Serial Id", 6)
    result = filter_changed([str_reg], {5001: "ABC123"})
    assert result == []


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

    import sys
    monkeypatch.setattr(sys, "argv", ["cli.py", "127.0.0.1", "--changed"])
    cli.main()

    assert calls, "filter_changed was not called when --changed flag is set"


# --- validate_write_value tests ---

def test_validate_write_value_uint16_valid():
    reg = Register(5016, "Charging current", "uint16", 1, "A", access="R/W")
    assert validate_write_value(reg, "10") == 10


def test_validate_write_value_scaled():
    reg = Register(5076, "Current step", "uint16", 10, "A", access="R/W")
    assert validate_write_value(reg, "0.2") == 2


def test_validate_write_value_uint16_out_of_range():
    reg = Register(5016, "Charging current", "uint16", 1, "A", access="R/W")
    with pytest.raises(ValueError):
        validate_write_value(reg, "70000")


def test_validate_write_value_int16_valid():
    reg = Register(5071, "Grid power for start", "int16", 1, "W", access="R/W")
    assert validate_write_value(reg, "-500") == -500


def test_validate_write_value_int16_out_of_range():
    reg = Register(5071, "Grid power for start", "int16", 1, "W", access="R/W")
    with pytest.raises(ValueError):
        validate_write_value(reg, "40000")


def test_validate_write_value_string_valid():
    reg = StringRegister(5027, "Device name", 22, access="R/W")
    assert validate_write_value(reg, "My Charger") == "My Charger"


def test_validate_write_value_string_too_long():
    reg = StringRegister(5027, "Device name", 2, access="R/W")  # max 4 bytes
    with pytest.raises(ValueError):
        validate_write_value(reg, "Hello!")


# --- write_register tests ---

def test_write_register_scalar():
    reg = Register(5016, "Charging current", "uint16", 1, "A", access="R/W")
    mock_client = MagicMock()
    response = MagicMock()
    response.isError.return_value = False
    mock_client.write_register.return_value = response
    success, _ = write_register(mock_client, reg, 10)
    assert success is True
    mock_client.write_register.assert_called_once_with(address=5016, value=10, device_id=1)


def test_write_register_scalar_error():
    reg = Register(5016, "Charging current", "uint16", 1, "A", access="R/W")
    mock_client = MagicMock()
    response = MagicMock()
    response.isError.return_value = True
    mock_client.write_register.return_value = response
    success, _ = write_register(mock_client, reg, 10)
    assert success is False


def test_write_register_int16_negative():
    reg = Register(5071, "Grid power for start", "int16", 1, "W", access="R/W")
    mock_client = MagicMock()
    response = MagicMock()
    response.isError.return_value = False
    mock_client.write_register.return_value = response
    success, _ = write_register(mock_client, reg, -500)
    assert success is True
    mock_client.write_register.assert_called_once_with(address=5071, value=65036, device_id=1)


def test_write_register_string():
    reg = StringRegister(5027, "Device name", 22, access="R/W")
    mock_client = MagicMock()
    response = MagicMock()
    response.isError.return_value = False
    mock_client.write_registers.return_value = response
    success, _ = write_register(mock_client, reg, "My Charger")
    assert success is True
    mock_client.write_registers.assert_called_once()
    call_kwargs = mock_client.write_registers.call_args[1]
    assert call_kwargs["address"] == 5027
    assert len(call_kwargs["values"]) == 22
    # Verify little-endian byte order: "My" → struct.unpack("<H", b"My") = 0x794D
    import struct as _struct
    assert call_kwargs["values"][0] == _struct.unpack("<H", b"My")[0]


def test_string_register_byte_order_read():
    """Bytes within each 16-bit word are little-endian: low byte = first char."""
    import struct as _struct
    client = MagicMock()
    response = MagicMock()
    response.isError.return_value = False
    # "EV" stored little-endian: low='E'=0x45, high='V'=0x56 → register=0x5645
    response.registers = [_struct.unpack("<H", b"EV")[0], 0x0000, 0x0000,
                          0x0000, 0x0000, 0x0000]
    client.read_holding_registers.return_value = response
    reg = StringRegister(5001, "Serial Id", 6)
    result = read_registers(client, [reg])
    assert result[5001] == "EV"


def test_write_register_exception_returns_false():
    reg = Register(5016, "Charging current", "uint16", 1, "A", access="R/W")
    mock_client = MagicMock()
    mock_client.write_register.side_effect = Exception("connection lost")
    success, _ = write_register(mock_client, reg, 10)
    assert success is False


# --- --write CLI tests ---

def test_write_cli_flag(monkeypatch):
    import cli
    mock_client = MagicMock()
    mock_client.connect.return_value = True
    response = MagicMock()
    response.isError.return_value = False
    mock_client.write_register.return_value = response
    monkeypatch.setattr(cli, "ModbusTcpClient", lambda **kw: mock_client)
    monkeypatch.setattr(sys, "argv", ["cli.py", "127.0.0.1", "--write", "5016", "10"])
    cli.main()
    mock_client.write_register.assert_called_once_with(address=5016, value=10, device_id=1)


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


def test_read_registers_uses_unit_id():
    client = MagicMock()
    response = MagicMock()
    response.isError.return_value = False
    response.registers = [0]
    client.read_holding_registers.return_value = response
    reg = Register(5000, "Product ID", "uint16", 1, "")
    read_registers(client, [reg], unit_id=3)
    client.read_holding_registers.assert_called_with(address=5000, count=1, device_id=3)


def test_write_register_uses_unit_id():
    reg = Register(5016, "Charging current", "uint16", 1, "A", access="R/W")
    client = MagicMock()
    response = MagicMock()
    response.isError.return_value = False
    client.write_register.return_value = response
    success, _ = write_register(client, reg, 10, unit_id=3)
    assert success is True
    client.write_register.assert_called_once_with(address=5016, value=10, device_id=3)


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
    monkeypatch.setattr(sys, "argv", ["cli.py", "127.0.0.1", "--unit-id", "3"])
    cli.main()
    for call in mock_client.read_holding_registers.call_args_list:
        assert call[1]["device_id"] == 3


def test_write_register_returns_tuple():
    reg = Register(5016, "Charging current", "uint16", 1, "A", access="R/W")
    client = MagicMock()
    response = MagicMock()
    response.isError.return_value = False
    client.write_register.return_value = response
    success, verified = write_register(client, reg, 10)
    assert success is True
    assert verified is None


def test_write_register_verify_match():
    reg = Register(5016, "Charging current", "uint16", 1, "A", access="R/W")
    client = MagicMock()
    write_resp = MagicMock()
    write_resp.isError.return_value = False
    read_resp = MagicMock()
    read_resp.isError.return_value = False
    read_resp.registers = [10]
    client.write_register.return_value = write_resp
    client.read_holding_registers.return_value = read_resp
    success, verified = write_register(client, reg, 10, verify=True)
    assert success is True
    assert verified is True


def test_write_register_verify_mismatch():
    reg = Register(5016, "Charging current", "uint16", 1, "A", access="R/W")
    client = MagicMock()
    write_resp = MagicMock()
    write_resp.isError.return_value = False
    read_resp = MagicMock()
    read_resp.isError.return_value = False
    read_resp.registers = [6]
    client.write_register.return_value = write_resp
    client.read_holding_registers.return_value = read_resp
    success, verified = write_register(client, reg, 10, verify=True)
    assert success is True
    assert verified is False


def test_write_register_verify_readback_error():
    reg = Register(5016, "Charging current", "uint16", 1, "A", access="R/W")
    client = MagicMock()
    write_resp = MagicMock()
    write_resp.isError.return_value = False
    read_resp = MagicMock()
    read_resp.isError.return_value = True
    client.write_register.return_value = write_resp
    client.read_holding_registers.return_value = read_resp
    success, verified = write_register(client, reg, 10, verify=True)
    assert success is True
    assert verified is None


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


def test_validate_write_value_range_scaled():
    # scale=10: display lo=0.1 → raw=1, display hi=6553.5 → raw=65535
    reg = Register(5076, "Feed-in current step", "uint16", 10, "A", access="R/W", range=(0.1, 6553.5))
    assert validate_write_value(reg, "0.1") == 1
    assert validate_write_value(reg, "6553.5") == 65535
    with pytest.raises(ValueError, match="out of range"):
        validate_write_value(reg, "0.09")


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
