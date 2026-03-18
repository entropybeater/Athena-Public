# Petri Dish Monitor V2 — Phase 1 Proof of Concept Checklist
### XIAO ESP32-S3 Sense | Risk Elimination Before Architecture Lock-In
**Reference:** V2 Firmware Specification v1.0 §1, V2 Development Roadmap Phase 1  
**Date Started:** 2026-03-17  
**Checked By:** _______________

> **IMPORTANT:** Phase 2 firmware development does not begin until Phase 1 exit criteria are met.  
> **Exit Criteria:** HaLow connects to HaLowLink 2 AND transfers a test image. Camera mode switching works without deinit/reinit.

---

## Phase 1 Overview

| Track | Goal | Status |
|---|---|---|
| **1A — HaLow Library Evaluation** | Prove WM6108 works on PlatformIO, connects to HaLow router, transfers test image | 🔴 In Progress |
| **1B — Camera Mode Switching** | Prove OV3660 can switch YUV↔JPEG via register writes without deinit/reinit | ⬜ Not Started |
| **1C — 2.4GHz WiFi Baseline** | POST a 400KB JPEG to test server, measure throughput for comparison | ⬜ Not Started |

---

## 🔌 Track 1A — HaLow Library Evaluation (HIGHEST PRIORITY)

### Step 1: Library Research and Evaluation

> **⚠️ Architecture Finding (2026-03-17):** The WM6108 does NOT have an Arduino/PlatformIO library. It uses **MorseMicro MM-IoT-SDK** via **ESP-IDF** (Espressif's native framework). Phase 1A validation will use ESP-IDF examples. Architecture decision (ESP-IDF vs Arduino) deferred until after HaLow throughput is confirmed.

| # | Check | How to Verify | PASS / FAIL | Notes |
|---|-------|---------------|-------------|-------|
| 1A-1 | **Identify available library for Wio-WM6108** | Research complete. No Arduino/PlatformIO library exists. WM6108 uses MorseMicro MM-IoT-SDK via ESP-IDF. | ✅ PASS | No Arduino lib. ESP-IDF only. |
| 1A-2 | **Evaluate library maturity** | `Seeed-Studio/mm-iot-esp32` on GitHub. Last updated 2026-03-13. Active development. Official Seeed fork of MorseMicro SDK. Examples include: scan, sta_connect, iperf, web_camera_server. | ✅ PASS | Active. Seeed-maintained fork. |
| 1A-3 | **ESP-IDF v5.1.1 installed and idf.py functional** | Install ESP-IDF v5.1.1 per Seeed wiki. Run `idf.py --version` → should return `ESP-IDF v5.1.1`. | ☐ PASS  ☐ FAIL | Required for mm-iot-esp32 |
| 1A-4 | **mm-iot-esp32 repo cloned and MMIOT_ROOT set** | `git clone https://github.com/Seeed-Studio/mm-iot-esp32.git`. Set `MMIOT_ROOT` env variable. | ☐ PASS  ☐ FAIL | |

**Library Findings:**
```
Library Name:      Seeed-Studio/mm-iot-esp32 (MorseMicro MM-IoT-SDK, ESP-IDF port)
Source URL:        https://github.com/Seeed-Studio/mm-iot-esp32
Last Commit:       2026-03-13
Framework:         ESP-IDF v5.1.1 (NOT Arduino/PlatformIO)
Install Method:    git clone + MMIOT_ROOT env variable
Assessment:        Active, Seeed-maintained. Only option for WM6108 on ESP32.
Architecture Note: Full project framework decision deferred to after Phase 1A throughput test.
```

---

### Step 2: ESP-IDF Environment Setup

| # | Check | How to Verify | PASS / FAIL | Notes |
|---|-------|---------------|-------------|-------|
| 1A-5 | **`sta_connect` example builds successfully** | `cd $MMIOT_ROOT/examples/sta_connect` → configure SSID `halowlink2-6bc7` in `mm_app_loadconfig.c` → `idf.py set-target esp32s3` → `idf.py build`. No errors. | ☐ PASS  ☐ FAIL | |
| 1A-6 | **`sta_connect` flashes and device connects to HaLowLink 2** | `idf.py flash monitor`. Serial output shows device associates with `halowlink2-6bc7` and receives IP address. | ☐ PASS  ☐ FAIL | |
| 1A-7 | **IP address received via DHCP** | Serial output shows valid IP address (not 0.0.0.0). Log IP and RSSI. | ☐ PASS  ☐ FAIL | |

**Association Result:**
```
IP Address:        _______________
RSSI:              _______________
Association Time:  _______________ ms
```

---

### Step 3: HaLow Network Association (via sta_connect example)

> **Note:** Steps 1A-5 through 1A-7 above cover association. This section documents the iperf throughput test.

### Step 4: Throughput Test via iperf Example

| # | Check | How to Verify | PASS / FAIL | Notes |
|---|-------|---------------|-------------|-------|
| 1A-8 | **`iperf` example builds and flashes** | `cd $MMIOT_ROOT/examples/iperf` → configure SSID → build → flash. Note: may need to disable power saving per HudsonReynolds2 fix: add `mmwlan_set_power_save_mode(MMWLAN_PS_DISABLED)` and `mmwlan_set_wnm_sleep_enabled(false)` to main. | ☐ PASS  ☐ FAIL | |
| 1A-9 | **Local Python test server running and reachable** | Start `test_server.py` on development PC. Confirm server IP is reachable from HaLow network via ping. | ☐ PASS  ☐ FAIL | |
| 1A-10 | **HTTP POST of 400KB payload succeeds over HaLow** | Use iperf or custom HTTP POST test. Device sends 400KB to test server. Server receives complete payload. | ☐ PASS  ☐ FAIL | |

---

### Step 5: Image Transfer Throughput Test (GO / NO-GO GATE)

| # | Check | How to Verify | PASS / FAIL | Notes |
|---|-------|---------------|-------------|-------|
| 1A-11 | **400KB test payload generated on device** | Firmware generates or loads a 400KB synthetic JPEG payload in RAM. Confirm size on serial output. | ☐ PASS  ☐ FAIL | |
| 1A-12 | **HTTP POST of 400KB payload succeeds over HaLow** | Device POSTs 400KB payload to test server. Server receives complete payload. Serial output confirms 200 OK response. | ☐ PASS  ☐ FAIL | |
| 1A-13 | **Throughput measured and documented** | Record transfer time (ms) and calculate throughput (KB/s). Log to serial. | ☐ PASS  ☐ FAIL | |

**Throughput Result:**
```
Payload Size:      400 KB
Transfer Time:     _______________ ms
Throughput:        _______________ KB/s
Minimum Required:  ~27 KB/s (400KB in <15 sec)
Assessment:        ☐ ADEQUATE  ☐ MARGINAL  ☐ INADEQUATE
```

> **Throughput Guidance:**
> - **>100 KB/s** — Excellent. Well within budget.
> - **27–100 KB/s** — Adequate. 400KB image uploads in <15 seconds.
> - **<27 KB/s** — Marginal. Review upload session timeout assumptions.
> - **<10 KB/s** — Inadequate. Communication strategy must be revisited before Phase 2.

---

### Track 1A — GO / NO-GO Decision

| Decision | Outcome |
|---|---|
| **HaLow GO** | WM6108 associates with router AND throughput is adequate → proceed to Phase 2 with HaLow as primary radio |
| **HaLow NO-GO** | WM6108 fails to associate OR throughput inadequate → architecture review required before Phase 2 |

**Track 1A Decision:** ☐ GO  ☐ NO-GO  ☐ CONDITIONAL GO (document conditions below)

**Decision Notes:**
```
_______________________________________________
_______________________________________________
```

**Sign-off:** _______________________________  **Date:** _______________

---

## 📷 Track 1B — Camera Mode Switching Without Deinit

| # | Check | How to Verify | PASS / FAIL | Notes |
|---|-------|---------------|-------------|-------|
| 1B-1 | **OV3660 initializes via esp_camera** | Upload camera init sketch. Confirm sensor detected and ID logged to serial. | ☐ PASS  ☐ FAIL | |
| 1B-2 | **YUV422 frame captured at CIF resolution** | Switch to CIF/YUV422 via register writes (no deinit). Capture frame. Confirm non-null buffer returned. | ☐ PASS  ☐ FAIL | |
| 1B-3 | **Switch to JPEG mode via register writes only (no deinit)** | Execute register-level mode switch from YUV to JPEG. Confirm no driver error or crash. | ☐ PASS  ☐ FAIL | |
| 1B-4 | **JPEG frame captured at SXGA resolution** | Capture JPEG frame after register-level switch. Confirm valid JPEG header (FF D8 FF). Log file size to serial. | ☐ PASS  ☐ FAIL | |
| 1B-5 | **20 consecutive mode switch cycles — no memory leak or instability** | Run 20 YUV→JPEG switch cycles. Monitor heap free memory each cycle. Confirm no progressive memory loss or driver crash. | ☐ PASS  ☐ FAIL | |

**Mode Switching Result:**
```
Heap at cycle 1:   _______________ bytes free
Heap at cycle 10:  _______________ bytes free
Heap at cycle 20:  _______________ bytes free
Memory delta:      _______________ bytes (should be ~0)
Any crashes:       ☐ None  ☐ Yes (describe below)
```

### Track 1B — GO / NO-GO Decision

| Decision | Outcome |
|---|---|
| **Camera GO** | Register-level switching stable across 20 cycles → capture pipeline design confirmed |
| **Camera NO-GO** | Switching unstable or memory leak detected → alternative approach must be documented before Phase 3 |

**Track 1B Decision:** ☐ GO  ☐ NO-GO

**Decision Notes:**
```
_______________________________________________
```

**Sign-off:** _______________________________  **Date:** _______________

---

## 📶 Track 1C — 2.4GHz WiFi Baseline (Parallel to 1A)

| # | Check | How to Verify | PASS / FAIL | Notes |
|---|-------|---------------|-------------|-------|
| 1C-1 | **Device connects to 2.4GHz network** | Upload WiFi baseline sketch. Confirm connection and IP address received. | ☐ PASS  ☐ FAIL | |
| 1C-2 | **HTTP POST of 400KB payload succeeds over 2.4GHz** | POST same 400KB test payload to local test server. Confirm 200 OK. | ☐ PASS  ☐ FAIL | |
| 1C-3 | **2.4GHz throughput measured and documented** | Record transfer time and calculate throughput. Compare against HaLow result. | ☐ PASS  ☐ FAIL | |

**2.4GHz Throughput Result:**
```
Payload Size:      400 KB
Transfer Time:     _______________ ms
Throughput:        _______________ KB/s
```

**HaLow vs 2.4GHz Comparison:**
```
HaLow throughput:   _______________ KB/s
2.4GHz throughput:  _______________ KB/s
Delta:              _______________ KB/s
Assessment:         _______________________________________________
```

**Sign-off:** _______________________________  **Date:** _______________

---

## 🖥️ Test Infrastructure

### Local Python Test Server

| # | Item | Status |
|---|------|--------|
| T-1 | `test_server.py` created in `Specification/test_server/` | ☐ Done |
| T-2 | Server runs on development PC (Python 3) | ☐ Done |
| T-3 | Server IP confirmed reachable from HaLow network | ☐ Done |
| T-4 | Server logs incoming requests with payload size and timestamp | ☐ Done |

**Test Server IP:** _______________  **Port:** 5000

---

## ✅ Phase 1 Sign-Off

| Item | Status |
|------|--------|
| Track 1A (HaLow): GO decision | ☐ Yes  ☐ No — architecture review required |
| Track 1B (Camera): GO decision | ☐ Yes  ☐ No — alternative approach documented |
| Track 1C (2.4GHz baseline): Complete | ☐ Yes |
| HaLow throughput result documented | ☐ Yes |
| Camera switching stability confirmed | ☐ Yes |
| Phase 1 report written | ☐ Yes |

**Phase 1 Complete:** ☐ YES — cleared to begin Phase 2 firmware development.

**Sign-off:** _______________________________  **Date:** _______________

**Phase 1 Report / Notes:**

```
HaLow Library:     _______________________________________________
HaLow Throughput:  _______________ KB/s
Camera Switching:  ☐ Stable  ☐ Unstable
Architecture:      ☐ Confirmed as designed  ☐ Requires revision
Revision Notes:    _______________________________________________
```

---

*Reference: V2 Firmware Specification v1.0 §1, §9 | V2 Development Roadmap Phase 1*  
*Document Version: 1.0 — 2026-03-17*
