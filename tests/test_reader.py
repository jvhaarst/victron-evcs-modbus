import struct
import sys
from unittest.mock import MagicMock
import pytest
from registers import Register, StringRegister, ALL_REGISTERS
from reader import read_registers, build_table, format_value, filter_registers, filter_changed, validate_write_value, write_register


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
    # "MyDevice" = 0x4D79, 0x4465, 0x7669, 0x6365, then two null words
    response.registers = [0x4D79, 0x4465, 0x7669, 0x6365, 0x0000, 0x0000]
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
    import reader

    calls = []
    orig = reader.filter_changed

    def spy(registers, values):
        calls.append(True)
        return orig(registers, values)

    monkeypatch.setattr(reader, "filter_changed", spy)

    mock_client = MagicMock()
    mock_client.connect.return_value = True

    # Create a response that works for both scalar and string registers
    def mock_read_holding_registers(address, count, device_id):
        response = MagicMock()
        response.isError.return_value = False
        response.registers = [0] * count  # Return exactly as many registers as requested
        return response

    mock_client.read_holding_registers.side_effect = mock_read_holding_registers
    monkeypatch.setattr(reader, "ModbusTcpClient", lambda **kw: mock_client)

    import sys
    monkeypatch.setattr(sys, "argv", ["reader.py", "127.0.0.1", "--changed"])
    reader.main()

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
    assert write_register(mock_client, reg, 10) is True
    mock_client.write_register.assert_called_once_with(address=5016, value=10, device_id=1)


def test_write_register_scalar_error():
    reg = Register(5016, "Charging current", "uint16", 1, "A", access="R/W")
    mock_client = MagicMock()
    response = MagicMock()
    response.isError.return_value = True
    mock_client.write_register.return_value = response
    assert write_register(mock_client, reg, 10) is False


def test_write_register_int16_negative():
    reg = Register(5071, "Grid power for start", "int16", 1, "W", access="R/W")
    mock_client = MagicMock()
    response = MagicMock()
    response.isError.return_value = False
    mock_client.write_register.return_value = response
    result = write_register(mock_client, reg, -500)
    assert result is True
    mock_client.write_register.assert_called_once_with(address=5071, value=65036, device_id=1)


def test_write_register_string():
    reg = StringRegister(5027, "Device name", 22, access="R/W")
    mock_client = MagicMock()
    response = MagicMock()
    response.isError.return_value = False
    mock_client.write_registers.return_value = response
    assert write_register(mock_client, reg, "My Charger") is True
    mock_client.write_registers.assert_called_once()
    call_kwargs = mock_client.write_registers.call_args[1]
    assert call_kwargs["address"] == 5027
    assert len(call_kwargs["values"]) == 22


def test_write_register_exception_returns_false():
    reg = Register(5016, "Charging current", "uint16", 1, "A", access="R/W")
    mock_client = MagicMock()
    mock_client.write_register.side_effect = Exception("connection lost")
    assert write_register(mock_client, reg, 10) is False


# --- --write CLI tests ---

def test_write_cli_flag(monkeypatch):
    import reader
    mock_client = MagicMock()
    mock_client.connect.return_value = True
    response = MagicMock()
    response.isError.return_value = False
    mock_client.write_register.return_value = response
    monkeypatch.setattr(reader, "ModbusTcpClient", lambda **kw: mock_client)
    monkeypatch.setattr(sys, "argv", ["reader.py", "127.0.0.1", "--write", "5016", "10"])
    reader.main()
    mock_client.write_register.assert_called_once_with(address=5016, value=10, device_id=1)


def test_write_cli_invalid_address(monkeypatch, capsys):
    import reader
    monkeypatch.setattr(sys, "argv", ["reader.py", "127.0.0.1", "--write", "9999", "10"])
    with pytest.raises(SystemExit) as exc:
        reader.main()
    assert exc.value.code == 1


def test_write_cli_readonly_address(monkeypatch, capsys):
    import reader
    # 5000 (Product ID) is R-only
    monkeypatch.setattr(sys, "argv", ["reader.py", "127.0.0.1", "--write", "5000", "10"])
    with pytest.raises(SystemExit) as exc:
        reader.main()
    assert exc.value.code == 1


def test_write_cli_out_of_range(monkeypatch, capsys):
    import reader
    monkeypatch.setattr(sys, "argv", ["reader.py", "127.0.0.1", "--write", "5016", "70000"])
    with pytest.raises(SystemExit) as exc:
        reader.main()
    assert exc.value.code == 1
