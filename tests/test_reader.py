import struct
from unittest.mock import MagicMock
import pytest
from registers import Register, StringRegister, ALL_REGISTERS
from reader import read_registers, build_table, format_value, filter_registers


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
    # Table should render without error and have 4 columns
    assert len(table.columns) == 4


def test_build_table_string_register_none():
    str_reg = StringRegister(5001, "Serial Id", 6)
    values = {5001: None}
    table = build_table([str_reg], values)
    assert len(table.columns) == 4


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
    assert len(result) == 115


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
