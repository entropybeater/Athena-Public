# Phase 1A Research Handoff — HaLow Library Evaluation
## Petri Dish Monitor V2 | XIAO ESP32-S3 Sense | WM6108 / mm-iot-esp32
**Research completed:** 2026-03-17  
**Status:** Pre-PoC investigation complete. Ready for Phase 1A hardware validation.

---

## Executive Summary

The WM6108 HaLow module uses **MorseMicro's MM-IoT-SDK**, which is an **ESP-IDF component library only** — there is no Arduino/PlatformIO integration path and none has ever been publicly attempted. The firmware spec's assumption of Arduino framework + PlatformIO is incompatible with HaLow as-shipped.

**The good news:** Seeed has already written a working demo (`web_camera_serve`) that combines OV3660 camera capture + HaLow networking on the exact target hardware (XIAO ESP32S3 Sense), built with `idf.py`. This is the correct starting point for Phase 1A validation.

**Framework decision required after Phase 1A throughput test.** Do not begin Phase 2 firmware architecture until GO/NO-GO on HaLow is confirmed.

---

## Repository Map

| Repo | URL | Notes |
|---|---|---|
| **Seeed fork (use this)** | `https://github.com/Seeed-Studio/mm-iot-esp32` | Forked from MorseMicro. Adds `web_camera_serve` example and XIAO-specific BCF blob. Use this, not upstream. |
| MorseMicro upstream | `https://github.com/MorseMicro/mm-iot-esp32` | Upstream alpha port. Missing Seeed-specific BCF and `web_camera_serve`. |
| IDF v5.4 community patch | `https://github.com/leighleighleigh/mm-iot-esp32` | Personal fork with 2-change patch to support IDF ≥5.1.1. See IDF version section below. |

---

## SDK Structure

```
mm-iot-esp32/
├── framework/
│   ├── morselib/
│   │   └── lib/esp32-xtensa-lx7/
│   │       ├── libmorse.a            ← Pre-compiled, Xtensa LX7, full WPA3 stack
│   │       ├── libmorse_nocrypto.a
│   │       └── libmorse_nosupplicant.a
│   ├── mm_shims/
│   │   └── mmosal_shim_freertos_esp32.c  ← FreeRTOS glue layer (source available)
│   ├── morsefirmware/                ← WM6108 chip firmware blobs (.mbin)
│   ├── src/
│   │   ├── mmutils/
│   │   ├── mmipal/
│   │   ├── mmiperf/
│   │   └── mmpktmem/
│   └── [Pipfile, doc/]
└── examples/
    ├── iperf/              ← Use for throughput measurement (Phase 1A Step 5)
    ├── sta_connect/        ← Use for association test (Phase 1A Steps 2-4)
    ├── scan/
    ├── porting_assistant/  ← Use first to validate SPI connections (Phase 1A Step 1)
    ├── sta_reboot/
    ├── transfer_reset/
    └── web_camera_serve/   ← Seeed-added. Camera + HaLow on XIAO ESP32S3 Sense. KEY REFERENCE.
```

---

## The `web_camera_serve` Example — Key Reference

**This is the most important artifact for Phase 1A.** Seeed wrote this demo specifically for the XIAO ESP32S3 Sense. It does camera capture over HaLow — directly proving that `esp_camera`, `esp_http_server`, and the MM HaLow stack coexist on this hardware.

### What it does
- Initializes OV3660 via `esp_camera_init()` with the XIAO Sense DVP pin config
- Initializes HaLow and associates with an AP via `app_wlan_init()` / `app_wlan_start()`
- Serves MJPEG stream over HTTP via `esp_http_server`

### Build command
```bash
cd examples/web_camera_serve
export MMIOT_ROOT=../../
idf.py build flash monitor
```

### Component dependencies (`idf_component.yml`)
```yaml
dependencies:
  espressif/esp32-camera: "^2.0.13"   # Same camera component as Arduino-ESP32
  idf: ">=5.1.0"
  mmutils:
    path: $MMIOT_ROOT/framework/src/mmutils
  morselib:
    path: $MMIOT_ROOT/framework/morselib
  mm_shims:
    path: $MMIOT_ROOT/framework/mm_shims
  mmipal:
    path: $MMIOT_ROOT/framework/src/mmipal
  mmiperf:
    path: $MMIOT_ROOT/framework/src/mmiperf
```

### The actual HaLow API surface in `app_main()`
The HaLow-specific calls at the application layer are exactly three functions + one keepalive:

```c
// From mm_app_common.h — this is the entire HaLow API surface
app_wlan_init();        // Initialize the MM/HaLow stack
app_wlan_start();       // Connect to AP — BLOCKS until associated
// ... your application code runs here ...
// In main loop, every 5 seconds:
app_wlan_arp_send();    // REQUIRED keepalive — tells router device is online
```

`esp_event_loop_create_default()` must be called before `init_camera()`. Everything else is standard ESP-IDF.

### Critical production difference from demo
**Credentials are compile-time `#define`s in `mm_app_loadconfig.c`**, not NVS-backed:
```c
#define SSID      "halowlink2-6bc7"   // hardcoded in demo
#define PASSPHRASE "your_password"     // hardcoded in demo
```
For production firmware, `mm_app_loadconfig.c` must be modified to read SSID/passphrase from NVS instead of constants. This is Phase 2 work, not Phase 1A.

### OV3660 pin config used in `web_camera_serve`
```c
camera_config_t camera_config = {
    .pin_pwdn    = -1,
    .pin_reset   = -1,
    .pin_xclk    = 10,
    .pin_sccb_sda = 40,
    .pin_sccb_scl = 39,
    .pin_d7 = 48, .pin_d6 = 11, .pin_d5 = 12, .pin_d4 = 14,
    .pin_d3 = 16, .pin_d2 = 18, .pin_d1 = 17, .pin_d0 = 15,
    .pin_vsync = 38, .pin_href = 47, .pin_pclk = 13,
    .xclk_freq_hz = 20000000,
    .pixel_format = PIXFORMAT_JPEG,
    .frame_size   = FRAMESIZE_VGA,
    .jpeg_quality = 10,
    .fb_count     = 1,
    .grab_mode    = CAMERA_GRAB_WHEN_EMPTY
};
```

---

## IDF Version Requirements

### Official requirement
IDF **v5.1.1** (exact). The Seeed repo ships with all component `idf_component.yml` files pinned to `"==5.1.1"`.

### For Phase 1A: use v5.1.1
Start with the officially documented version to maximize first-build success. Do not use a newer IDF for Phase 1A.

### If you need IDF v5.4+ later
A community member (`leighleighleigh`) confirmed IDF v5.4 works with exactly **8 one-line changes** across 8 files:

**Change 1** — In each of these files, relax the IDF version pin:
- `framework/mm_shims/idf_component.yml`
- `framework/morselib/idf_component.yml`
- `framework/src/mmipal/idf_component.yml`
- `framework/src/mmiperf/idf_component.yml`
- `framework/src/mmpktmem/idf_component.yml`
- `framework/src/mmutils/idf_component.yml`
- `framework/src/slip/idf_component.yml`

```yaml
# Change in each file:
version: "==5.1.1"   →   version: ">=5.1.1"
```

**Change 2** — One line in `framework/mm_shims/mmosal_shim_freertos_esp32.c`:
```c
// Before (IDF 5.1 ESP_SYSTEM_INIT_FN signature):
ESP_SYSTEM_INIT_FN(mmosal_dump_failure_info, BIT(0), 999)

// After (IDF 5.4+ signature — added SECONDARY stage parameter):
ESP_SYSTEM_INIT_FN(mmosal_dump_failure_info, SECONDARY, BIT(0), 999)
```

Reference commit: `https://github.com/leighleighleigh/mm-iot-esp32/commit/2be34bd12201acf423e9d82d6900462f7ea58cf8`

---

## Framework Decision — Options A / B / C

### Option C (recommended for Phase 1A)
Run `iperf` and `web_camera_serve` in native ESP-IDF to get throughput data. Make the framework decision after seeing real results. This is pure validation — no architecture commitment.

### Option A — Full ESP-IDF
- Full HaLow support, no integration risk
- Working reference implementation exists (`web_camera_serve`)
- Lose Arduino convenience wrappers (`Wire`, `SPI`, etc.) — all have direct ESP-IDF equivalents
- `esp_camera` API is identical to what Arduino-ESP32 wraps
- **Recommended if HaLow throughput is adequate**

### Option B — Arduino-ESP32 / PlatformIO hybrid
**No documented path exists. Zero public attempts found.**

However, the FreeRTOS shim (`mmosal_shim_freertos_esp32.c`) uses exclusively standard FreeRTOS API calls — `xTaskCreate`, `xSemaphoreCreateMutex`, `xQueueCreate`, `xTimerCreate`, `pvPortMalloc`, etc. These symbols are identical in Arduino-ESP32's FreeRTOS. The libraries would likely link.

**The one compile blocker** is `esp_private/startup_internal.h` — an internal IDF header not exposed in Arduino-ESP32. It is only used for the `ESP_SYSTEM_INIT_FN` crash diagnostics registration, not for core HaLow operation. A `#ifdef` guard around that block would remove the blocker.

**Pre-conditions for Option B to work:**
1. IDF version used by PlatformIO's Arduino-ESP32 must be ≥5.1.1 (Arduino-ESP32 v3.x uses IDF 5.1.x — this matches)
2. The `$MMIOT_ROOT` path variables must resolve correctly inside PlatformIO's build system
3. `esp_private/startup_internal.h` dependency must be stubbed or guarded
4. The binary `.a` files link without symbol conflicts (unverified — requires empirical test)

**Estimated Option B investigation time: 1-2 days with no guaranteed outcome.**

---

## SDK Maturity — Risk Register Addition

| Risk Item | Detail |
|---|---|
| **Alpha Port label** | MorseMicro explicitly calls this an "Alpha Port" — not part of their standard test cycle, features may be incomplete |
| **Abandoned upstream** | MorseMicro has not responded to any of the 5 open issues on the upstream repo |
| **Tiny community** | 26 stars, 18 forks upstream. Seeed fork has 7 stars, 2 forks |
| **IDF version locked** | Pinned to `==5.1.1` out of box; community workaround exists for ≥5.1.1 |
| **No MorseMicro support** | If you hit a bug in `libmorse.a` (closed binary), there is no recourse |
| **Seeed fork diverges from upstream** | Seeed is 3 commits ahead, 4 commits behind upstream. Upstream is not tracking Seeed changes |

---

## Phase 1A Recommended Execution Order

### Step 0: Environment setup
```bash
# Install ESP-IDF v5.1.1 (not newer for Phase 1A)
# https://docs.espressif.com/projects/esp-idf/en/v5.1.1/esp32s3/get-started/

# Clone Seeed fork (not MorseMicro upstream)
git clone https://github.com/Seeed-Studio/mm-iot-esp32
export MMIOT_ROOT=/path/to/mm-iot-esp32
```

### Step 1: Porting assistant — validate SPI connections
```bash
cd $MMIOT_ROOT/examples/porting_assistant
idf.py build flash monitor
```
Expected output: series of PASS results including "WLAN HAL initialisation [ PASS ]" and "Validate BCF [ PASS ]". If SPI connections (GPIO4/7/8/9) are correct and `bcf_mf16858_us.mbin` is present, this should pass.

**Note:** The SPI GPIO pins differ between the MorseMicro upstream and the XIAO Sense layout. Verify via `idf.py menuconfig` → Component config → Morse Micro Shim Configuration that pins match your hardware: CS=GPIO4, SCK=GPIO7, MISO=GPIO8, MOSI=GPIO9.

### Step 2: sta_connect — validate HaLow association
Edit `examples/sta_connect/main/src/sta_connect.c`:
```c
#define SSID       "halowlink2-6bc7"
#define PASSPHRASE "your_passphrase"
#define COUNTRY_CODE "US"    // uncomment and set correct country code
```
```bash
cd $MMIOT_ROOT/examples/sta_connect
idf.py build flash monitor
```
Expected output: `Link went Up` and `STA state: CONNECTED (2)`.  
Record IP address, RSSI, and association time for the Phase 1A checklist.

### Step 3: iperf — throughput measurement
```bash
cd $MMIOT_ROOT/examples/iperf
idf.py build flash monitor
```
Run iperf against local test server. Document result in KB/s.

**Throughput gates (per spec §1A-13):**
- **>100 KB/s** — Excellent
- **27–100 KB/s** — Adequate (400KB image in <15 sec)
- **<27 KB/s** — Marginal, review assumptions
- **<10 KB/s** — Inadequate, architecture review required before Phase 2

### Step 4: web_camera_serve — image transfer reference
```bash
cd $MMIOT_ROOT/examples/web_camera_serve
export MMIOT_ROOT=../../
idf.py build flash monitor
```
Browse to device IP. Confirms camera + HaLow coexistence on target hardware.

**Note:** The `web_camera_serve` demo uses a Raspberry Pi + HaLow module as AP in bridge mode (SSID: MorseMicro, Password: 12345678) in its README. For testing against HaLowLink 2, modify SSID/passphrase in the loadconfig file before building.

---

## BCF File — Critical Seeed-Specific Detail

The Seeed fork added `bcf_mf16858_us.mbin.o` — this is the Board Configuration File for the WM6108 module on the XIAO, for US regulatory domain. This blob does **not exist** in the MorseMicro upstream repo. It was added by commit `b8b7452` (Wvirgil123, Jan 8 2025).

If building from upstream instead of Seeed fork, this BCF will be missing and radio init will fail. **Always use the Seeed fork.**

To configure the BCF in menuconfig:
```
idf.py menuconfig
→ Component config → Morse Micro Shim Configuration
  → Board Configuration File: bcf_mf16858_us.mbin
  → Chip type: MM6108
```

---

## Known Open Issues on Upstream Repo

| # | Title | Status | Notes |
|---|---|---|---|
| #1 | Quectel FGH100M | Open | Different module, not relevant |
| #2 | Request: Support for Newer ESP-IDF Versions | Open, **no MorseMicro response** | Community patch exists (see IDF version section) |
| #3 | Can't connect webcamera to HaLow | Open, **no MorseMicro response** | Reporter's setup unclear; not a confirmed SDK bug |
| #4 | FGH100M ESP32S3 AP Mode | Open | Different module |
| #6 | Support for MM8108 | Open | Different chip variant |

MorseMicro has not responded to any issues. All workarounds are community-sourced.

---

## What the Agent Does NOT Need to Investigate

These questions are answered. Do not spend time re-researching them:

- ❌ "Is there a PlatformIO library for WM6108?" — No. Does not exist anywhere.
- ❌ "Has anyone integrated mm-iot-esp32 with Arduino-ESP32?" — No. Zero public attempts.
- ❌ "Does the SDK work on IDF newer than 5.1.1?" — Yes, with the 8-line patch documented above.
- ❌ "What is the HaLow API surface at the application layer?" — Three calls: `app_wlan_init()`, `app_wlan_start()`, `app_wlan_arp_send()` (keepalive every 5s).
- ❌ "Does `web_camera_serve` work on XIAO ESP32S3 Sense?" — Yes. Seeed wrote and tested it on that exact hardware.
- ❌ "Are the binary libraries compatible with ESP32-S3?" — Yes. `libmorse.a` is compiled for Xtensa LX7 (the ESP32-S3 CPU).
- ❌ "What FreeRTOS calls does the shim use?" — Standard FreeRTOS only. Full list in the Option B section above.

---

## Files to Modify for Production Use (Post-Phase 1A)

| File | Change Required | Phase |
|---|---|---|
| `examples/*/main/src/mm_app_loadconfig.c` | Replace compile-time `#define` credentials with NVS reads | Phase 2 |
| `framework/mm_shims/mmosal_shim_freertos_esp32.c` | Add `SECONDARY` parameter to `ESP_SYSTEM_INIT_FN` if upgrading to IDF ≥5.4 | Only if IDF upgrade needed |
| All `framework/*/idf_component.yml` | Change `"==5.1.1"` to `">=5.1.1"` if upgrading IDF | Only if IDF upgrade needed |

---

## Phase 1A Exit Criteria (from spec)

Phase 2 does not begin until both conditions are met:
1. ✅ WM6108 associates with `halowlink2-6bc7` router AND transfers a 400KB test payload
2. ✅ Camera mode switching (YUV↔JPEG) works without deinit/reinit (Track 1B — separate from HaLow)

The framework decision (ESP-IDF full-time vs hybrid) must be documented before Phase 2 architecture is locked.

---

*Research conducted: 2026-03-17*  
*Sources: Live inspection of Seeed-Studio/mm-iot-esp32, MorseMicro/mm-iot-esp32, leighleighleigh/mm-iot-esp32, and upstream GitHub issues*  
*No assumptions — all findings verified against actual repo content*
