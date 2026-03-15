# Interactive Default Mode Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the interactive TUI the default mode, add `--read` for explicit table output, and remove `--interactive`.

**Architecture:** Three changes in lockstep — argparse restructure (mode group becomes `--read | --write`, `--changed` goes standalone), mode dispatch rewrite (`if write → elif read/changed → else TUI`), and TUI import+launch moves to the new `else` branch. Five new tests cover the four new routing cases; one existing test (`test_unit_id_cli_flag`) gets `--read` added to keep it in table mode.

**Tech Stack:** Python 3.12, argparse, pytest, pymodbus, rich, textual (TUI)

**Spec:** `docs/superpowers/specs/2026-03-14-interactive-default-design.md`
**Beads:** `victron_evcs_modbus-my8`

---

## Chunk 1: Tests + Implementation

### Task 1: Write failing tests

**Files:**
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write 5 new failing tests**

Append to `tests/test_cli.py`:

```python
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

    # If TUI path is taken, this will cause ImportError — good safety net
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
    """--changed alone (no --read) → table path (not TUI)."""
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
```

- [ ] **Step 2: Run tests to verify they fail**

```
uv run pytest tests/test_cli.py::test_default_mode_launches_tui tests/test_cli.py::test_read_flag_prints_table tests/test_cli.py::test_read_and_changed_flags tests/test_cli.py::test_changed_flag_implies_read tests/test_cli.py::test_changed_with_write_ignored -v
```

Expected: all 5 FAIL.
- `test_default_mode_launches_tui`: FAIL — default mode prints table, not TUI
- `test_read_flag_prints_table`: FAIL — `--read` is unrecognized
- `test_read_and_changed_flags`: FAIL — `--read` is unrecognized
- `test_changed_flag_implies_read`: FAIL — `--changed` currently mutually exclusive with (nothing here but...)... actually this may pass since `--changed` already routes to table. Re-check: currently `--changed` routes to table AND `sys.modules["tui"] = None` won't be triggered. This test may already pass — that's acceptable, leave it.
- `test_changed_with_write_ignored`: FAIL — `--changed` and `--write` are currently mutually exclusive (argparse error)

- [ ] **Step 3: Commit failing tests**

```bash
git add tests/test_cli.py
git commit -m "test: add failing tests for interactive-default mode (my8)"
```

---

### Task 2: Implement argparse restructure and mode dispatch

**Files:**
- Modify: `cli.py:320-407` (`main()`)
- Modify: `tests/test_cli.py:454-470` (`test_unit_id_cli_flag` — add `--read`)

- [ ] **Step 1: Update `main()` in `cli.py`**

Replace the `mode_group` block and mode dispatch in `main()`. The full replacement covers lines 331–402:

Old `mode_group` block (lines 331–343):
```python
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--changed", action="store_true",
        help="Show only registers that differ from their factory default",
    )
    mode_group.add_argument(
        "--write", nargs=2, metavar=("ADDRESS", "VALUE"),
        help="Write VALUE to register at ADDRESS (e.g. --write 5016 10)",
    )
    mode_group.add_argument(
        "--interactive", action="store_true",
        help="Launch interactive TUI editor",
    )
```

New `mode_group` block:
```python
    parser.add_argument(
        "--changed", action="store_true",
        help="Show only registers that differ from factory default (implies --read; ignored with --write)",
    )

    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--read", action="store_true",
        help="Print register table and exit",
    )
    mode_group.add_argument(
        "--write", nargs=2, metavar=("ADDRESS", "VALUE"),
        help="Write VALUE to register at ADDRESS (e.g. --write 5016 10)",
    )
```

Old mode dispatch block (lines 391–402):
```python
    if args.interactive:
        from tui import RegisterEditorApp
        try:
            RegisterEditorApp(client, registers, values, unit_id=args.unit_id).run()
        finally:
            client.close()
        return

    client.close()
    registers_to_display = filter_changed(registers, values) if args.changed else registers
    table = build_table(registers_to_display, values)
    console.print(table)
```

New mode dispatch block:
```python
    if args.read or args.changed:
        client.close()
        registers_to_display = filter_changed(registers, values) if args.changed else registers
        table = build_table(registers_to_display, values)
        console.print(table)
    else:
        from tui import RegisterEditorApp
        try:
            RegisterEditorApp(client, registers, values, unit_id=args.unit_id).run()
        finally:
            client.close()
```

- [ ] **Step 2: Fix `test_unit_id_cli_flag` — add `--read`**

This test calls `main()` with no mode flag. After the change it would try to launch the TUI. Add `--read` to its argv:

Old (line ~467):
```python
    monkeypatch.setattr(sys, "argv", ["cli.py", "127.0.0.1", "--unit-id", "3"])
```

New:
```python
    monkeypatch.setattr(sys, "argv", ["cli.py", "127.0.0.1", "--unit-id", "3", "--read"])
```

- [ ] **Step 3: Run the full test suite**

```
uv run pytest -v
```

Expected: all tests pass. Specifically verify:
- 5 new tests pass
- `test_changed_flag_calls_filter_changed` still passes
- `test_unit_id_cli_flag` still passes
- All existing `--write` tests still pass

- [ ] **Step 4: Commit**

```bash
git add cli.py tests/test_cli.py
git commit -m "feat: make TUI the default mode; add --read, remove --interactive (my8)"
```

---

## Chunk 2: Documentation

### Task 3: Update README

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update the Options table**

Old rows to remove/change:
```markdown
| `--changed` | — | Show only registers that differ from factory default |
| `--write ADDR VALUE` | — | Write a value to a register |
| `--interactive` | — | Launch TUI editor |
```

New rows:
```markdown
| `--read` | — | Print register table and exit (default: launch TUI) |
| `--changed` | — | Show only registers that differ from factory default (implies `--read`) |
| `--write ADDR VALUE` | — | Write a value to a register |
```

- [ ] **Step 2: Update the "Read registers" section heading and examples**

Old heading and first example block:
```markdown
### Read registers (default)

```bash
# All 115 registers
uv run python cli.py 192.168.0.128
```

New heading and first example block:
```markdown
### Read registers (table output)

```bash
# All 115 registers
uv run python cli.py 192.168.0.128 --read
```

Also update the `--changed` example:
```bash
# Show only registers that differ from their factory default
uv run python cli.py 192.168.0.128 --changed
```
(no change needed for `--changed` example — still works standalone)

- [ ] **Step 3: Update the "Interactive TUI" section**

Old:
```markdown
### Interactive TUI

```bash
uv run python cli.py <host> --interactive [--category ...] [--address ...] [--name ...]
```
```

New:
```markdown
### Interactive TUI (default)

```bash
# Default: launches TUI editor
uv run python cli.py <host> [--category ...] [--address ...] [--name ...]
```
```

- [ ] **Step 4: Run tests to confirm nothing broken**

```
uv run pytest -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add README.md
git commit -m "docs: update README for interactive-default and --read flag (my8)"
```
