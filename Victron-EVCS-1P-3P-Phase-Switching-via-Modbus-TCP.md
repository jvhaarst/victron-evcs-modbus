# Victron EVCS — 1P/3P Phase Switching via Modbus TCP

> **Status:** Unofficial / unsupported feature, present in current EVCS firmware as preparation
> for the next hardware generation. Use at your own risk.  
> **Hardware prerequisite:** The single factory 4-pole contactor must be replaced by two 2-pole
> contactors (one for L1+N, one for L2+L3) before this configuration has any effect.

---

## Connection Details

| Parameter | Value |
|---|---|
| Protocol | Modbus TCP |
| Port | 502 |
| Slave address | 1 |

If IP whitelisting is enabled on the EVCS, add your client IP to the allowlist first.

---

## Step 1 — Unlock Phase Switching

Write the following register first. Until this is set, registers 5055–5059 return `65535` and cannot be modified.

| Register | Value | Description |
|---|---|---|
| **5100** | `1` | Enable phase switching feature |

> **Note:** Some firmware versions have this register at address **5101** instead of 5100.
> If writing 5100 has no effect, try 5101. Verify by reading back the value — it should
> return `1` after a successful write.

After setting this register, the EVCS display will show an updated **Settings** menu with phase selection options for AUTO and MANUAL mode.

---

## Step 2 — Phase Switching Registers (5055–5059)

These registers become writable after Step 1.

| Register | Name | Range | Description |
|---|---|---|---|
| **5055** | Manual mode phase | `0` / `1` | `0` = three-phase, `1` = single-phase |
| **5056** | Auto mode phase | `0` / `1` / `2` | `0` = 3P only, `1` = 1P only, `2` = auto 1P↔3P |
| **5057** | Switch-up threshold (W) | integer | Charge power at which EVCS switches **1P → 3P** |
| **5058** | Switch-down threshold (W) | integer | Charge power at which EVCS switches **3P → 1P** |
| **5059** | Switching delay (s) | integer | Time the threshold must be exceeded before switching |

> **Important:** Registers 5057 and 5058 measure **actual EV charging power**, not solar
> surplus. In AUTO mode the EVCS continuously adjusts current to keep net grid flow near 0 W,
> so charging power approximates available solar surplus — but the trigger is based on the
> charge power reading, not a grid flow measurement.

---

## Step 3 — Recommended Values for a 3×16 A Setup

### Power reference

| Situation | Power |
|---|---|
| Maximum single-phase (16 A × 230 V) | **3,680 W** |
| Minimum three-phase (6 A × 3 × 230 V) | **4,140 W** |
| Gap (unavoidable with 16 A single-phase) | **≈ 460 W** |

Because single-phase can never reach the three-phase minimum, the switch-up threshold (5057) must be set **below** the 1P ceiling rather than above the 3P floor. This means the EVCS switches to 3P when 1P charging is nearly maxed out, implying sufficient solar surplus.

### Register values

| Register | Recommended value | Rationale |
|---|---|---|
| **5055** | `0` | Manual/scheduled mode uses **three-phase** (full-power grid charging) |
| **5056** | `2` | AUTO mode uses automatic 1P ↔ 3P switching |
| **5057** | `3500` | Switch to 3P when 1P charge power exceeds ~3,500 W (≈ 15.2 A) |
| **5058** | `4200` | Switch back to 1P when 3P charge power drops below ~4,200 W (≈ 6.1 A/phase) |
| **5059** | `60` | Wait 60 s before switching, to filter cloud transients |

### Hysteresis visualised

```
  W  │
     │
11040─      ┌─────────────┐
     │      │             │
     │      │   3P zone   │
     │      │             │
 4200─ ─ ─ ─│─ ─ ─ ─ ─ ─ ─│─ ─ ─ reg 5058 = 4200 W → switch DOWN to 1P
     │      │             │
 4140─      └─────────────┘  ← 3P minimum (6 A × 3 phases)
     │         ▲     ▲
     │      ~460 W GAP — neither mode can operate here
     │         ▼     ▼
 3680─      ┌─────────────┐  ← 1P maximum (16 A × 1 phase)
     │      │             │
 3500─ ─ ─ ─│─ ─ ─ ─ ─ ─ ─│─ ─ ─ reg 5057 = 3500 W → switch UP to 3P
     │      │             │
     │      │   1P zone   │
     │      │             │
 1380─      └─────────────┘  ← 1P minimum (6 A × 1 phase)
     │
     └──────────────────────
```

Reading the diagram:

- While charging in **1P mode**, power rises with increasing solar surplus. When it crosses
  the 5057 threshold (3,500 W), the EVCS switches to 3P after the 5059 delay.
- While charging in **3P mode**, power falls as solar surplus decreases. When it drops below
  the 5058 threshold (4,200 W), the EVCS switches back to 1P after the 5059 delay.
- The ~460 W **gap** between the 1P ceiling (3,680 W) and the 3P floor (4,140 W) means a
  brief power interruption occurs during every phase transition. This is inherent to a 16 A
  single-phase limit and cannot be eliminated without upgrading to a 20 A or 32 A circuit.

---

## Step 4 — Operating Modes Summary

| Mode | Phase | Max power | Use case |
|---|---|---|---|
| **AUTO** | 1P ↔ 3P (automatic) | 3,680 W (1P) / 11 kW (3P) | Solar surplus charging |
| **MANUAL** | 3P (per register 5055) | 11 kW | On-demand full-power grid charging |
| **SCHEDULED** | 3P (follows register 5055) | 11 kW | Timed grid charging (e.g. off-peak) |

> **Note:** The "Manual mode phase" selector on the EVCS display controls **both** Manual
> and Scheduled modes. Setting it to 3-phase (register 5055 = `0`) ensures overnight
> scheduled charging runs at full 3P power.

---

## Modbus Write Sequence

```
1. Write 5100 = 1          (or 5101 = 1 if 5100 has no effect)
2. Read back 5100/5101     (verify value is 1, not 65535)
3. Write 5055 = 0          (manual/scheduled → 3-phase)
4. Write 5056 = 2          (auto → 1P/3P switching)
5. Write 5057 = 3500       (switch-up threshold)
6. Write 5058 = 4200       (switch-down threshold)
7. Write 5059 = 60         (switching delay in seconds)
```

---

## Tuning Notes

- If switching happens too often on partly cloudy days, **increase register 5059** (delay).
- If the EVCS stays on 1P even with plenty of sun, **decrease register 5057** slightly.
- If it stays on 3P with insufficient surplus and draws heavily from the grid, **increase
  register 5058** slightly.
- Some cars (including the Hyundai Ioniq 5 / Kia EV6) accept charge rates well below the
  IEC 61851 minimum of 6 A, so the 1P floor of ~1.38 kW (6 A × 230 V) should not be
  a problem on the car side.

---

## References

- Victron Community (new): https://community.victronenergy.com/t/charging-an-ev-with-excess-solar-switching-between-1p-and-3p/21181
- Victron Community (archive): https://communityarchive.victronenergy.com/questions/243413/evcs-automatic-switching-between-1p-and-3p.html
- EVCS phase switching hardware guide (PDF by Heiko Braak): https://communityarchive.victronenergy.com/storage/attachments/evcs-phasenumschaltung.pdf