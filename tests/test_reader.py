from unittest.mock import MagicMock
import pytest
from reader import read_registers, format_value


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
