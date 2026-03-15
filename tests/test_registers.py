import pytest
from registers import REGISTERS, Register, StringRegister, STRING_REGISTERS, ALL_REGISTERS


def test_register_list_is_not_empty():
    assert len(REGISTERS) > 0


def test_register_has_required_fields():
    reg = REGISTERS[0]
    assert isinstance(reg.address, int)
    assert isinstance(reg.name, str)
    assert reg.data_type in ("uint16", "int16")
    assert isinstance(reg.scale, int)
    assert isinstance(reg.unit, str)


def test_product_id_register():
    reg = next(r for r in REGISTERS if r.address == 5000)
    assert reg.name == "Product ID"
    assert reg.data_type == "uint16"
    assert reg.scale == 1
    assert reg.unit == ""


def test_charging_current_actual_has_scale_10():
    reg = next(r for r in REGISTERS if r.address == 5018)
    assert reg.scale == 10
    assert reg.unit == "A"


def test_addresses_are_unique():
    addresses = [r.address for r in REGISTERS]
    assert len(addresses) == len(set(addresses))


def test_register_rejects_non_positive_scale():
    with pytest.raises(ValueError, match="scale must be > 0"):
        Register(5000, "Test", "uint16", 0, "")


def test_all_registers_have_valid_data_type():
    valid = {"uint16", "int16"}
    for reg in REGISTERS:
        assert reg.data_type in valid, f"Register {reg.address} has data_type={reg.data_type!r}"


def test_string_register_fields():
    reg = StringRegister(5001, "Serial Id", 6)
    assert reg.address == 5001
    assert reg.name == "Serial Id"
    assert reg.register_count == 6
    assert reg.encoding == "utf-8"


def test_string_register_custom_encoding():
    reg = StringRegister(5001, "Test", 6, encoding="ascii")
    assert reg.encoding == "ascii"


def test_string_registers_list():
    assert len(STRING_REGISTERS) == 2
    addrs = [r.address for r in STRING_REGISTERS]
    assert 5001 in addrs  # Serial Id
    assert 5027 in addrs  # Device name


def test_string_register_rejects_non_positive_register_count():
    with pytest.raises(ValueError, match="register_count must be > 0"):
        StringRegister(5001, "Test", 0)


def test_all_registers_count():
    assert len(ALL_REGISTERS) == len(REGISTERS) + len(STRING_REGISTERS)


def test_no_duplicate_addresses_across_all():
    addrs = [r.address for r in ALL_REGISTERS]
    assert len(addrs) == len(set(addrs))


def test_register_default_is_none_by_default():
    reg = Register(5000, "Test", "uint16", 1, "")
    assert reg.default is None


def test_register_with_default():
    reg = Register(5000, "Test", "uint16", 1, "", default=6)
    assert reg.default == 6


def test_register_with_zero_default():
    reg = Register(5000, "Test", "uint16", 1, "", default=0)
    assert reg.default == 0  # 0 is valid, not None


def test_registers_with_defaults_count():
    count = sum(1 for r in REGISTERS if r.default is not None)
    assert count == 80


def test_register_access_defaults_to_r():
    reg = Register(5000, "Test", "uint16", 1, "")
    assert reg.access == "R"


def test_register_rw_access():
    reg = Register(5000, "Test", "uint16", 1, "", access="R/W")
    assert reg.access == "R/W"


def test_string_register_access_defaults_to_r():
    reg = StringRegister(5001, "Test", 6)
    assert reg.access == "R"


def test_registers_rw_count():
    # All scalar Register entries across the full list
    count = sum(1 for r in ALL_REGISTERS if isinstance(r, Register) and r.access == "R/W")
    assert count == 76



def test_device_name_is_rw():
    reg = next(r for r in STRING_REGISTERS if r.address == 5027)
    assert reg.access == "R/W"


def test_register_notes_defaults_to_empty():
    reg = Register(5000, "Test", "uint16", 1, "")
    assert reg.notes == ""


def test_register_notes_value():
    reg = Register(5000, "Test", "uint16", 1, "", notes="0 - stop, 1 - start")
    assert reg.notes == "0 - stop, 1 - start"


def test_string_register_notes_defaults_to_empty():
    reg = StringRegister(5001, "Test", 6)
    assert reg.notes == ""


def test_charge_mode_notes():
    reg = next(r for r in REGISTERS if r.address == 5009)
    assert reg.notes == "0 - manual, 1 - auto, 2 - scheduled"


def test_serial_id_notes():
    reg = next(r for r in STRING_REGISTERS if r.address == 5001)
    assert reg.notes == "6 registers, 12 characters"
