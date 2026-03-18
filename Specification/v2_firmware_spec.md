# Petri Dish Monitor — V2 Firmware Specification
### XIAO ESP32-S3 Sense | Arduino Framework | PlatformIO
**Document Version:** 1.0  
**Status:** Draft for Review  
**Last Updated:** 2026-03-12

---

## Table of Contents
1. [Project Overview](#1-project-overview)
2. [Hardware Reference](#2-hardware-reference)
3. [Partition Scheme](#3-partition-scheme)
4. [Boot Sequence](#4-boot-sequence)
5. [Wake Cycle Architecture](#5-wake-cycle-architecture)
6. [Image Capture Pipeline](#6-image-capture-pipeline)
7. [Storage Management](#7-storage-management)
8. [Metadata System](#8-metadata-system)
9. [Radio and Connectivity](#9-radio-and-connectivity)
10. [Upload Session Protocol](#10-upload-session-protocol)
11. [Capture Scheduling](#11-capture-scheduling)
12. [BLE Provisioning](#12-ble-provisioning)
13. [OTA Firmware Updates](#13-ota-firmware-updates)
14. [Battery Management](#14-battery-management)
15. [Error Reporting and Fault Handling](#15-error-reporting-and-fault-handling)
16. [Edge Case Definitions](#16-edge-case-definitions)
17. [LED Indication System](#17-led-indication-system)
18. [Button Interface](#18-button-interface)
19. [Health Packet Specification](#19-health-packet-specification)
20. [NVS State Reference](#20-nvs-state-reference)
21. [Server Communication Contract](#21-server-communication-contract)
22. [Sensor Calibration Support](#22-sensor-calibration-support)
23. [BME280 Interval Data Logging](#23-bme280-interval-data-logging)
24. [Open Items and Future Considerations](#24-open-items-and-future-considerations)

---

## 1. Project Overview

### 1.1 Device Purpose
The Petri Dish Monitor is a battery-powered, wireless image acquisition node deployed inside commercial greenhouses. It captures time-lapse images of petri dishes used to monitor mold growth in professional horticultural facilities.

The device is not a smart device. All intelligence — image analysis, growth stage detection, plate change detection, anomaly detection — lives on the server. The device's responsibility is to be a reliable, low-maintenance, high-quality image acquisition and transmission node.

### 1.2 Deployment Context
- Deployed inside greenhouses at customer facilities
- Installed and configured by the vendor team
- Maintained by unskilled on-site labor (petri dish swaps, battery swaps)
- Monitored remotely by the vendor team via server dashboard
- Customers interact with data only via alerts and reports — never with the device directly

### 1.3 V1 Lessons Applied
| V1 Problem | V2 Solution |
|---|---|
| 2.4GHz WiFi insufficient range | WiFi HaLow (802.11ah) primary radio |
| No battery monitoring | ADS1115 reading V50 SBU pin |
| Firmware updates required physical access | OTA over HaLow |
| BLE reprovision required NVS wipe | Dedicated NVS partition survives OTA |
| Single-shot brightness calibration failed at extremes | Iterative convergence loop |
| MQTT protocol clunky and error-prone | Clean protocol abstraction layer (TBD) |
| No error reporting | Comprehensive health packet every session |
| Fixed capture schedule | Adaptive schedule driven by server |
| BME680 gas resistance unused | BME280 — temp, humidity, pressure only |

### 1.4 Design Principles
- **Device is a transmission buffer, not an archive.** Server is system of record.
- **Every second awake costs battery.** Timeouts are a battery management mechanism.
- **Never block on a fault.** Every fault has a defined graceful degradation path.
- **Server is the authority.** Device executes instructions, server makes decisions.
- **All state survives deep sleep.** NVS is the single source of truth for device state.

---

## 2. Hardware Reference

### 2.1 Core Components
| Component | Part | Interface |
|---|---|---|
| Microcontroller | Seeed Studio XIAO ESP32-S3 Sense | — |
| Camera | OV3660 (integrated on Sense module) | DVP via B2B connector |
| WiFi HaLow Radio | Seeed Wio-WM6108 | SPI |
| Environmental Sensor | BME280 | I2C (0x76) |
| ADC / Battery Monitor | ADS1115 | I2C (0x48) |
| LED Flash Driver | IRLZ44N MOSFET | GPIO PWM |
| LED Flash Ring | 325mm ring, 5V, ~650mA | MOSFET switched |
| SD Card | 32GB (integrated slot on Sense module) | Internal SPI |
| Battery | Voltaic Systems V50 (13,400mAh) | USB-C VBUS + SBU |
| Status Indicator | Onboard RGB NeoPixel | GPIO21 |

### 2.2 GPIO Pin Allocation
| XIAO Label | GPIO | Function | Status |
|---|---|---|---|
| D0 | GPIO1 | HaLow Wakeup | HaLow |
| D1 | GPIO2 | HaLow Reset | HaLow |
| D2 | GPIO3 | HaLow Interrupt/BUSY | HaLow |
| D3 | GPIO4 | HaLow SPI CS | HaLow |
| D4 | GPIO5 | I2C SDA — BME280 + ADS1115 | In use |
| D5 | GPIO6 | I2C SCL — BME280 + ADS1115 | In use |
| D6 | GPIO43 | LED Flash PWM → MOSFET gate | In use |
| D7 | GPIO44 | Mode select button | In use |
| D8 | GPIO7 | HaLow SPI SCK | HaLow |
| D9 | GPIO8 | HaLow SPI MISO | HaLow |
| D10 | GPIO9 | HaLow SPI MOSI | HaLow |
| D11 | GPIO42 | Blocked by HaLow B2B connector | Unavailable |
| D12 | GPIO41 | Blocked by HaLow B2B connector | Unavailable |
| — | GPIO21 | Onboard NeoPixel RGB LED | In use |

### 2.3 I2C Bus
- SDA: GPIO5, SCL: GPIO6
- Pull-ups: 4.7kΩ on each line (single resistor per line, not per device)
- BME280: address 0x76 (SDO → GND), CSB → 3.3V for I2C mode
- ADS1115: address 0x48 (ADDR → GND)
- Wire.begin(5, 6) — initialized once, recovered if locked

### 2.4 Battery Monitoring
- V50 SBU pin outputs ½ cell voltage: 1.6V (empty) to 2.1V (full)
- Voltage divider (100kΩ / 91kΩ) scales to ADS1115 A0
- ADS1115 PGA: GAIN_TWO (±2.048V range)
- Recovery formula:
```cpp
float v_sbu  = ads_voltage / (91.0 / (100.0 + 91.0));
float v_cell = v_sbu * 2.0;
float pct    = (v_cell - 3.2) / (4.2 - 3.2) * 100.0;
```
- **Critical requirement:** USB-C cable must be 3.1 or 3.2 spec (SBU pins required). Standard USB 2.0 cables will silently fail battery monitoring.

### 2.5 LED Flash Driver
- IRLZ44N low-side MOSFET switch
- Gate: GPIO43 via 220Ω resistor, 10kΩ pull-down to GND
- Flyback diode: 1N5819 across LED ring
- PWM: LEDC peripheral, 20kHz+ (above rolling shutter threshold)
- Flash duration: <2 seconds per capture (no heatsink required)

### 2.6 Hardware Variants
| Configuration | HaLow Module | Primary Radio |
|---|---|---|
| Full deployment | Wio-WM6108 installed | HaLow (802.11ah) |
| Testing / lower cost | No HaLow module | 2.4GHz onboard WiFi |

Same firmware binary supports both configurations via compile-time flag and runtime detection.

---

## 3. Partition Scheme

```
┌─────────────────────────────────────┐
│ Bootloader (fixed)                  │
├─────────────────────────────────────┤
│ Partition Table                     │
├─────────────────────────────────────┤
│ NVS — Provisioning & Device State   │  ← Never erased by OTA
│   HaLow credentials                 │
│   2.4GHz credentials                │
│   Radio preference                  │
│   Image counter                     │
│   Capture schedule / stage          │
│   Battery thresholds                │
│   Quality metric thresholds         │
│   Crash counter                     │
│   Last phase attempted              │
│   Pending reset report              │
│   OTA flags                         │
│   Lens obstruction state            │
│   Last NTP sync timestamp           │
│   Rolling quality metric buffers    │
├─────────────────────────────────────┤
│ OTA Data (tracks active slot)       │
├─────────────────────────────────────┤
│ App Partition 0 (OTA slot 0)        │  ← Running firmware
├─────────────────────────────────────┤
│ App Partition 1 (OTA slot 1)        │  ← OTA target
├─────────────────────────────────────┤
│ SPIFFS / LittleFS (optional)        │
└─────────────────────────────────────┘

SD Card (external — all image and metadata storage):
/images/
  /pending/    → captured, not yet uploaded
  /uploaded/   → server confirmed receipt
  /corrupt/    → failed integrity check, quarantined
metadata.dat   → fixed-size binary struct records
```

**Rule:** NVS partition is explicitly excluded from OTA update scope. Image counter and all device state survive any firmware update.

---

## 4. Boot Sequence

Every boot — whether from power-on, deep sleep wake, watchdog reset, or OTA reboot — executes this sequence in strict order:

```
BOOT
  │
  ▼
[STEP 1] Read reset reason
  esp_reset_reason() → stored in session state
  Classify: CLEAN (POWERON, SW, DEEPSLEEP) or
            FAULT (WDT, PANIC, BROWNOUT)

[STEP 2] Crash counter management
  If FAULT reset:
    Read crash_count from NVS
    Increment and write back
    Store reset_reason + last_phase_attempted
    Set pending_reset_report: true in NVS
  If CLEAN reset:
    Do not increment crash_count

[STEP 3] Safe mode check
  If crash_count >= 3 → enter SAFE MODE
  (see Section 15.3)

[STEP 4] I2C bus health check
  Probe BME280 and ADS1115
  If no response → attempt 9-clock-pulse recovery
  (see Section 15.4)
  Classify result: HEALTHY / RECOVERED / FAULT

[STEP 5] Sensor reads
  BME280: temperature, humidity, pressure
  ADS1115: battery voltage → calculate percentage
  On fault: null values + fault flags in session state

[STEP 6] SD card health check
  SD.begin() → filesystem probe
  Check /images/pending/ for corrupt files (JPEG header validation)
  Quarantine corrupt files to /images/corrupt/
  Check free space → evaluate against thresholds

[STEP 7] Determine wake reason
  Scheduled capture, OTA maintenance window,
  manual button wake, safe mode cycle

[STEP 8] Proceed to wake cycle
```

---

## 5. Wake Cycle Architecture

### 5.1 Phase-Specific Watchdog Timeouts
The watchdog timer is resized at the start of each phase. Current phase is written to NVS before each phase begins — enabling post-reset diagnosis of which phase caused a fault.

| Phase | Timeout | Protects Against |
|---|---|---|
| BOOT_SENSORS | 10 seconds | I2C hang, SD init block |
| CAMERA_CAPTURE | 20 seconds | Camera init hang, convergence runaway, SD write block |
| CONNECTION | 75 seconds | Radio stack freeze, DHCP hang, NTP block |
| DATA_EXCHANGE | 45 sec per image + kicked after each ACK | Server response hang, stalled upload |
| HOUSEKEEPING | 10 seconds | NVS write hang, filesystem close block |

### 5.2 Normal Wake Cycle (Online)
```
Wake from deep sleep
  │
  ▼
Boot sequence (Section 4)
  │
  ▼
[PHASE: CAMERA_CAPTURE]
  NeoPixel: OFF (blanked for capture)
  Execute image capture pipeline (Section 6)
  Save image + metadata to SD /pending/
  NeoPixel: resume previous state
  │
  ▼
[PHASE: CONNECTION]
  NeoPixel: BLUE slow pulse
  NTP sync attempt (pool.ntp.org, 10sec timeout) — FIRST
  Try primary radio (3 × 10sec attempts)
  If fail → try secondary radio (3 × 10sec attempts)
  If fail → OFFLINE MODE
  │
  ▼
[PHASE: DATA_EXCHANGE]
  Execute upload session (Section 10)
  │
  ▼
[PHASE: HOUSEKEEPING]
  Update NVS state
  Reset crash_count to 0 (successful cycle)
  Calculate next wake time from schedule
  │
  ▼
Deep sleep until next scheduled wake
```

### 5.3 Offline Wake Cycle
```
Wake from deep sleep
  │
  ▼
Boot sequence
  │
  ▼
Camera capture → save to SD
  │
  ▼
Connection attempt → all radios fail (60sec max)
  │
  ▼
Skip data exchange entirely
  │
  ▼
Housekeeping → update NVS → deep sleep
```

### 5.4 Operating Modes
| Mode | Description |
|---|---|
| ONLINE | Connected, capturing, uploading, receiving config |
| OFFLINE | Not connected, capturing and storing locally |
| SYNC | Reconnected after offline period — uploading backlog |
| SAFE | Crash loop detected — connect and report only, no capture |
| MAINTENANCE | Button-triggered — TBD functions |
| PROVISIONING | Awaiting BLE configuration |

---

## 6. Image Capture Pipeline

### 6.1 Requirements
- **IC-01:** Brightness calibration shall use an iterative convergence loop. The loop shall converge luminance within an acceptable target band before committing to final capture, with a maximum iteration cap to prevent infinite loops.
- **IC-02:** Luminance sampling shall be center-weighted, sampling only the central region of the probe frame corresponding to the petri dish area. Edge pixels shall be excluded.
- **IC-03:** Camera mode switching between probe (YUV) and capture (JPEG) shall be achieved via in-place sensor register writes. Full driver deinit/reinit cycles between modes are prohibited.
- **IC-04:** The brightness calibration system shall perform correctly across the full operating range including complete darkness and direct greenhouse sunlight.

### 6.2 Pre-Capture LED Blackout
```
Before any capture phase begins:
  1. Save current NeoPixel state
  2. NeoPixel → OFF explicitly
  3. Verify flash ring PWM = 0
  4. Proceed with capture
  5. After capture complete → restore NeoPixel state
```

### 6.3 Capture Sequence
```
[PROBE PHASE — YUV mode]
  Switch camera to CIF / YUV422 via register write (no deinit)
  Fire flash ring at baseline duty (10%)
  Wait 250ms for sensor to settle
  Capture probe frame
  Flash ring → OFF

  Sample center ROI only (middle third of frame):
    Correct byte indexing: even indices for Y channel (0, 2, 4...)
    Calculate average Y luminance of center region only

[CONVERGENCE LOOP]
  Target Y: configurable (default 200)
  Max iterations: configurable (default 5)
  
  For each iteration:
    Calculate duty = (TARGET_Y / measured_Y) × current_duty × safety_factor
    Clamp to LEDC_MAX
    Fire at new duty → capture probe → measure Y
    If Y within ±15 of TARGET_Y → convergence achieved → exit loop
    If iterations == max → exit loop, use best duty found, flag HIGH_ITER

  Record: final_duty, final_luminance, convergence_iters

[MAIN CAPTURE PHASE — JPEG mode]
  Switch camera to SXGA / JPEG via register write (no deinit)
  Fire flash ring at converged duty
  Wait 500ms for LED to stabilize

  Discard frames until luminance stabilizes (max 5 frames):
    Measure luminance each frame
    Stop discarding when delta < threshold OR 5 frames reached

  AEC/AGC lock sequence:
    Attempt 1: set_aec2(0) + set_gain_ctrl(0) → verify (50ms)
    If unconfirmed → Attempt 2: retry → verify (50ms)
    If still unconfirmed → proceed, flag AEC_LOCK_FAILED

  Capture final JPEG frame
  Flash ring → OFF immediately

  Save to /images/pending/[MAC]_[imageCount].jpg
  Write metadata record (Section 8)
  Increment imageCount in NVS
```

### 6.4 Lens Obstruction Detection
After each capture, evaluate all three conditions:
- Condition A: flash_duty == LEDC_MAX
- Condition B: measured_luminance < luminance_min threshold
- Condition C: convergence_iters == max_iterations

If ALL THREE conditions are true → increment `lens_anomaly_counter`  
If any condition is false → reset `lens_anomaly_counter` to 0

If `lens_anomaly_counter >= 2` consecutive captures:
- Set `lens_obstruction_suspected: true` in NVS
- Include flag in health packet
- Server AI confirms or clears via image analysis
- If confirmed: server alerts personnel + sends LENS_OBSTRUCTION_CONFIRMED
- Flash ring activates rapid double-pulse pattern while suspected confirmed

Cleared when server sends LENS_OBSTRUCTION_RESOLVED after clean image confirmed.

### 6.5 Capture Failure Handling
If camera fails to initialize or capture fails:
- Write failed capture record to metadata with `CAPTURE_FAILED` status flag
- Skip to connection phase
- Report in health packet
- Server sees explicit failure reason, not just a gap

---

## 7. Storage Management

### 7.1 SD Card Directory Structure
```
/images/
  /pending/    → [MAC]_[00000].jpg — awaiting upload
  /uploaded/   → [MAC]_[00000].jpg — server confirmed
  /corrupt/    → [MAC]_[00000].jpg — failed integrity, quarantined
metadata.dat   → fixed-size binary struct, one record per image
```

### 7.2 Image Naming Convention
Format: `[MAC_ADDRESS]_[ZERO_PADDED_ID].jpg`  
Example: `AABBCCDDEEFF_00047.jpg`

- MAC address prefix ensures global uniqueness across all deployed devices
- Zero-padded 8-digit integer (`%08d`) — supports up to 99,999,999 images
- Sequential ID enables server-side gap detection for missing images
- NVS-backed counter survives deep sleep and firmware updates
- Counter survives OTA — NVS partition explicitly excluded from OTA scope
- Rollover at 99,999,999 → detected and flagged as lifecycle event to server

### 7.3 Pending Image State Transitions
```
Captured → saved to /pending/
  │
  Upload attempted → server ACK received
  │
  └── Move to /uploaded/
      Mark metadata: upload_confirmed = true
      upload_attempt_count reset to 0

  Upload attempted → no ACK within 15 seconds
  │
  └── Leave in /pending/
      Increment upload_attempt_count in metadata
      Retry next session
      After 5 failed attempts → flag in health packet

  Corrupt file detected on boot (JPEG header invalid)
  │
  └── Retry SD read once
      If still invalid → move to /corrupt/
      Write failed record to metadata: CAPTURE_CORRUPT
      Report in health packet with fault_hint:
        SD_WRITE_ERROR (if metadata shows capture completed)
        POSSIBLE_SENSOR_FAULT (if metadata shows incomplete capture)
```

### 7.4 SD Card Capacity Management

**Thresholds:**
| Threshold | Value | Action |
|---|---|---|
| WARNING | 80% full | Begin purging oldest /uploaded/ files. Alert server. |
| CRITICAL | 95% full | Stop capturing. Alert server. Resume only after purge brings below 80%. |

**SD Full — Unuploaded Data:**
If SD reaches critical threshold with unuploaded images still in /pending/:
- Stop all new captures
- Alert server: "SD card critical — capturing suspended, unuploaded data at risk"
- Never overwrite /pending/ files
- Resume captures only after server acknowledges and /uploaded/ purge creates headroom

**Retention Policy (current):**
Purge oldest /uploaded/ files when approaching WARNING threshold.  
*(Team discussion pending — may transition to fixed-day retention window, e.g. 7 days after confirmed upload)*

### 7.5 Corrupt File Scan on Boot
At boot, scan /images/pending/ for files with invalid JPEG headers:
- Valid JPEG header: first 3 bytes = `FF D8 FF`
- File size 0 bytes: immediate quarantine
- Invalid header: one SD re-read retry before quarantine
- Quarantined files moved to /images/corrupt/ — never deleted automatically
- Pattern of corruption on a single device → SD card hardware failure indicator

---

## 8. Metadata System

### 8.1 Storage Format
Fixed-size binary struct stored in `metadata.dat`. O(1) retrieval by image ID:
```cpp
size_t offset = (image_id - 1) * sizeof(ImageMetadata);
```

### 8.2 ImageMetadata Struct
```cpp
struct ImageMetadata {
    uint8_t  struct_version;       // Schema version — increment on any change
    uint32_t image_id;             // Explicit ID — verified against file position
    uint32_t unix_timestamp;       // 0 if RTC not synced at capture time
    float    temperature;          // BME280 °C
    float    humidity;             // BME280 %RH
    float    pressure;             // BME280 hPa
    uint16_t flash_duty;           // LEDC duty cycle used for final capture
    uint8_t  measured_luminance;   // Average Y value from final probe
    uint8_t  convergence_iters;    // Number of probe iterations needed
    uint8_t  capture_status;       // Bitmask (see below)
    uint16_t jpeg_size_kb;         // Approximate size of paired JPEG
    uint8_t  upload_attempt_count; // Times upload attempted
    bool     upload_confirmed;     // Server ACK received
    uint16_t crc16;                // CRC of all preceding fields
};
```

**capture_status bitmask:**
```
Bit 0: RTC_SYNCED         — timestamp is reliable
Bit 1: AEC_LOCKED         — exposure locked before capture
Bit 2: AEC_LOCK_RETRY     — lock succeeded on second attempt
Bit 3: AEC_LOCK_FAILED    — lock failed, proceeded without
Bit 4: FLASH_FIRED        — flash ring activated
Bit 5: FLASH_FAULT        — flash not responding to duty
Bit 6: CAPTURE_FAILED     — image not captured
Bit 7: CAPTURE_CORRUPT    — image corrupted on SD
```

### 8.3 Struct Version Migration
On boot, read struct_version from first record in metadata.dat.  
If struct_version != current firmware struct_version:
- Log migration event
- Firmware handles backward compatibility for N-1 version
- Alert server: "metadata schema version mismatch — manual review may be needed"

### 8.4 Partial Write Protection
Each record includes CRC16 of all preceding fields.  
On read, verify CRC. If mismatch:
- Mark record as corrupt
- Do not use corrupt data for upload
- Report to server in health packet

---

## 9. Radio and Connectivity

### 9.1 Hardware Variant Detection
```
On boot, read radio_preference from NVS
  │
  ├── PRIMARY = HaLow
  │     Probe SPI bus for WM6108 (identity register read)
  │     ├── Module responds → init HaLow stack
  │     └── Module absent  → log warning, fall back to 2.4GHz
  │                          flag halow_module_fault in health packet
  │
  └── PRIMARY = 2.4GHz
        Skip HaLow probe entirely
        Init onboard WiFi directly
```

### 9.2 Connection Attempt Sequence
```
Try primary radio:
  3 attempts × 10 seconds each = 30 seconds max

If all fail → try secondary radio:
  3 attempts × 10 seconds each = 30 seconds max

If all fail → OFFLINE MODE
  Total maximum connection time: 60 seconds
  No further time spent seeking connection
```

### 9.3 Radio Fallback Behavior
- When operating on secondary radio: flag `operating_on_fallback: true` in health packet
- Every wake cycle: always try primary radio first before fallback
- Fallback is never sticky — primary is always retried

### 9.4 Provisioning Credential Storage
```
NVS stores (all optional — device works with whatever is provided):
  halow_ssid
  halow_password
  wifi_ssid
  wifi_password
  radio_preference   (HALOW / WIFI_24 — defaults to HALOW if credentials present)
```

Device with no credentials stored → remains in provisioning mode.  
Device with only one credential set → uses that radio, no fallback available.  
Device with both → uses preference, falls back to other if primary fails.

### 9.5 NTP Sync
- Attempted at Step 0 of every connected session — before health packet
- Source: pool.ntp.org
- Timeout: 10 seconds
- On success: set internal RTC, store `last_ntp_sync` timestamp in NVS
- On failure: proceed with current RTC value, set `rtc_unsynced: true` for session
- Any capture taken with unsynced RTC → `unix_timestamp = 0` in metadata

---

## 10. Upload Session Protocol

### 10.1 Session Sequence
```
CONNECTION ESTABLISHED + NTP SYNC COMPLETE
        │
[STEP 1] Send health packet (JSON)            ~1 sec
         Full device state, metrics, fault flags
         Server has complete situational awareness
        │
[STEP 2] Send all pending metadata records    ~2-5 sec
         All ImageMetadata records with upload_confirmed = false
         Server knows exactly what images are coming
        │
[STEP 3] Upload all pending images            variable
         Oldest first (lowest image_id first)
         45 second timeout per image
         Explicit server ACK required per image before next
         On ACK → move file /pending/ → /uploaded/
                  set upload_confirmed = true in metadata
         On timeout → leave in /pending/
                      increment upload_attempt_count
                      continue to next image
         After 5 failed attempts on same image →
                      flag in health packet next session
        │
[STEP 4] Receive server messages              ~2 sec
         Config updates (schedule, stage, thresholds)
         OTA announcement if applicable
         Any commands (FORCE_NORMAL_MODE, LENS_OBSTRUCTION_CLEARED, etc.)
        │
[STEP 5] Acknowledge server messages          ~1 sec
         Confirm receipt of all commands
         Close connection cleanly
        │
HOUSEKEEPING → DEEP SLEEP
```

### 10.2 Upload Priority Note
Metadata (Step 2) always precedes images (Step 3). If connection drops mid-session, server has full knowledge of device state and pending image list even without receiving the images themselves.

### 10.3 Idempotent Uploads
**Backend requirement (flag for backend teammate):** The server upload endpoint must handle duplicate image_id submissions gracefully. If a device uploads an image, loses connection before receiving the ACK, and re-uploads the same image next session — the server must accept the second upload without creating a duplicate record.

### 10.4 Backlog Sync Behavior
After offline period, device uploads entire pending backlog in one session.  
Backend must handle upload bursts gracefully — flag for backend teammate.

---

## 11. Capture Scheduling

### 11.1 Approach
Option C: Predefined adaptive schedule as default, server-authoritative override.

The device runs a biologically-informed default schedule based on mold growth stages. The server AI observes growth, determines stage transitions, and pushes updated intervals. The device never needs to know it's a mold monitor — it executes whatever interval it receives.

### 11.2 Default Adaptive Schedule
| Day Since Experiment Start | Interval | Rationale |
|---|---|---|
| Day 0-2 | Every 4 hours | Flat phase — minimal growth activity |
| Day 2-4 | Every 2 hours | Early growth — dots beginning to appear |
| Day 4-6 | Every 1 hour | Active growth phase |
| Day 6+ | Every 30 minutes | Explosive growth phase |

### 11.3 Server-Driven Schedule
Server pushes stage updates to device during Step 4 of upload session:
```json
{
  "command": "SET_SCHEDULE",
  "stage": 2,
  "interval_minutes": 120,
  "stage_set_timestamp": 1741823400
}
```
Device stores in NVS: `current_stage`, `capture_interval_minutes`, `stage_set_timestamp`  
Falls back to default schedule if server stage update never received.

### 11.4 Experiment Lifecycle
- **Plate change detection:** Server-side only. AI detects new plate at next scheduled capture.
- **Experiment start:** Server opens new experiment record when new plate detected.
- **Schedule reset:** Server pushes Day 0 schedule (4hr interval) when new plate confirmed.
- **Exhausted plate:** Server pushes check interval (4hr) when plate exhaustion detected. AI alerts personnel for swap.
- **First deployment:** Device captures at Day 0 defaults until server sends first stage update.

### 11.5 Schedule Storage in NVS
```cpp
uint8_t  current_stage;               // 0-N growth stage
uint16_t capture_interval_minutes;    // Active interval
uint32_t stage_set_timestamp;         // When server last updated stage
uint32_t next_capture_timestamp;      // Absolute RTC time of next capture
uint32_t next_maintenance_timestamp;  // Absolute RTC time of OTA window
```

---

## 12. BLE Provisioning

### 12.1 Current Approach (Phase 1)
BLE provisioning via nRF Connect app. Installation team connects to device over BLE and writes credentials to defined GATT characteristics.

### 12.2 Future Approach (Phase 2 — not in V2 scope)
Custom mobile app or browser-based provisioning via vendor website. GATT service definition must be clean and documented so Phase 2 app targets same characteristics without firmware changes.

### 12.3 Provisioning Mode Entry
- Factory reset (button hold on power-on or 10s hold powered)
- Device advertises BLE with device name: `PDM-[last 4 MAC digits]`
- NeoPixel: PURPLE fast pulse (250ms on/off)
- Flash ring: OFF

### 12.4 GATT Characteristics (provisional)
| Characteristic | UUID | Properties | Data |
|---|---|---|---|
| HaLow SSID | TBD | Write | String |
| HaLow Password | TBD | Write | String |
| WiFi SSID | TBD | Write | String |
| WiFi Password | TBD | Write | String |
| Radio Preference | TBD | Write | Enum: HALOW / WIFI_24 |
| Provision Complete | TBD | Write | Trigger reboot |

All fields optional. Device reboots into normal operation on Provision Complete write.

### 12.5 Provisioning Improvements Over V1
- Only HaLow/WiFi credentials needed — no server endpoint provisioned on device
- Credentials survive OTA updates (NVS partition protected)
- Factory reset restores to provisioning mode without laptop
- Credentials changeable without full reprovision

---

## 13. OTA Firmware Updates

### 13.1 Mechanism
ESP32-S3 dual OTA partition scheme. New firmware written to inactive slot, validated, then booted. Automatic rollback if new firmware fails to mark itself valid.

### 13.2 OTA Trigger Flow
```
Server announces OTA available (Step 4 of upload session)
  Device stores in NVS:
    ota_pending: true
    ota_firmware_url: [URL]
    ota_maintenance_window: [unix timestamp]
    ota_firmware_hash: [expected hash]
  Device reports ota_pending: true in subsequent health packets

Maintenance window arrives:
  Device wakes at scheduled RTC alarm
  Check battery >= 20% AND ads1115_fault == false
  If battery gate passes (or FORCED flag set by server):
    Download firmware to OTA slot 1 in chunks over HaLow/HTTPS
    Validate SHA256 hash
    ├── VALID → reboot into new firmware
    └── INVALID → discard, report OTA_HASH_FAIL, retain current firmware
  If battery < 20%:
    Skip OTA, report OTA_DEFERRED_LOW_BATTERY in health packet
    Server reschedules maintenance window
```

### 13.3 OTA Result Reporting
On first successful boot + connection after OTA:
```json
{
  "event": "OTA_RESULT",
  "status": "SUCCESS",
  "previous_version": "2.0.0",
  "new_version": "2.1.0",
  "boot_time_ms": 1840,
  "timestamp": 1741823400
}
```

On rollback (old firmware reconnects):
```json
{
  "event": "OTA_RESULT",
  "status": "ROLLED_BACK",
  "attempted_version": "2.1.0",
  "current_version": "2.0.0",
  "timestamp": 1741823400
}
```

### 13.4 OTA Battery Gate
- Normal: Battery must be >= 20% to begin OTA download
- ADS1115 fault (battery unknown): OTA blocked automatically
- Server can send FORCE_OTA flag to bypass both gates
- FORCE_OTA is a one-time authorization, cleared after OTA attempt completes or fails
- Forced OTA procedure: team verifies battery via V50 LEDs → server sets FORCE_OTA → customer/team resets device → device connects → receives forced OTA

### 13.5 Rollback Monitoring
Firmware version included in every health packet. Server detects version mismatch passively. Explicit OTA_RESULT message provides deterministic confirmation.

---

## 14. Battery Management

### 14.1 Battery Thresholds
| Threshold | Level | Behavior |
|---|---|---|
| NORMAL | > 15% | All operations nominal. Auto-OTA proceeds. |
| WARNING | <= 15% | All operations continue. Auto-OTA blocked. Server alerted. Personnel dispatched. Server can override OTA block if absolutely necessary. |
| CRITICAL | <= ~0.07% (2× session energy) | Skip capture. Attempt connection. Send critical alert. Upload pending metadata only. Skip image backlog. Deep sleep immediately. |

Both thresholds are server-configurable per device. Stored in NVS.

### 14.2 Session Energy Estimate
```
Typical wake cycle energy consumption:
  Boot + sensors:    ~0.056mAh
  Camera + flash:    ~1.111mAh
  Connection:        ~0.729mAh
  Upload session:    ~2.917mAh
  Housekeeping:      ~0.056mAh
  Total:             ~4.87mAh per cycle

2× session (CRITICAL threshold): ~9.74mAh
V50 capacity:                    13,400mAh
```

### 14.3 ADS1115 Fault Battery Behavior
If ADS1115 fails and battery level is unknown:
- Continue all normal operations
- Auto-OTA blocked (battery level unverifiable)
- Every health packet: `ads1115_fault: true`, `ota_blocked: true`, `ota_block_reason: "battery_unverifiable"`
- Server alerts team for physical inspection
- Forced OTA available via server override after manual battery verification

---

## 15. Error Reporting and Fault Handling

### 15.1 Reset Reason Taxonomy
| Reset Reason | Classification | Action |
|---|---|---|
| ESP_RST_POWERON | Informational | Log in health packet, do not increment crash counter |
| ESP_RST_DEEPSLEEP | Expected | Normal operation, do not increment crash counter |
| ESP_RST_SW | Intentional | Log in health packet, do not increment crash counter |
| ESP_RST_WDT | FAULT | Increment crash counter, store phase, set pending_reset_report |
| ESP_RST_PANIC | FAULT | Increment crash counter, store phase, set pending_reset_report |
| ESP_RST_BROWNOUT | FAULT | Increment crash counter, store phase, set pending_reset_report |

### 15.2 Watchdog Reboot Reporting
- Phase name written to NVS at start of each phase
- On FAULT reset: `reset_reason` + `reset_phase` stored in NVS
- `pending_reset_report: true` set in NVS
- Reported in health packet at next session
- `pending_reset_report` cleared after successful health packet delivery

### 15.3 Crash Loop Detection and Safe Mode

**Detection:**
- `crash_count` incremented on every FAULT reset
- `crash_count` reset to 0 on successful completion of any full wake cycle
- `crash_count >= 3` → enter SAFE MODE

**Safe Mode Operation:**
- Disabled: camera, flash, SD image operations, sensor reads, auto-OTA
- Enabled: radio connection, health packet, button input, forced OTA
- Sleep interval: 30 minutes default, server-overridable
- Flash ring: slow single pulse at 15% (2sec on / 2sec off) while awake
- NeoPixel: OFF during safe mode

**Safe Mode Exit:**
1. Server sends `FORCE_NORMAL_MODE` command → reset `crash_count` to 0 → reboot
2. Successful OTA update → new firmware completes cycle → `crash_count` resets naturally
3. Factory reset via button → full reprovision required

### 15.4 I2C Bus Lockup Detection and Recovery

**Detection:** Both BME280 and ADS1115 fail to respond on boot.

**Recovery sequence:**
1. Attempt 9-clock-pulse bit-bang recovery on SCL while monitoring SDA
2. If SDA released → send STOP condition → reinit Wire → re-probe devices
3. If still locked → full I2C peripheral reset + repeat 9-pulse sequence
4. If still locked → classify as `I2C_BUS_FAULT_UNRECOVERABLE`

**I2C recovery is always Step 4 in boot sequence — before any code uses the bus.**

**Result classification:**
- Both respond after recovery → `I2C_LOCKUP_RECOVERED` (soft event, monitor frequency)
- One device responds → specific device fault (not bus lockup)
- Neither responds after recovery → `i2c_bus_fault: true` (hard fault)

### 15.5 NTP Sync Warning
- NTP attempted every connected session as Step 0 (before health packet)
- Warning condition: any capture taken with `unix_timestamp = 0`
- `rtc_unsynced: true` flagged in health packet
- `last_ntp_sync` timestamp stored in NVS and reported in every health packet
- Server back-fills approximate timestamp from upload receipt time, flags as estimated
- **Hardware note for V3:** Add DS3231 battery-backed external RTC to eliminate this condition permanently

### 15.6 Image Quality and Lens Obstruction
See Section 6.4 for lens obstruction detection definition.  
See Section 19 for health packet quality metric fields.

---

## 16. Edge Case Definitions

| Edge Case | Behavior |
|---|---|
| SD card missing at boot | No capture attempted. Connect if possible. Health packet flags `sd_missing: true`. Server alerts team. |
| SD card corrupted filesystem | One remount attempt. If fails → treat as missing. Never write to corrupted filesystem. |
| BME280 fails to respond | Null telemetry values in metadata and health packet. `bme280_fault: true`. Never blocks capture or upload. |
| ADS1115 fails to respond | Battery level = UNKNOWN. Continue all ops except auto-OTA. See Section 14.3. |
| Camera fails to initialize | Write failed capture record to metadata. Skip to connection phase. Report in health packet. |
| RTC not synced at capture | Proceed with `unix_timestamp = 0`. Flag `rtc_unsynced: true`. Server estimates timestamp from receipt time. |
| HaLow module not on SPI | Fall back to 2.4GHz if credentials available. Flag `halow_module_fault: true`. Report in health packet. |
| V50 battery critically low | Skip capture. Connect. Send critical alert. Upload metadata only. Deep sleep immediately. |
| Connection established, server not responding | Retry once (15sec). If still no response → treat as offline. Log `server_unreachable` event. |
| Partial image on SD (corrupt JPEG header) | One SD re-read retry. If still invalid → quarantine to /corrupt/. Write fault record to metadata with fault_hint. |
| Flash LED not responding to duty | Retry probe at 50% duty. If still no response → capture anyway at max duty. Flag `flash_fault: true`. Report in health packet. |
| OTA maintenance window, battery < 20% | Skip OTA. Report `OTA_DEFERRED_LOW_BATTERY`. Server reschedules. |
| Crash loop (3 consecutive FAULT resets) | Enter SAFE MODE. See Section 15.3. |
| Image counter rollover (99,999,999) | Flag as device lifecycle event to server. Behavior TBD — do not silently reset to 0. |
| Upload attempt fails 5 consecutive times | Flag image_id as `UPLOAD_FAILING` in health packet. Server investigates. |

---

## 17. LED Indication System

### 17.1 Architecture
Two independent LED systems with distinct responsibilities:

| System | Hardware | Purpose | Capture Behavior |
|---|---|---|---|
| NeoPixel | GPIO21, onboard RGB | Routine status | MUST be OFF during capture |
| Flash Ring | GPIO43 → MOSFET, 325mm | Image illumination + critical fault indication | Controlled by capture pipeline or status system — never simultaneously |

### 17.2 Pre-Capture LED Blackout Rule
NeoPixel state saved → NeoPixel OFF → capture executes → NeoPixel state restored.  
Flash ring PWM must be verified at 0 before capture pipeline begins.

### 17.3 NeoPixel State Map
| Device State | Color | Pattern |
|---|---|---|
| Deep sleep | OFF | — |
| Wake confirmation | GREEN | Single 200ms flash |
| Connecting to network | BLUE | Slow pulse 1sec on / 1sec off |
| Uploading data | CYAN | Slow pulse 1sec on / 1sec off |
| Provisioning mode | PURPLE | Fast pulse 250ms on / 250ms off |
| Low battery warning | YELLOW | Double flash every 5 seconds |
| Critical battery | ORANGE | Triple flash every 5 seconds |
| OTA in progress | BLUE | Rapid pulse 100ms on / 100ms off |
| OTA success | GREEN | 3 long flashes 500ms on / 200ms off |
| OTA failed / rolled back | RED | 3 short-long pairs (SOS-like) |
| Factory reset countdown | RED | Steady, growing 10%→100% over 10 seconds |
| Capture sequence active | OFF | Explicitly blanked |
| Safe mode | OFF | Flash ring handles safe mode indication |

### 17.4 Flash Ring State Map
| Device State | Pattern | Brightness |
|---|---|---|
| Normal capture | Steady on | Calibrated by convergence loop |
| Safe mode (each 30min wake) | Slow single pulse, 2sec on / 2sec off | 15% |
| Lens obstruction confirmed | Rapid double pulse, 150ms / 150ms / 2sec off | 15% |
| Factory reset countdown | Steady growing | 10% → 100% over 10 seconds |
| All other states | OFF | — |

### 17.5 Deep Sleep LED Rule
All LEDs OFF during deep sleep. No exceptions.  
Safe mode flash ring pattern activates only while device is awake during 30-minute check cycle.

---

## 18. Button Interface

### 18.1 Hardware
- Single tactile switch: GPIO44 (D7) to GND
- Internal pull-up: `pinMode(44, INPUT_PULLUP)` — HIGH idle, LOW pressed
- Debounce: software only (50ms), no hardware capacitor

### 18.2 Defined Press Patterns
| Action | Threshold | Function |
|---|---|---|
| Hold during power-on | Held at boot | Factory reset |
| Short press | < 1 second | TBD |
| Double press | Two presses < 500ms apart | TBD |
| Hold (powered) | 3 seconds | Maintenance mode (functions TBD) |
| Hold (powered) | 10 seconds | Factory reset |

### 18.3 Button Event Architecture
Button detection decodes press patterns and emits named events to a handler:
```
BTN_SHORT_PRESS
BTN_DOUBLE_PRESS
BTN_HOLD_3S
BTN_HOLD_10S
BTN_POWER_ON_HOLD
```
Adding new button functions requires only one handler mapping change — detection logic untouched.

### 18.4 Factory Reset Behavior
- Clears: all NVS credentials, provisioning state, crash counter, all device config
- Preserves: nothing — full clean state
- Enters: provisioning mode immediately after reset
- LED: factory reset countdown pattern (flash ring growing to full brightness)
- User must hold through full 10 seconds to confirm — accidental triggers prevented

---

## 19. Health Packet Specification

Sent as JSON. Always first in every upload session. Always after NTP sync attempt.

```json
{
  "device_id": "AA:BB:CC:DD:EE:FF",
  "firmware_version": "2.0.0",
  "timestamp": 1741823400,
  "uptime_cycles": 847,

  "connectivity": {
    "active_radio": "HALOW",
    "operating_on_fallback": false,
    "halow_module_fault": false,
    "rssi": -67
  },

  "rtc": {
    "rtc_unsynced": false,
    "last_ntp_sync": 1741820000
  },

  "battery": {
    "battery_pct": 78.4,
    "battery_state": "NORMAL",
    "ads1115_fault": false,
    "ota_blocked": false,
    "ota_block_reason": null
  },

  "storage": {
    "sd_present": true,
    "sd_fault": false,
    "sd_free_pct": 94.2,
    "sd_state": "NORMAL",
    "images_pending": 3,
    "images_uploaded_this_session": 3
  },

  "sensors": {
    "bme280_fault": false,
    "temperature_c": 22.4,
    "humidity_pct": 61.2,
    "pressure_hpa": 1013.2,
    "i2c_bus_fault": false,
    "i2c_lockup_recovered": false
  },

  "capture": {
    "capture_status": "SUCCESS",
    "last_luminance": 198,
    "last_duty": 4096,
    "last_convergence_iters": 2,
    "last_aec_status": "LOCKED",
    "flash_fault": false,
    "avg_luminance": 201.4,
    "avg_duty": 4120.6,
    "avg_convergence_iters": 2.2,
    "luminance_out_of_range": false,
    "duty_maxed_out": false,
    "convergence_high": false,
    "lens_obstruction_suspected": false,
    "lens_obstruction_confirmed": false,
    "lens_anomaly_counter": 0
  },

  "faults": {
    "reset_reason": "DEEPSLEEP",
    "reset_phase": null,
    "pending_reset_report": false,
    "safe_mode": false,
    "crash_count": 0,
    "ota_pending": false,
    "upload_failing_image_ids": []
  },

  "schedule": {
    "current_stage": 2,
    "capture_interval_minutes": 120,
    "next_capture_timestamp": 1741830600
  }
}
```

---

## 20. NVS State Reference

Complete list of all values stored in NVS:

**Provisioning:**
- `halow_ssid`, `halow_password`
- `wifi_ssid`, `wifi_password`
- `radio_preference`
- `device_provisioned` (bool)

**Identity:**
- `device_mac` (string)
- `image_count` (uint32) — never reset by OTA

**Schedule:**
- `current_stage` (uint8)
- `capture_interval_minutes` (uint16)
- `stage_set_timestamp` (uint32)
- `next_capture_timestamp` (uint32)
- `next_maintenance_timestamp` (uint32)

**Battery thresholds (server-configurable):**
- `battery_warning_pct` (float, default 15.0)
- `battery_critical_mah` (float, default 9.74)

**Quality thresholds (server-configurable):**
- `luminance_min`, `luminance_max`
- `convergence_warn`
- `duty_warn_pct`

**Fault state:**
- `crash_count` (uint8)
- `last_phase_attempted` (string)
- `last_phase_start_time` (uint32)
- `pending_reset_report` (bool)
- `reset_reason` (uint8)

**OTA state:**
- `ota_pending` (bool)
- `ota_firmware_url` (string)
- `ota_maintenance_window` (uint32)
- `ota_firmware_hash` (string)
- `ota_battery_gate_open` (bool) — one-time server override

**Lens state:**
- `lens_anomaly_counter` (uint8)
- `lens_obstruction_suspected` (bool)
- `lens_obstruction_confirmed` (bool)

**RTC:**
- `last_ntp_sync` (uint32)

**Quality history (circular buffers, last 5 captures):**
- `luminance_history[5]`
- `duty_history[5]`
- `convergence_history[5]`

---

## 21. Server Communication Contract

### 21.1 Protocol
TBD — HTTP/HTTPS (REST) or MQTT. Firmware implements a clean abstraction layer so protocol can be swapped without touching any other module.

**Storage abstraction layer (protocol-agnostic interface):**
```cpp
bool storage_save_capture(uint32_t image_id, camera_fb_t* jpeg, SensorData* env);
bool storage_mark_uploaded(uint32_t image_id);
bool storage_delete_uploaded(uint32_t image_id);
bool storage_get_next_pending(uint32_t* image_id);
bool storage_get_metadata(uint32_t image_id, ImageMetadata* out);
uint32_t storage_get_free_space_kb();
```

### 21.2 Server Commands (Device Receives)
| Command | Action |
|---|---|
| `SET_SCHEDULE` | Update stage + interval, store in NVS |
| `SET_THRESHOLDS` | Update quality/battery thresholds in NVS |
| `FORCE_OTA` | Set ota_battery_gate_open, proceed with OTA |
| `FORCE_NORMAL_MODE` | Reset crash_count to 0, reboot from safe mode |
| `LENS_OBSTRUCTION_CONFIRMED` | Set lens_obstruction_confirmed in NVS, activate flash ring pattern |
| `LENS_OBSTRUCTION_CLEARED` | Clear all lens flags in NVS |
| `LENS_OBSTRUCTION_RESOLVED` | Clear confirmed flag, log resolution |
| `SET_SAFE_MODE_INTERVAL` | Override 30min safe mode sleep interval |
| `FORCE_UPLOAD` | Trigger immediate upload of all pending data |

### 21.3 Backend Requirements (Flags for Backend Teammate)
- Upload endpoint must be **idempotent** — duplicate image_id submissions handled gracefully
- Must handle **upload bursts** after extended offline periods
- Must store **mask parameters per device** (dish position, radius) for server-side masking
- Must perform **server-side masking and watermarking** — device delivers raw JPEG
- Must **back-fill timestamps** for images received with `unix_timestamp = 0`
- Must track **firmware versions per device** for OTA rollback detection
- Must handle **gap detection** in sequential image IDs to identify missing images

---

## 23. BME280 Interval Data Logging

### 23.1 Overview
In addition to the full wake cycle (image capture + upload session), the device operates a second lightweight wake mode dedicated exclusively to BME280 environmental logging. This provides continuous high-frequency environmental context between image captures — enabling the server to build a meaningful picture of the thermal and humidity conditions experienced by mold cultures throughout their growth cycle.

### 23.2 Two Environmental Record Types
All environmental records share a single log file but are distinguished by record type:

```
TYPE_INTERVAL (0) — Periodic lightweight BME wake
  Triggered by:  RTC alarm every 15 minutes
  Contains:      temp, humidity, pressure + timestamp
  Purpose:       Continuous environmental time series
  image_id:      0 (not image-correlated)

TYPE_IMAGE (1) — BME reading at image capture time
  Triggered by:  Full wake cycle capture pipeline
  Contains:      temp, humidity, pressure + timestamp + image_id
  Purpose:       Environmental snapshot correlated to specific image
  image_id:      Populated — links record to paired JPEG
```

Server filters by record_type to separate continuous log from image-correlated snapshots. The `image_id` field in TYPE_IMAGE records is the join key between environmental data and image data on the server.

### 22.3 Minimal BME Wake Cycle
The lightweight wake is optimized for minimum active time and minimum power consumption. No camera, no radio, no full boot sequence — only what is needed to read and store one environmental record.

```
RTC ALARM FIRES (every 15 minutes)
        │
        ▼
[BOOT — minimal]
  Read reset reason
  Check crash_count (safe mode gate — see 22.6)
  Set watchdog: BOOT_SENSORS timeout (10 seconds)
        │
        ▼
[BME READ]
  Attempt BME280 read directly (no I2C health check)
        │
        ├── SUCCESS → apply calibration offsets
        │             build BmeLogRecord (TYPE_INTERVAL)
        │
        └── FAIL → retry once after 10ms
                    │
                    ├── SUCCESS → build record normally
                    │
                    └── FAIL → build fault record
                                record_status: BME_FAULT
                                null sensor values
                                increment bme_wake_fail_count in NVS
        │
        ▼
[SD WRITE]
  Append BmeLogRecord to bme_log.dat
  On SD write fail → increment bme_sd_fail_count in NVS
                      log lost reading count (not recoverable)
        │
        ▼
[HOUSEKEEPING]
  Update next_bme_wake_timestamp in NVS
  Reset watchdog
        │
        ▼
DEEP SLEEP until next RTC alarm
(next_bme_wake or next_capture — whichever is sooner)
```

**Total active time target: <200ms**  
**Estimated energy cost: ~0.007mAh per wake**  
**Daily cost at 15-min interval: ~0.67mAh — less than 1.2% of total daily consumption**

### 22.4 I2C Strategy for Minimal Wake
Full 9-clock-pulse I2C recovery is NOT run during minimal BME wake — it adds latency and complexity to a cycle that must be fast. Instead:
- Direct BME280 read attempted immediately
- Single retry on failure (10ms delay)
- Fault record logged if both attempts fail
- Full I2C recovery deferred to next full wake cycle boot sequence (Step 4)
- Consecutive BME wake failures tracked in NVS (`bme_wake_fail_count`)
- Reported in health packet at next full session

### 22.5 BmeLogRecord Struct
```cpp
struct BmeLogRecord {
    uint8_t  struct_version;      // Schema version
    uint8_t  record_type;         // TYPE_INTERVAL (0) or TYPE_IMAGE (1)
    uint32_t unix_timestamp;      // 0 if RTC unsynced at wake time
    uint32_t log_sequence_id;     // Monotonic counter — own sequence,
                                  // independent of image_count
    uint32_t image_id;            // TYPE_IMAGE: paired image ID
                                  // TYPE_INTERVAL: 0
    float    temperature_raw;     // BME280 uncorrected °C
    float    temperature;         // Corrected (raw + offset)
    float    humidity_raw;        // BME280 uncorrected %RH
    float    humidity;            // Corrected
    float    pressure_raw;        // BME280 uncorrected hPa
    float    pressure;            // Corrected
    bool     cal_active;          // Calibration active at log time
    uint8_t  record_status;       // Bitmask:
                                  //   OK
                                  //   BME_FAULT
                                  //   RTC_UNSYNCED
                                  //   BME_DELAYED_CAPTURE_BUSY
                                  //   BME_INTERVALS_MISSED
    uint16_t delay_ms;            // Scenario 4/8: ms between scheduled
                                  // and actual read time (0 if on time)
    uint8_t  missed_intervals;    // Scenario 8: intervals that passed
                                  // without a reading (0 if none)
    bool     uploaded;            // Server confirmed receipt
    uint16_t crc16;               // CRC of all preceding fields
};
```

`log_sequence_id` provides independent gap detection for the environmental time series on the server — separate from image sequence gap detection.

### 22.6 Safe Mode Interaction — Phase-Aware
BME logging suspension in safe mode is determined by the phase that caused the crash loop — not a blanket disable:

```
reset_phase = BOOT_SENSORS:
  bme_logging_suspended = true
  Both BME reads and SD writes suspended
  (I2C or SD is implicated in the crash)

reset_phase = any other phase:
  bme_logging_suspended = false
  BME interval logging continues normally
  Environmental record is preserved through camera/comms crashes
```

`bme_logging_suspended` stored in NVS. Reported in health packet: `bme_logging_active: true/false`

This ensures environmental data is never lost to a camera firmware bug, while never crash-looping on a broken BME280 or SD card.

### 22.7 Dual Wake Scenario Definitions

All eight scenarios governing the interaction between BME wake cycles, capture cycles, and OTA maintenance windows:

**Scenario 1 — Normal separation (most common ~90% of wakes)**
```
BME due, capture not due
→ Minimal BME cycle only
→ Reschedule next_bme_wake = now + 15min
→ Sleep until next event
```

**Scenario 2 — Collision: BME and capture due simultaneously**
```
Both timestamps due at same time
→ Full capture cycle only — no separate minimal BME cycle
→ TYPE_IMAGE record serves as the BME record for this interval
→ Reschedule next_bme_wake = capture_completion_time + 15min
→ No duplicate records written
```

**Scenario 3 — BME interval timing drift**
```
Timing is relative — 15 minutes from last actual reading
next_bme_wake = last_bme_timestamp + interval_minutes
No wall clock pinning — drift over time is acceptable
```

**Scenario 4 — Capture cycle overruns a BME wake time (single missed interval)**
```
At end of every full capture cycle — before sleeping:
  Check: now >= next_bme_wake?
        │
        ├── NO → sleep normally, no action
        │
        └── YES (one interval overdue) → execute BME read immediately
              Write TYPE_INTERVAL record:
                record_status: BME_DELAYED_CAPTURE_BUSY
                unix_timestamp: now (actual read time — not scheduled time)
                delay_ms: (now - next_bme_wake_timestamp) in ms
                missed_intervals: 0
              Reschedule next_bme_wake = now + 15min
              Increment bme_delayed_count in NVS
              Report bme_delayed_readings_count in health packet
```

**Scenario 5 — Device wakes slightly late (minor RTC drift)**
```
bme_due evaluated against actual now at wake
Reschedule from actual wake time naturally
No special handling required
```

**Scenario 6 — OTA maintenance window collides with capture**
```
Both capture and maintenance due simultaneously
→ Capture executes first (experiment data is primary product)
→ After capture + upload session complete:
    Check battery gate for OTA
    Proceed with OTA if battery adequate
→ Reschedule next_capture normally
→ OTA window considered served regardless of OTA outcome
→ Capture is never delayed for OTA
```

**Scenario 7 — Missed OTA maintenance window (device was offline)**
```
Device reconnects after scheduled OTA window has passed
→ Report in health packet:
    missed_ota_window: true
    scheduled_window_timestamp: [original window]
    actual_reconnect_timestamp: now
→ Device does NOT execute OTA autonomously
→ Server is always the authority on OTA rescheduling
→ Server decides whether to push new window or defer
```

**Scenario 8 — Multiple BME intervals missed during long capture/upload cycle**
```
At end of capture cycle:
  Check: how many complete 15-min intervals have passed
         since next_bme_wake_timestamp?
        │
        ├── 1 interval overdue → Scenario 4 handling
        │
        └── 2+ intervals overdue →
              Execute ONE BME read immediately
              Write TYPE_INTERVAL record:
                record_status: BME_DELAYED_CAPTURE_BUSY
                               | BME_INTERVALS_MISSED
                unix_timestamp: now (actual read time)
                delay_ms: (now - next_bme_wake_timestamp) in ms
                missed_intervals: N (count of unread intervals)
              Reschedule next_bme_wake = now + 15min
              Report in health packet:
                bme_missed_intervals_total: cumulative count

Scientific integrity rule: never fabricate or back-fill readings
for intervals the device did not actually measure. One real reading
with a missed_intervals count is always preferred over reconstructed
data points.
```

### 22.8 RTC Scheduling — Dual Wake Times
The ESP32-S3 RTC timer must support two independent wake targets simultaneously. Deep sleep is entered with the earlier of the two:

```cpp
uint32_t next_wake = min(next_capture_timestamp,
                         next_bme_wake_timestamp);
// Also consider next_maintenance_timestamp for OTA
uint32_t next_wake = min({next_capture_timestamp,
                           next_bme_wake_timestamp,
                           next_maintenance_timestamp});
esp_sleep_enable_timer_wakeup(next_wake - now());
```

On wake, device reads reason from NVS timestamps to determine which event fired and executes the appropriate cycle.

### 22.8 bme_log.dat Storage
- Location: SD card root `/bme_log.dat`
- Format: fixed-size binary struct (same O(1) seek pattern as metadata.dat)
- Retrieval by log_sequence_id: `offset = (log_sequence_id - 1) * sizeof(BmeLogRecord)`
- Retention: same policy as images (currently purge-oldest-uploaded when near capacity)
- CRC16 per record for partial write detection

### 22.9 Upload Session — Revised Sequence
BME log batch upload added as Step 4 in the upload session:

```
[STEP 1] Health packet (JSON)
[STEP 2] Pending image metadata records
[STEP 3] Pending image uploads
[STEP 4] BME log batch upload          ← NEW
         All BmeLogRecords with uploaded = false
         Sent as batch — single server ACK for entire batch
         On ACK: mark all records uploaded = true
         45 second timeout for entire batch
         On timeout: retry next session
[STEP 5] Receive server messages
[STEP 6] Acknowledge + close
```

### 22.10 Health Packet Additions
```json
"bme_logging": {
  "bme_logging_active": true,
  "bme_wake_fail_count": 0,
  "bme_sd_fail_count": 0,
  "bme_log_interval_minutes": 15,
  "bme_pending_records": 47,
  "last_interval_temp": 22.4,
  "last_interval_humidity": 61.2,
  "last_interval_pressure": 1013.2,
  "last_interval_timestamp": 1741823100
}
```

`bme_wake_fail_count` and `bme_sd_fail_count` reset to 0 after successful health packet delivery. Last interval reading gives server a lightweight current-conditions snapshot without cluttering the main sensor fields.

### 22.11 Server Communication Contract Additions
- BME log upload endpoint must be **idempotent** — duplicate log_sequence_id submissions handled gracefully
- Server uses `record_type` flag to separate continuous log from image-correlated records
- Server uses `image_id` in TYPE_IMAGE records to join environmental data to image records
- Server uses `log_sequence_id` gaps to detect missing interval records
- `bme_log_interval_minutes` is server-configurable via SET_SCHEDULE command (default 15)

### 22.12 Power Budget — BME Logging Addition
```
Minimal BME wake cycle energy:
  Active time:      ~140ms
  SD write:         ~100ms additional
  Total active:     ~240ms × 100mA = 0.007mAh per wake

96 wakes/day (every 15 min):
  Daily BME cost:   96 × 0.007mAh = ~0.67mAh/day

Full daily budget (2hr capture interval):
  Image cycles:     ~58.4mAh/day
  BME logging:      ~0.67mAh/day
  Deep sleep:       ~0.48mAh/day
  Total:            ~59.6mAh/day

V50 13,400mAh runtime: ~224 days (~7.5 months)
BME logging impact on runtime: <0.5% reduction
Battery decision: V50 13,400mAh confirmed for V2
```

---

## 22. Sensor Calibration Support

### 22.1 Overview
Calibration is a **customer-driven optional feature**. Devices operate identically whether calibrated or not. When offsets are zero and no certificate is present, calibration is invisible and adds no operational overhead. When a customer requires certified measurements — laboratory deployments, compliance frameworks — the calibration system activates without firmware changes.

### 22.2 Design Principles
- Raw values enable server-side retroactive reprocessing if offsets change
- Laboratory customers can audit raw values independently
- Calibration metadata is machine-readable and reportable
- BLE interface handles offset entry — no display required
- Server monitors certificate expiry and alerts team proactively

### 22.3 NVS Calibration State
```cpp
float    temp_offset;          // °C correction (default 0.0)
float    humidity_offset;      // %RH correction (default 0.0)
float    pressure_offset;      // hPa correction (default 0.0)
char     cal_cert_number[32];  // Certificate ID (default empty)
uint32_t cal_expiry_date;      // Unix timestamp (default 0)
char     sensor_serial[32];    // BME280 serial / lot number (default empty)
bool     cal_active;           // true if cert_number is present and not expired
```

### 22.4 Corrected Reading Formula
```cpp
float corrected_temp     = raw_temp     + temp_offset;
float corrected_humidity = raw_humidity + humidity_offset;
float corrected_pressure = raw_pressure + pressure_offset;
```
Applied before storing to metadata and before transmission. Both raw and corrected values stored and transmitted.

### 22.5 BLE Calibration Interface
Extends existing provisioning GATT service. Only used by vendor team when customer requires calibration. Compatible with existing nRF Connect workflow.

| Characteristic | Properties | Data |
|---|---|---|
| LIVE_TEMP_RAW | Read | float — live uncorrected reading |
| LIVE_HUMIDITY_RAW | Read | float — live uncorrected reading |
| LIVE_PRESSURE_RAW | Read | float — live uncorrected reading |
| TEMP_OFFSET | Read / Write | float |
| HUMIDITY_OFFSET | Read / Write | float |
| PRESSURE_OFFSET | Read / Write | float |
| CAL_CERT_NUMBER | Read / Write | string |
| CAL_EXPIRY_DATE | Read / Write | uint32 unix timestamp |
| SENSOR_SERIAL | Read / Write | string |

Live read characteristics allow calibration technician to compare device output against reference standard in real time without a display.

### 22.6 Health Packet — Calibration Fields
```json
"sensors": {
  "temperature_raw": 22.7,
  "temperature_corrected": 22.4,
  "humidity_raw": 63.0,
  "humidity_corrected": 61.2,
  "pressure_raw": 1013.0,
  "pressure_corrected": 1013.2,
  "cal_active": true,
  "cal_cert_number": "CAL-2026-004821",
  "cal_expiry_date": 1710979200,
  "sensor_serial": "SN-BME-00142",
  "cal_expiry_warning": false
}
```
When `cal_active` is false (uncalibrated device): raw and corrected values are identical, cert fields are empty/null. No behavioral difference.

### 22.7 Calibration Expiry Monitoring
Server monitors `cal_expiry_date` from health packet:
- **30 days before expiry:** Server alerts vendor team — schedule sensor swap or recertification
- **At expiry:** Server sets `cal_active: false` effectively, alerts team, flags in customer dashboard if applicable
- **Expired cert:** Device continues operating and reporting — expiry is a server-side flag, not a device fault

### 22.8 ImageMetadata — Calibration Fields
Add to `ImageMetadata` struct:
```cpp
float    temperature_raw;      // Uncorrected BME280 reading
float    humidity_raw;
float    pressure_raw;
bool     cal_active;           // Was calibration active at time of capture
```
Corrected values already in existing temperature/humidity/pressure fields.  
Raw values enable retroactive reprocessing if offsets are updated after capture.

### 22.9 Operational Procedure
```
CALIBRATION WORKFLOW:

1. Remove BME280 module from device (socketed for this purpose)
2. Send to calibration lab with sensor serial number
3. Lab compares against NIST-traceable reference
4. Lab provides: temp/humidity/pressure offsets + certificate number + expiry
5. Your team connects to device via BLE (nRF Connect)
6. Read LIVE_*_RAW characteristics to verify sensor is responding
7. Write offsets, cert number, expiry date, sensor serial via BLE
8. Verify corrected readings match expected values via LIVE_* reads
9. Disconnect — device stores all calibration data in NVS
10. Calibration data survives all OTA updates

SENSOR SWAP WORKFLOW (recalibration or replacement):
1. Swap BME280 module in field (socketed — no soldering)
2. Connect via BLE
3. Clear old calibration data
4. Enter new sensor serial and new offsets if pre-certified
5. Confirm live readings via BLE
6. Done — NVS updated, health packet reflects new cal state
```

### 22.10 Notes
- Calibration is entirely optional — most deployments will run uncalibrated
- Architecture is ready for certification without requiring it
- If no customer ever requests calibration, this system costs zero operational overhead
- If a laboratory customer requires calibration, the system is complete without firmware changes

---

## 24. Open Items and Future Considerations

### 22.1 Must Resolve Before Development Begins
| Item | Detail |
|---|---|
| Communication protocol | HTTP/HTTPS vs MQTT — decision needed before upload session implementation |
| Storage implementation | File-per-image (Option 2) vs circular indexed (Option 3) — follows from protocol decision |
| HaLow library validation | Wio-WM6108 Arduino/PlatformIO library must be evaluated as first proof-of-concept |
| HaLow image transfer throughput | Real-world throughput test required before architecture is locked in |
| LED ring current limiting | Confirm 325mm ring has onboard series resistors before powering up |
| USB-C breakout board | Must expose SBU/A8/B8 pins — confirm chosen board before PCB finalization |
| USB-C cable spec | Must be USB-C 3.1 or 3.2 — verify before field deployment |
| BME280 SDO/CSB wiring | SDO → GND (0x76), CSB → 3.3V — confirm on chosen breakout board |
| ADS1115 ADDR pin | Must be connected to GND — confirm not floating |
| Data retention policy | Team discussion pending — fixed-day limit (7 days) vs purge-on-threshold |
| Image counter rollover | Define exact behavior at 99,999,999 images |
| Double-press button function | Currently undefined |
| Short-press button function | Currently undefined |
| Maintenance mode functions | 3-second hold mode functions TBD |
| GATT characteristic UUIDs | Must be defined before BLE provisioning implementation |

### 22.2 V3 Hardware Recommendations
| Item | Detail |
|---|---|
| External battery-backed RTC | DS3231 or similar — eliminates timestamp = 0 condition permanently. <$1 BOM addition. |
| Power mux / ideal diode | Prevent back-feed if V50 and PC USB-C connected simultaneously |
| Dedicated second button | If maintenance mode requires more than one physical interaction type |

### 22.3 Future Firmware Features (Not V2 Scope)
| Feature | Notes |
|---|---|
| Custom BLE provisioning app | Phase 2 provisioning — targets same GATT characteristics as nRF Connect flow |
| Browser-based provisioning | Via vendor website on mobile device |
| Per-device adaptive quality thresholds | Server learns each device's baseline metrics over time |
| Multi-device fleet management commands | Broadcast commands to device groups |
| Scheduled lens cleaning reminders | Server-generated alerts tied to dish swap schedule |

---

*End of V2 Firmware Specification — Version 1.0*  
*Next step: HaLow library proof-of-concept validation*
