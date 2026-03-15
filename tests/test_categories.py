from categories import CATEGORIES
from registers import ALL_REGISTERS

_ALL_ADDRESSES = {r.address for r in ALL_REGISTERS}
_VALID_CATEGORIES = {"status", "session", "device", "config", "auto_mode", "sensors", "diagnostics"}


def test_categories_has_expected_keys():
    assert set(CATEGORIES.keys()) == _VALID_CATEGORIES


def test_all_category_addresses_exist_in_all_registers():
    for cat, addresses in CATEGORIES.items():
        for addr in addresses:
            assert addr in _ALL_ADDRESSES, f"Category '{cat}' has address {addr} not in ALL_REGISTERS"


def test_sensors_contains_humidity():
    assert 5121 in CATEGORIES["sensors"]


def test_sensors_contains_all_temperatures():
    for addr in [5122, 5123, 5124, 5125, 5126, 5127]:
        assert addr in CATEGORIES["sensors"], f"Address {addr} not in sensors category"


def test_status_contains_charger_status():
    assert 5015 in CATEGORIES["status"]


def test_no_empty_categories():
    for cat, addresses in CATEGORIES.items():
        assert len(addresses) > 0, f"Category '{cat}' is empty"


def test_no_duplicate_addresses_within_category():
    for cat, addresses in CATEGORIES.items():
        assert len(addresses) == len(set(addresses)), f"Duplicate addresses in '{cat}'"


def test_register_can_appear_in_multiple_categories():
    """Registers may belong to more than one category — this is intentional."""
    assert 5099 in CATEGORIES["status"]
    assert 5099 in CATEGORIES["config"]
