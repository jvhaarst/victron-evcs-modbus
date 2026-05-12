"""Tests for modbus I/O operations (read, write, scan)."""
from unittest.mock import MagicMock

import pytest

from modbus import read_registers, scan_registers, write_register
from registers import Register, StringRegister


# --- fixtures ---


@pytest.fixture
def mock_modbus_client():
    client = MagicMock()
    # Chunk 1: address=5000, count=125 (registers 5000-5124)
    response1 = MagicMock()
    response1.isError.return_value = False
    response1.registers = [0xC024] + [0] * 124  # 125 registers

    # Chunk 2: address=5125, count=19 (registers 5125-5143)
    response2 = MagicMock()
    response2.isError.return_value = False
    response2.registers = [0] * 19  # 19 registers

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


# --- read_registers tests ---


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


def test_read_registers_uses_unit_id():
    client = MagicMock()
    response = MagicMock()
    response.isError.return_value = False
    response.registers = [0]
    client.read_holding_registers.return_value = response
    reg = Register(5000, "Product ID", "uint16", 1, "")
    read_registers(client, [reg], unit_id=3)
    client.read_holding_registers.assert_called_with(address=5000, count=1, device_id=3)


def test_int16_sign_conversion(mock_modbus_client_signed):
    # Use a minimal register list with just one int16 register
    int16_reg = Register(5071, "Test int16", "int16", 1, "W")
    result = read_registers(mock_modbus_client_signed, [int16_reg])
    assert result[5071] == -500


def test_string_register_decode(mock_modbus_client_string):
    str_reg = StringRegister(5001, "Serial Id", 6)
    result = read_registers(mock_modbus_client_string, [str_reg])
    assert result[5001] == "MyDevice"


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


def test_write_register_exception_returns_false():
    reg = Register(5016, "Charging current", "uint16", 1, "A", access="R/W")
    mock_client = MagicMock()
    mock_client.write_register.side_effect = OSError("connection lost")
    success, _ = write_register(mock_client, reg, 10)
    assert success is False


def test_write_register_uses_unit_id():
    reg = Register(5016, "Charging current", "uint16", 1, "A", access="R/W")
    client = MagicMock()
    response = MagicMock()
    response.isError.return_value = False
    client.write_register.return_value = response
    success, _ = write_register(client, reg, 10, unit_id=3)
    assert success is True
    client.write_register.assert_called_once_with(address=5016, value=10, device_id=3)


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


# --- scan_registers tests ---


def test_scan_registers_returns_values():
    client = MagicMock()
    response = MagicMock()
    response.isError.return_value = False
    response.registers = [100, 200, 300]
    client.read_holding_registers.return_value = response

    result = scan_registers(client, 5000, 5002)
    assert result == {5000: 100, 5001: 200, 5002: 300}


def test_scan_registers_error_returns_none():
    client = MagicMock()
    response = MagicMock()
    response.isError.return_value = True
    client.read_holding_registers.return_value = response

    result = scan_registers(client, 5000, 5002)
    assert result == {5000: None, 5001: None, 5002: None}


def test_scan_registers_chunks_at_125():
    client = MagicMock()
    resp1 = MagicMock()
    resp1.isError.return_value = False
    resp1.registers = list(range(125))
    resp2 = MagicMock()
    resp2.isError.return_value = False
    resp2.registers = [999]
    client.read_holding_registers.side_effect = [resp1, resp2]

    result = scan_registers(client, 5000, 5125)
    assert len(result) == 126
    assert result[5000] == 0
    assert result[5124] == 124
    assert result[5125] == 999
    # Verify two calls were made with correct chunking
    calls = client.read_holding_registers.call_args_list
    assert len(calls) == 2
    assert calls[0].kwargs["count"] == 125
    assert calls[1].kwargs["count"] == 1


def test_scan_registers_uses_unit_id():
    client = MagicMock()
    response = MagicMock()
    response.isError.return_value = False
    response.registers = [42]
    client.read_holding_registers.return_value = response

    scan_registers(client, 5000, 5000, unit_id=7)
    client.read_holding_registers.assert_called_once_with(address=5000, count=1, device_id=7)
