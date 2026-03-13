from registers import REGISTERS, Register


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
