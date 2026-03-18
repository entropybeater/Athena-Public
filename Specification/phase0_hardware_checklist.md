# Petri Dish Monitor V2 — Phase 0 Hardware Verification Checklist
### XIAO ESP32-S3 Sense | Pre-Firmware Board Verification
**Reference:** V2 Firmware Specification v1.0 §2, V2 Development Roadmap Phase 0  
**Date Checked:** _______________  
**Checked By:** _______________

> **IMPORTANT:** No firmware development begins until every item below is marked PASS.  
> A single FAIL is a project blocker. Resolve before proceeding.

---

## ⚡ LED Flash Ring

| # | Check | How to Verify | PASS / FAIL | Consequence if Wrong |
|---|-------|---------------|-------------|----------------------|
| 1 | **LED ring has onboard current-limiting resistors** | Visually inspect the PCB of the 325mm LED ring for series resistors on each LED segment. Do NOT apply power before confirming. | ✅ PASS | Without resistors, powering the ring through the MOSFET will immediately destroy the LEDs and possibly the MOSFET. |
| 2 | **Flyback diode (1N5819) orientation is correct** | Stripe (cathode) faces the positive supply rail (5V side). Anode faces GND. With power off, use a multimeter in diode mode — low reading one way, open the other. | ✅ PASS | Reverse orientation = no flyback protection. MOSFET will be destroyed by inductive kickback on LED ring switch-off. |
| 3 | **MOSFET gate resistor (220Ω) is populated** | Measure resistance between GPIO43 (D6) pad and the MOSFET gate pin. Should read ~220Ω. | ✅ PASS | Without gate resistor, drive current is uncontrolled. Risk of GPIO latch-up or MOSFET oscillation at high frequencies. |
| 4 | **MOSFET pull-down resistor (10kΩ) is populated** | Measure resistance between MOSFET gate and GND. Should read ~10kΩ. | ✅ PASS | Without pull-down, the gate floats on boot/deep sleep. LED ring may fire unexpectedly at power-on before firmware controls the pin. |

---

## 🔋 Battery Monitoring Circuit

| # | Check | How to Verify | PASS / FAIL | Consequence if Wrong |
|---|-------|---------------|-------------|----------------------|
| 5 | **USB-C breakout board exposes SBU / A8 / B8 pins** | Confirm the chosen USB-C breakout has a labeled SBU1 or SBU2 (A8/B8) pad accessible for your voltage divider connection. | ⏳ DEFERRED (breakout board en route) | Battery monitoring is impossible without SBU pin access. ADS1115 will read nothing. Battery level always UNKNOWN — auto-OTA permanently blocked. |
| 6 | **USB-C cable is 3.1 or 3.2 spec (SBU pins present)** | Check cable spec on packaging. USB 2.0 cables omit SBU pins entirely. Use a USB-C 3.1 or 3.2 cable. | ⏳ DEFERRED (breakout board en route) | USB 2.0 cable silently fails battery monitoring — SBU pins are not connected in cable. ADS1115 reads 0V. Battery always UNKNOWN. |
| 7 | **V50 SBU pin outputs expected voltage range (1.6V – 2.1V)** | Connect V50 via 3.1/3.2 USB-C cable. With multimeter, probe the SBU pad on the breakout board relative to GND. Empty V50: ~1.6V. Full V50: ~2.1V. | ⏳ DEFERRED (breakout board en route) | If SBU voltage is outside this range, the voltage divider formula and ADS1115 PGA range assumptions are wrong. Battery percentage calculations will be incorrect. |

---

## 🌡️ I2C Sensor Chain (BME280 + ADS1115)

| # | Check | How to Verify | PASS / FAIL | Consequence if Wrong |
|---|-------|---------------|-------------|----------------------|
| 8 | **BME280 I2C address is 0x76** | Board has no exposed SDO/CSB pins (hardwired on PCB). Upload I2C scanner sketch (`Wire.begin(5, 6)`, scan addresses 1–126). Confirm BME280 responds at **0x76**. If found at 0x77 → log as spec deviation, update driver address before Phase 2. | ✅ PASS (0x76) | If BME280 not found at any address: wiring fault or board-level I2C mode not enabled (CSB wired wrong internally). If found at 0x77: functional but requires driver config change. |
| 9 | ~~BME280 CSB pin → 3.3V~~ | **Covered by Check 8.** CSB is hardwired internally on this breakout. If the BME280 responds on I2C at any address, CSB is correctly set to I2C mode. | ✅ PASS (via Check 8) | N/A — subsumed by Check 8 result. |
| 10 | **ADS1115 ADDR pin → GND (I2C address 0x48)** | On the ADS1115 breakout, confirm ADDR is tied to GND. Floating ADDR pin = undefined address. Multimeter continuity check: ADDR to GND. | ✅ PASS | Floating ADDR = address undefined / drifts. Firmware targets 0x48. ADS1115 will be unreachable. Battery monitoring always UNKNOWN. |
| 11 | **I2C pull-up resistors: 4.7kΩ on SDA (GPIO5) and SCL (GPIO6)** | Measure resistance from SDA to 3.3V and from SCL to 3.3V (power off). Each should read ~4.7kΩ. Only one pull-up per line (not one per device). | ✅ PASS (SDA: 4.5kΩ, SCL: 4.4kΩ) | Missing pull-ups = I2C bus never pulls HIGH. All I2C transactions fail. Both BME280 and ADS1115 unreachable. Parallel pull-ups (two per line) = too low impedance, violates I2C spec. |

---

## 🖥️ Microcontroller and Module

| # | Check | How to Verify | PASS / FAIL | Consequence if Wrong |
|---|-------|---------------|-------------|----------------------|
| 12 | **XIAO ESP32-S3 Sense boots and USB CDC serial responds** | Connect via USB-C. Open a serial monitor at 115200 baud. You should see the ROM bootloader output or an existing sketch running. Verify the COM port enumerates. | ✅ PASS (confirmed via I2C scanner upload & serial output) | If no serial response, the board is damaged or the USB-C cable is charge-only (no data lines). Cannot upload firmware. |
| 13 | **HaLow module seats correctly on B2B connector (if present)** | Physically confirm the Wio-WM6108 is fully seated on the board-to-board connector with no bent pins. Apply gentle pressure to ensure full seating. *(Skip if testing WiFi-only build)* | ✅ PASS | Partially seated HaLow module = unreliable SPI bus. Will cause intermittent failures that are hard to diagnose in firmware. |
| 14 | **GPIO41 (D12) and GPIO42 (D11) are physically blocked by HaLow B2B connector** | With HaLow module installed, visually confirm these two pads are underneath the connector and inaccessible. Do not attempt to solder to them. *(Skip if no HaLow module)* | ✅ PASS | These pins are documented as unavailable in the spec. Any accidental use of GPIO41/42 in firmware will cause undefined behavior. |

---

## ✅ Phase 0 Sign-Off

### Part A — Checks 1–4, 8–14 (Hardware Verified)

| Item | Status |
|------|--------|
| Checks 1–4 (LED Flash Ring): PASS | ✅ Yes |
| Checks 8–14 (I2C Sensor Chain + MCU/Module): PASS | ✅ Yes |
| LED ring current-limiting confirmed | ✅ Yes |
| Checks 5, 6, 7 (Battery Monitoring): PENDING component arrival | ⏳ Deferred — USB-C breakout board en route |

**Part A Sign-off:** BCB  **Date:** 2026-03-17

> ⚠️ **Note:** Checks 5, 6, and 7 (Battery Monitoring Circuit) cannot be completed until the USB-C breakout board arrives. All other Phase 0 checks are PASS. Phase 1 firmware development may proceed for all subsystems **except** battery monitoring. Complete Part B sign-off before implementing battery monitoring in Phase 2.

---

### Part B — Checks 5–7 (Battery Monitoring — Pending Component)

| Item | Status |
|------|--------|
| Check 5: USB-C breakout exposes SBU pins | ☐ PASS  ☐ FAIL |
| Check 6: USB-C cable is 3.1 or 3.2 spec | ☐ PASS  ☐ FAIL |
| Check 7: V50 SBU pin voltage 1.6V–2.1V confirmed | ☐ PASS  ☐ FAIL |
| V50 SBU voltage range confirmed with multimeter | ☐ Yes |
| USB-C cable is 3.1 or 3.2 spec | ☐ Yes |

**Part B Sign-off:** _______________________________  **Date:** _______________

**Phase 0 Fully Complete:** ☐ YES — all 14 checks PASS, cleared to begin Phase 2 battery monitoring firmware.

---

**Notes / Findings:**

```
2026-03-17: Checks 1-4, 8-14 verified PASS. Checks 5-7 deferred pending USB-C breakout board arrival.
BME280 confirmed at 0x76 (spec target). ADS1115 confirmed at 0x48 (spec target).
I2C pull-ups measured: SDA 4.5kΩ, SCL 4.4kΩ (within tolerance of 4.7kΩ spec).
```

---

*Reference: V2 Firmware Specification v1.0 §2.2–2.6, §24 | V2 Development Roadmap Phase 0*  
*Document Version: 1.0 — 2026-03-16*
