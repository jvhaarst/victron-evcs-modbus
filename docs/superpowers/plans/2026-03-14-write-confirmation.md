# Write Confirmation Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** After a Modbus write, read back the register to confirm the device accepted the value; warn if it differs (device may have clamped it).

**Architecture:** Add `verify: bool = False` to `write_register()` and change return type from `bool` to `tuple[bool, bool | None]`. When `verify=True`, read back after a successful write and compare. `_handle_write()` in `cli.py` always verifies; TUI `action_write_all()` always verifies and reports mismatch count in the notification.

**Tech Stack:** Python 3.12, pymodbus, Textual, pytest

---

## Chunk 1: Core function change + CLI update

### Task 1: Change write_register() return type, add verify parameter and read-back logic

**Files:**
- Modify: `cli.py`
- Modify: `tests/test_cli.py`

The function currently returns `bool`. It will return `tuple[bool, bool | None]`:
- `(True, None)` — write OK, verify not requested
- `(True, True)` — write OK, read-back matched
- `(True, False)` — write OK, read-back mismatch
- `(False, None)` — write failed

- [ ] **Step 1: Write new tests (they will fail)**

Add after `test_write_register_exception_returns_false` in `tests/test_cli.py`:

```python
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
    read_resp.registers = [10]  # same as written value
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
    read_resp.registers = [6]  # device clamped to 6, not 10
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
```

- [ ] **Step 2: Run new tests to verify they fail**

```bash
uv run pytest tests/test_cli.py::test_write_register_returns_tuple -v
```

Expected: FAIL — `write_register()` does not return a tuple.

- [ ] **Step 3: Update write_register() signature, return type, and add read-back logic**

Replace the entire `write_register()` function in `cli.py` with:

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
    try:
        if isinstance(reg, StringRegister):
            raw_bytes = value.encode(reg.encoding)
            padded = raw_bytes.ljust(reg.register_count * 2, b"\x00")
            words = list(struct.unpack(f"<{reg.register_count}H", padded))
            response = client.write_registers(
                address=reg.address, values=words, device_id=unit_id
            )
        else:
            if not isinstance(value, int):
                return False, None
            wire_value = (value + 65536) if value < 0 else value
            response = client.write_register(
                address=reg.address, value=wire_value, device_id=unit_id
            )
        if response.isError():
            return False, None
        if not verify:
            return True, None
        # Read back to verify device accepted the value
        try:
            count = reg.register_count if isinstance(reg, StringRegister) else 1
            rb = client.read_holding_registers(
                address=reg.address, count=count, device_id=unit_id
            )
            if rb.isError():
                return True, None
            if isinstance(reg, StringRegister):
                rb_bytes = struct.pack(f"<{reg.register_count}H", *rb.registers)
                rb_str = rb_bytes.rstrip(b"\x00").decode(reg.encoding)
                return True, rb_str == value
            else:
                return True, rb.registers[0] == wire_value
        except Exception:
            return True, None
    except Exception:
        return False, None
```

- [ ] **Step 4: Update existing test_cli.py callers to unpack the tuple**

Find and update all 5 existing direct callers of `write_register()` in `tests/test_cli.py`:

In `test_write_register_scalar`:
```python
# Before:
assert write_register(mock_client, reg, 10) is True
# After:
success, _ = write_register(mock_client, reg, 10)
assert success is True
```

In `test_write_register_scalar_error`:
```python
# Before:
assert write_register(mock_client, reg, 10) is False
# After:
success, _ = write_register(mock_client, reg, 10)
assert success is False
```

In `test_write_register_int16_negative`:
```python
# Before:
result = write_register(mock_client, reg, -500)
assert result is True
# After:
success, _ = write_register(mock_client, reg, -500)
assert success is True
```

In `test_write_register_string`:
```python
# Before:
assert write_register(mock_client, reg, "My Charger") is True
# After:
success, _ = write_register(mock_client, reg, "My Charger")
assert success is True
```

In `test_write_register_exception_returns_false`:
```python
# Before:
assert write_register(mock_client, reg, 10) is False
# After:
success, _ = write_register(mock_client, reg, 10)
assert success is False
```

In `test_write_register_uses_unit_id` (result is currently unused — no change needed since tuple return is ignored, but update for explicitness):
```python
# Before:
write_register(client, reg, 10, unit_id=3)
# After:
success, _ = write_register(client, reg, 10, unit_id=3)
assert success is True
```

- [ ] **Step 5: Run all new and updated tests**

```bash
uv run pytest tests/test_cli.py::test_write_register_returns_tuple tests/test_cli.py::test_write_register_verify_match tests/test_cli.py::test_write_register_verify_mismatch tests/test_cli.py::test_write_register_verify_readback_error tests/test_cli.py::test_write_register_scalar tests/test_cli.py::test_write_register_scalar_error tests/test_cli.py::test_write_register_int16_negative tests/test_cli.py::test_write_register_string tests/test_cli.py::test_write_register_exception_returns_false -v
```

Expected: All PASS.

- [ ] **Step 6: Run full test suite**

```bash
uv run pytest -q
```

Expected: All tests PASS.

Note: `cli.py`'s `_handle_write()` currently has `success = write_register(...)` which will now receive a tuple. This will cause a type issue but NOT break tests because `_handle_write` is only tested via CLI integration tests that don't check the return value directly. Fix this in Task 2.

- [ ] **Step 7: Commit**

```bash
git add cli.py tests/test_cli.py
git commit -m "feat: change write_register() to return tuple[bool, bool|None], add verify parameter"
```

---

### Task 2: Update _handle_write() to use verify=True and print warning on mismatch

**Files:**
- Modify: `cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_cli.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_cli.py::test_write_cli_verify_mismatch_prints_warning -v
```

Expected: FAIL — no warning printed.

- [ ] **Step 3: Update _handle_write() in cli.py**

Replace the write call and success handling in `_handle_write()`:

```python
    try:
        success, verified = write_register(client, reg, raw_value, unit_id=args.unit_id, verify=True)
    finally:
        client.close()

    if success:
        if isinstance(reg, StringRegister):
            display = str(raw_value)
            unit = ""
        else:
            display = format_value(raw_value, reg.scale)
            unit = f" {reg.unit}" if reg.unit else ""
        console.print(f"[green]Written {address} ({reg.name}): {display}{unit}[/green]")
        if verified is False:
            console.print("[yellow]Warning: read-back value differs — device may have clamped the value[/yellow]")
    else:
        console.print(f"[red]Write failed for address {address}[/red]")
        sys.exit(1)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_cli.py::test_write_cli_verify_mismatch_prints_warning -v
```

Expected: PASS.

- [ ] **Step 5: Run full test suite**

```bash
uv run pytest -q
```

Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add cli.py tests/test_cli.py
git commit -m "feat: verify write in --write command, print warning on read-back mismatch"
```

---

## Chunk 2: TUI update

### Task 3: Update TUI action_write_all() for verify=True and mismatch notification

**Files:**
- Modify: `tui.py`
- Modify: `tests/test_tui.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_tui.py`:

```python
@pytest.mark.asyncio
async def test_tui_write_mismatch_notification(mock_client):
    from tui import RegisterEditorApp
    reg = Register(5016, "Charging current", "uint16", 1, "A", default=6, access="R/W")
    registers = [reg]
    values = {5016: 10}
    # Configure read-back to return a different value (device clamped to 6)
    rb_response = MagicMock()
    rb_response.isError.return_value = False
    rb_response.registers = [6]
    mock_client.read_holding_registers.return_value = rb_response
    notifications = []
    async with RegisterEditorApp(mock_client, registers, values).run_test() as pilot:
        pilot.app.pending[5016] = 16
        original_notify = pilot.app.notify
        pilot.app.notify = lambda msg, **kw: notifications.append((msg, kw)) or original_notify(msg, **kw)
        await pilot.press("ctrl+s")
        await pilot.pause()
        assert any("mismatch" in msg.lower() for msg, _ in notifications)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_tui.py::test_tui_write_mismatch_notification -v
```

Expected: FAIL — no mismatch notification.

- [ ] **Step 3: Update action_write_all() in tui.py**

Replace the entire `action_write_all()` method:

```python
    def action_write_all(self) -> None:
        if not self.pending:
            self.notify("Nothing to write", severity="information")
            return
        failed_address = None
        written: list[int] = []
        mismatch_count = 0
        for address, raw_value in list(self.pending.items()):
            reg = self._reg_by_key.get(str(address))
            if reg is None:
                continue
            success, verified = write_register(
                self.modbus_client, reg, raw_value, unit_id=self.unit_id, verify=True
            )
            if success:
                self.values[address] = raw_value
                del self.pending[address]  # remove only successfully written
                written.append(address)
                self._refresh_row(address)
                if verified is False:
                    mismatch_count += 1
            else:
                failed_address = address
                break  # stop; failed register + all subsequent remain in self.pending
        self._update_subtitle()
        if failed_address is not None:
            self.notify(
                f"Write failed at address {failed_address} — check connection",
                severity="error",
            )
        elif written:
            if mismatch_count:
                self.notify(
                    f"Written {len(written)} register(s) — ⚠ {mismatch_count} read-back mismatch(es)",
                    severity="warning",
                )
            else:
                self.notify(f"Written {len(written)} register(s)", severity="information")
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_tui.py::test_tui_write_mismatch_notification -v
```

Expected: PASS.

- [ ] **Step 5: Run full test suite**

```bash
uv run pytest -q
```

Expected: All tests PASS.

Note on existing TUI tests: `mock_client.read_holding_registers` is not configured in the existing `mock_client` fixture. It returns a `MagicMock()`, and `MagicMock().isError()` returns a truthy `MagicMock`, so the verify read-back will treat the result as "read-back error" and return `(True, None)` — which means no mismatch, notification is the same as before. Existing tests are unaffected.

- [ ] **Step 6: Commit**

```bash
git add tui.py tests/test_tui.py
git commit -m "feat: use verify=True in TUI action_write_all, notify on read-back mismatch"
```
