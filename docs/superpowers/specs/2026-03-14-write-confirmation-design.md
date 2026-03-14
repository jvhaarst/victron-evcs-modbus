# Write Confirmation Design

**Date:** 2026-03-14
**Status:** Approved

## Goal

After writing a register via FC6 (scalar) or FC16 (string), perform a read-back (FC3) to confirm the device accepted the new value. If the read-back value does not match what was written, report a warning. Useful for detecting device-side range clamping or silent rejection.

## Current State

- `write_register()` in `cli.py` returns `bool` (True = write OK, False = failed)
- No read-back performed after any write
- CLI `--write` command: prints success or error, exits 1 on failure
- TUI `action_write_all()`: calls `write_register()`, notifies on failure

## Architecture

### write_register() signature change (`cli.py`)

Change return type from `bool` to `tuple[bool, bool | None]`:

```python
def write_register(
    client: Any,
    reg: Register | StringRegister,
    value: int | str,
    unit_id: int = 1,
    verify: bool = False,
) -> tuple[bool, bool | None]:
    """Write a single register via Modbus FC6 (scalar) or FC16 (string).

    Returns (success, verified):
      (True,  None)  — write OK, verify not requested
      (True,  True)  — write OK, read-back matched
      (True,  False) — write OK, read-back mismatch (device may have clamped value)
      (False, None)  — write failed
    """
```

`verify=False` default keeps all existing callers valid after tuple-unpacking update.

### Read-back logic (inside write_register, when verify=True)

After a successful write:

- **Scalar (`Register`)**: `client.read_holding_registers(address=reg.address, count=1, device_id=unit_id)`. Compare `response.registers[0]` to the raw wire value (unsigned). For int16 registers where `value < 0`, the wire value is `value + 65536`; compare the raw register word.
- **String (`StringRegister`)**: `client.read_holding_registers(address=reg.address, count=reg.register_count, device_id=unit_id)`. Decode with `struct.pack(f"<{n}H").rstrip(b"\x00").decode(encoding)` and compare to the written string.
- **If read-back itself fails** (Modbus error or exception): return `(True, None)` — write succeeded, verification inconclusive.

### CLI _handle_write() (`cli.py`)

Pass `verify=True`:

```python
success, verified = write_register(client, reg, raw_value, unit_id=args.unit_id, verify=True)
```

Output:
- Write failed → `[red]Write failed for address {address}[/red]`, exit 1 (unchanged)
- Write OK, verified=True → `[green]Written {address} ({name}): {value}{unit}[/green]` (unchanged appearance)
- Write OK, verified=False → green success line **plus** `[yellow]Warning: read-back value differs — device may have clamped the value[/yellow]`
- Write OK, verified=None → green success line only (read-back inconclusive, no warning)

### TUI action_write_all() (`tui.py`)

Pass `verify=True`:

```python
success, verified = write_register(self.modbus_client, reg, raw_value, unit_id=self.unit_id, verify=True)
```

Track mismatches. After all writes complete, build notification:
- All writes OK, no mismatches → `"Written N register(s)"` (unchanged)
- Any mismatches → `"Written N register(s) — ⚠ M read-back mismatch(es)"`, severity `"warning"`
- Write failure → unchanged error notification

### Caller updates

All existing callers of `write_register()` must be updated to unpack the tuple:

In `cli.py` (`_handle_write`): already updated above.

In `tui.py` (`action_write_all`): already updated above.

In `tests/test_cli.py` and `tests/test_tui.py`: update assertions from `assert write_register(...) is True` to `success, _ = write_register(...); assert success is True` (or equivalent).

## Testing

### `tests/test_cli.py` additions

- `test_write_register_returns_tuple` — `write_register(client, reg, 10)` returns `(True, None)`
- `test_write_register_verify_match` — mock read-back returns same value; result is `(True, True)`
- `test_write_register_verify_mismatch` — mock read-back returns different value; result is `(True, False)`
- `test_write_register_verify_readback_error` — mock read-back returns error; result is `(True, None)`
- `test_write_cli_verify_mismatch_prints_warning` — `--write` with mismatched read-back; captured output contains "Warning"

### `tests/test_tui.py` additions

- `test_tui_write_mismatch_notification` — mock read-back returns different value; after ctrl+s, notification contains "mismatch"

### Existing test updates

All existing tests that do `assert write_register(...) is True/False` or `write_register(...) is False` must be updated to unpack the tuple. These tests do not need new mock setup for verify (verify=False by default, so read-back is not called).

## Files Touched

| File | Change |
|------|--------|
| `cli.py` | Change return type of `write_register()`; add `verify` param and read-back logic; update `_handle_write()` |
| `tui.py` | Update `action_write_all()` to use `verify=True` and handle mismatch notification |
| `tests/test_cli.py` | Update existing callers; add 5 new tests |
| `tests/test_tui.py` | Update existing callers; add 1 new test |

## Out of Scope

- Verify on TUI refresh (read-back only applies to writes)
- Configurable verify timeout
- Storing mismatch history
