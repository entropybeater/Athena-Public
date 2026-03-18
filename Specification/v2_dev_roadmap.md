# Petri Dish Monitor — V2 Firmware Development Roadmap
### XIAO ESP32-S3 Sense | Arduino Framework | PlatformIO
**Document Version:** 1.0  
**Status:** Draft for Review  
**Reference Spec:** V2 Firmware Specification v1.0

---

## Guiding Principles

- **Validate before building.** The two highest-risk unknowns — HaLow library support and image transfer throughput — must be proven before architecture is locked in.
- **Bottom-up construction.** Hardware drivers and primitives first. Logic layers second. Integration last.
- **Each phase produces a testable, runnable device.** No phase ends with untestable code.
- **Protocol decision gates Phase 4.** Upload session implementation cannot begin until HTTP vs MQTT is decided.
- **Spec is the source of truth.** Any deviation discovered during development updates the spec, not the other way around.

---

## Risk Register

These items must be resolved before or during Phase 1. They are not implementation tasks — they are go/no-go decisions that could reshape the architecture.

| Risk | Impact if Unresolved | Resolution Target |
|---|---|---|
| HaLow library unavailable or non-functional | Entire communication strategy must change | Phase 1 |
| HaLow image transfer throughput insufficient | Storage and scheduling assumptions invalid | Phase 1 |
| Camera mode switching without deinit/reinit not possible on OV3660 | Capture pipeline must be redesigned | Phase 2 |
| USB-C breakout board does not expose SBU pins | Battery monitoring impossible | Before Phase 1 |
| LED ring has no onboard current-limiting resistors | Hardware damage risk | Before Phase 1 |
| Communication protocol decision (HTTP vs MQTT) | Upload session cannot be implemented | Before Phase 4 |

---

## Phase Overview

```
PHASE 0 — Hardware Verification          (before any firmware)
PHASE 1 — Proof of Concept Validation    (risk elimination)
PHASE 2 — Core Drivers and Primitives    (hardware abstraction)
PHASE 3 — Capture Pipeline               (image acquisition)
PHASE 4 — Storage and Metadata           (SD card system)
PHASE 5 — Connectivity and Upload        (radio + server comms)
PHASE 6 — Scheduling and Power           (deep sleep + duty cycle)
PHASE 7 — Provisioning and OTA           (BLE + firmware updates)
PHASE 8 — Error Handling and Fault Recovery (robustness layer)
PHASE 9 — Health Packet and Telemetry    (observability)
PHASE 10 — Integration and System Test   (full system validation)
PHASE 11 — Field Validation              (3-device test deployment)
```

---

## Phase 0 — Hardware Verification
**Goal:** Confirm all hardware is correct before writing a line of firmware.  
**Exit criteria:** All unresolved hardware items from spec Section 24 confirmed.

### Tasks
- [ ] Confirm LED ring has onboard current-limiting resistors before applying power
- [ ] Confirm USB-C breakout board exposes SBU / A8 / B8 pins
- [ ] Confirm USB-C cable is 3.1 or 3.2 spec (SBU pins present)
- [ ] Confirm BME280 breakout: SDO → GND (address 0x76), CSB → 3.3V (I2C mode)
- [ ] Confirm ADS1115 ADDR pin connected to GND (not floating)
- [ ] Verify V50 SBU pin outputs expected voltage range (1.6V–2.1V) with multimeter
- [ ] Verify IRLZ44N gate resistor (220Ω) and pull-down (10kΩ) populated correctly
- [ ] Verify flyback diode (1N5819) orientation correct across LED ring
- [ ] Power-on test: XIAO boots, USB CDC serial responds
- [ ] Confirm HaLow module seats correctly on B2B connector (if present)
- [ ] Confirm GPIO41/42 (D11/D12) are inaccessible with HaLow module installed

### Deliverable
Hardware verification checklist signed off. No firmware work begins until Phase 0 is complete.

---

## Phase 1 — Proof of Concept Validation
**Goal:** Eliminate the two highest architectural risks before building anything else.  
**Exit criteria:** HaLow connects to HaLowLink 2 router AND transfers a test image. Camera mode switching works without deinit/reinit.

### 1A — HaLow Library Evaluation (HIGHEST PRIORITY)
- [ ] Identify available Arduino/PlatformIO library for Wio-WM6108
- [ ] Evaluate library maturity, last commit date, open issues
- [ ] Basic init: WM6108 responds on SPI bus
- [ ] Association: device connects to HaLow network, receives IP address
- [ ] HTTP GET: retrieve a small payload from a test server
- [ ] **Image transfer test:** POST a 400KB test JPEG to test server, measure throughput
- [ ] Document real-world throughput result
- [ ] **GO / NO-GO decision:** If throughput is inadequate, revisit communication strategy before proceeding

### 1B — Camera Mode Switching Without Deinit
- [ ] Initialize OV3660 via esp_camera
- [ ] Capture YUV422 frame at CIF resolution via register writes only (no deinit)
- [ ] Switch to JPEG mode via register writes only (no deinit)
- [ ] Capture JPEG frame at SXGA resolution
- [ ] Confirm no memory leak or driver instability across 20 consecutive switch cycles
- [ ] **GO / NO-GO decision:** If register-level switching is not stable, document alternative approach

### 1C — 2.4GHz WiFi Baseline (parallel to 1A)
- [ ] Connect to 2.4GHz network
- [ ] POST a 400KB test JPEG to test server
- [ ] Document throughput for comparison against HaLow result

### Deliverable
Phase 1 report: HaLow throughput result, camera switching stability result, GO/NO-GO on both. Architecture confirmed or revised before Phase 2 begins.

---

## Phase 2 — Core Drivers and Primitives
**Goal:** Clean, tested hardware abstraction layer for every peripheral.  
**Exit criteria:** Every peripheral reads correctly and independently testable.

### 2A — Project Structure Setup
- [ ] PlatformIO project initialized
- [ ] Custom partition table defined (NVS / OTA0 / OTA1 per spec Section 3)
- [ ] Directory structure established:
  ```
  /src
    main.cpp
    /drivers       (hardware abstraction — one file per peripheral)
    /managers      (logic layers — capture, storage, comms, power)
    /system        (boot, watchdog, NVS, health)
    /config        (pin definitions, constants, defaults)
  /test            (unit test stubs)
  ```
- [ ] All pin definitions and compile-time constants in config header
- [ ] Hardware variant compile flag defined (`BUILD_HALOW` / `BUILD_WIFI24`)

### 2B — NVS Manager
- [ ] NVS read/write wrapper with typed accessors
- [ ] Default value initialization on first boot
- [ ] All NVS keys defined as constants (no magic strings)
- [ ] Verified: NVS survives simulated OTA partition swap
- [ ] Verified: image_count survives reboot and power cycle

### 2C — I2C Bus Driver
- [ ] Wire.begin(5, 6) initialization
- [ ] 9-clock-pulse recovery routine implemented
- [ ] Bus health check function (probe both devices)
- [ ] Recovery integrated into boot sequence as Step 4
- [ ] Fault classification: HEALTHY / RECOVERED / DEVICE_FAULT / BUS_FAULT
- [ ] Tested: lockup simulation (SDA held low) → recovery succeeds

### 2D — BME280 Driver
- [ ] Initialize BME280 at 0x76
- [ ] Read temperature, humidity, pressure
- [ ] Apply calibration offsets (from NVS — default 0.0)
- [ ] Return both raw and corrected values
- [ ] Fault handling: returns null struct + fault flag if unresponsive

### 2E — ADS1115 Driver
- [ ] Initialize ADS1115 at 0x48, GAIN_TWO
- [ ] Read channel A0 (SBU voltage divider)
- [ ] Apply voltage divider formula → cell voltage → battery percentage
- [ ] Fault handling: returns BATTERY_UNKNOWN + fault flag if unresponsive

### 2F — LED Flash Driver
- [ ] LEDC PWM init on GPIO43, 20kHz+
- [ ] set_duty(uint16_t duty) function
- [ ] flash_off() function (explicit zero)
- [ ] NeoPixel init on GPIO21
- [ ] set_neopixel(uint8_t r, uint8_t g, uint8_t b) function
- [ ] neopixel_off() function
- [ ] save_neopixel_state() / restore_neopixel_state() for capture blackout

### 2G — Button Driver
- [ ] GPIO44 INPUT_PULLUP init
- [ ] Non-blocking press pattern detection
- [ ] Emits named events: BTN_SHORT_PRESS, BTN_DOUBLE_PRESS, BTN_HOLD_3S, BTN_HOLD_10S, BTN_POWER_ON_HOLD
- [ ] 50ms software debounce
- [ ] Tested: all press patterns correctly identified

### 2H — SD Card Driver
- [ ] SD.begin() initialization
- [ ] Directory creation: /images/pending, /images/uploaded, /images/corrupt
- [ ] File read / write / move / delete wrappers
- [ ] Free space calculation (bytes and percentage)
- [ ] Capacity threshold evaluation (WARNING 80% / CRITICAL 95%)
- [ ] Fault handling: missing card, corrupted filesystem, remount attempt

### Deliverable
All peripheral drivers independently verified. Simple test sketch cycles through all hardware and prints pass/fail to USB CDC serial.

---

## Phase 3 — Image Capture Pipeline
**Goal:** Complete, robust capture pipeline per spec Section 6.  
**Exit criteria:** 50 consecutive captures in varied lighting produce well-exposed JPEGs. Extreme conditions (darkness, full sun) handled correctly.

### 3A — Camera Initialization
- [ ] esp_camera_init() with correct DVP pin config for XIAO Sense
- [ ] Sensor detection and ID logging
- [ ] Clean deinit / error recovery if init fails
- [ ] Camera fault flag set on repeated init failure

### 3B — YUV Probe Capture
- [ ] Switch to CIF / YUV422 via register writes (no deinit)
- [ ] Center ROI sampling function:
  - Calculate center third of frame bounds
  - Sample Y channel only (even byte indices: 0, 2, 4...)
  - Return average luminance of ROI only
- [ ] Tested: correct Y values returned vs whole-frame average

### 3C — Iterative Convergence Loop
- [ ] Baseline duty: 10% of LEDC_MAX
- [ ] Target Y: configurable (default stored in NVS)
- [ ] Max iterations: configurable (default 5, stored in NVS)
- [ ] Per-iteration: fire at duty → capture probe → measure Y → calculate new duty
- [ ] Convergence condition: measured Y within ±15 of target
- [ ] Clamp: new_duty never exceeds LEDC_MAX
- [ ] Exit conditions: convergence achieved OR max iterations reached
- [ ] Records: final_duty, final_luminance, convergence_iters
- [ ] Tested: convergence in darkness (duty climbs to max)
- [ ] Tested: convergence in bright conditions (duty stays low)
- [ ] Tested: max iteration cap fires and does not loop infinitely

### 3D — Main JPEG Capture
- [ ] Switch to SXGA / JPEG via register writes (no deinit)
- [ ] Fire flash at converged duty
- [ ] Adaptive warmup frame discard (max 5 frames, stops when luminance stabilizes)
- [ ] AEC/AGC lock sequence:
  - Attempt 1 → verify → retry if unconfirmed → verify
  - Flag AEC_LOCK_FAILED if both attempts fail
  - Proceed regardless
- [ ] Capture final JPEG frame
- [ ] Flash ring → OFF immediately after capture
- [ ] NeoPixel restored to pre-capture state

### 3E — Pre/Post Capture LED Blackout
- [ ] save_neopixel_state() called before probe phase
- [ ] NeoPixel explicitly OFF before flash fires
- [ ] Flash ring verified at 0 before probe fires
- [ ] restore_neopixel_state() called after JPEG saved

### 3F — Lens Obstruction Detection
- [ ] Per-capture evaluation of all three conditions (duty maxed AND luminance low AND iters maxed)
- [ ] lens_anomaly_counter increment / reset logic
- [ ] lens_obstruction_suspected flag set at counter >= 2
- [ ] NVS updated with lens state after each capture
- [ ] Tested: 2 consecutive anomalous captures → flag set

### 3G — Capture Quality Metrics
- [ ] flash_duty_used, measured_luminance, convergence_iters recorded per capture
- [ ] Rolling circular buffer (last 5) maintained in NVS
- [ ] Average calculated across buffer
- [ ] Out-of-range flags evaluated against NVS thresholds

### Deliverable
Standalone capture test: 50 consecutive captures across lighting range. Review JPEGs for exposure quality. Verify all metrics recorded correctly.

---

## Phase 3B — BME Interval Logging System
**Goal:** Complete lightweight BME wake cycle and bme_log.dat storage per spec Section 22.  
**Exit criteria:** 24-hour continuous BME logging test produces correct records at 15-minute intervals. Both TYPE_INTERVAL and TYPE_IMAGE records correctly written and distinguished.  
**Can be developed in parallel with Phase 3 capture pipeline.**

### Tasks
- [ ] BmeLogRecord struct defined per spec Section 22.5
- [ ] log_sequence_id counter in NVS (independent of image_count)
- [ ] bme_log.dat append function with CRC16
- [ ] O(1) read by log_sequence_id
- [ ] TYPE_INTERVAL record written every minimal BME wake
- [ ] TYPE_IMAGE record written during full wake capture pipeline (image_id populated)
- [ ] Minimal BME wake cycle implemented:
  - Direct BME280 read (no I2C health check)
  - Single retry on failure
  - Fault record written on double failure
  - bme_wake_fail_count incremented in NVS
- [ ] Dual RTC wake time calculation:
  - next_bme_wake_timestamp maintained in NVS
  - Deep sleep set to min(next_capture, next_bme_wake, next_maintenance)
  - Wake reason correctly identified from NVS timestamps on boot
- [ ] Scenario handling implemented and tested:
  - S1: Normal BME-only wake → minimal cycle, reschedule
  - S2: BME + capture collision → capture absorbs, TYPE_IMAGE serves as BME record
  - S3: Relative interval timing — reschedule from last actual reading
  - S4: Single overdue BME at end of capture cycle → catch-up read, delay_ms populated, BME_DELAYED_CAPTURE_BUSY flag
  - S5: Minor RTC drift → handled naturally, no special case
  - S6: OTA + capture collision → capture first, OTA after
  - S7: Missed OTA window → report to server, server reschedules
  - S8: Multiple overdue intervals → one catch-up read, missed_intervals count populated, BME_INTERVALS_MISSED flag
- [ ] Safe mode phase-aware suspension:
  - BOOT_SENSORS crash → bme_logging_suspended = true
  - All other crashes → bme_logging_suspended = false
  - Flag stored in NVS, reported in health packet
- [ ] BME log batch upload added as Step 4 of upload session
- [ ] Server ACK marks all pending records as uploaded
- [ ] Retention: same threshold purge policy as images
- [ ] Health packet bme_logging fields added (per spec Section 22.10)
- [ ] bme_log_interval_minutes server-configurable via SET_SCHEDULE

### Deliverable
24-hour BME logging test: verify 96 TYPE_INTERVAL records written correctly. Verify TYPE_IMAGE records written with correct image_id during capture cycles. Verify batch upload delivers all records and server ACK clears pending flag.

---

## Phase 4 — Storage and Metadata System
**Goal:** Complete SD card storage system per spec Sections 7 and 8.  
**Exit criteria:** Images and metadata saved, retrieved, and managed correctly across simulated power-loss scenarios.

> **Gate:** Communication protocol decision (HTTP vs MQTT) should be made before this phase ends. Storage implementation (file-per-image vs circular indexed) follows from that decision.

### 4A — Image File Management
- [ ] Save JPEG to /images/pending/[MAC]_[%08d].jpg
- [ ] image_count incremented in NVS after each save
- [ ] JPEG header validation function (FF D8 FF check)
- [ ] Corrupt file scan on boot: scan /pending/, quarantine invalid files
- [ ] File move: /pending/ → /uploaded/ on server ACK
- [ ] File move: /pending/ → /corrupt/ on quarantine
- [ ] upload_attempt_count tracked in metadata per image

### 4B — Metadata System
- [ ] ImageMetadata struct defined per spec Section 8.2
- [ ] struct_version field — increment policy documented
- [ ] CRC16 calculation and verification
- [ ] appendMetadata() — write new record to metadata.dat
- [ ] readMetadata(image_id) — O(1) seek-based retrieval
- [ ] Partial write detection: CRC mismatch → mark corrupt
- [ ] Struct version check on boot → migration handler stub

### 4C — Storage Abstraction Layer
- [ ] storage_save_capture() — atomic: save JPEG + write metadata
- [ ] storage_mark_uploaded() — update metadata, move file
- [ ] storage_delete_uploaded() — remove from /uploaded/
- [ ] storage_get_next_pending() — return lowest unuploaded image_id
- [ ] storage_get_metadata() — retrieve by image_id
- [ ] storage_get_free_space_kb() — return available SD space

### 4D — Capacity Management
- [ ] SD free space checked at boot and after each upload session
- [ ] WARNING threshold (80%): purge oldest /uploaded/ files, flag in health packet
- [ ] CRITICAL threshold (95%): halt captures, flag in health packet
- [ ] Resume logic: captures restart when free space returns below WARNING threshold
- [ ] Tested: simulated full SD — correct threshold behavior fires

### 4E — Power Loss Recovery
- [ ] Simulate power loss mid-JPEG-write → corrupt file quarantined on next boot
- [ ] Simulate power loss mid-metadata-write → CRC detects partial record
- [ ] Confirm image_count in NVS is consistent with files on SD after recovery
- [ ] Confirm pending queue is correctly reconstructed after recovery

### Deliverable
Storage stress test: 200 capture/save cycles with simulated power interruptions. Verify zero data corruption goes undetected.

---

## Phase 5 — Connectivity and Upload Session
**Goal:** Complete radio management and upload session per spec Sections 9 and 10.  
**Exit criteria:** Full upload session completes reliably over both HaLow and 2.4GHz. Offline mode stores correctly and syncs on reconnection.

### 5A — Radio Manager
- [ ] HaLow init and association (WM6108 SPI driver)
- [ ] 2.4GHz WiFi init (onboard ESP32-S3)
- [ ] SPI probe for WM6108 presence at boot
- [ ] Primary / secondary radio selection from NVS preference
- [ ] Connection attempt sequence: 3 × 10sec per radio
- [ ] Fallback logic: primary fail → secondary attempt
- [ ] `operating_on_fallback` flag set when on secondary
- [ ] Every wake cycle retries primary first
- [ ] Offline mode entry when both radios fail
- [ ] halow_module_fault flag when SPI probe fails

### 5B — NTP Sync
- [ ] NTP request to pool.ntp.org on connection
- [ ] 10 second timeout
- [ ] Set internal RTC on success
- [ ] Store last_ntp_sync in NVS
- [ ] rtc_unsynced flag set on failure
- [ ] NTP always Step 0 of connected session (before health packet)

### 5C — Upload Session Implementation
- [ ] Step 1: Health packet serialized to JSON, POSTed (or published)
- [ ] Step 2: All pending metadata records serialized and transmitted
- [ ] Step 3: Pending image upload loop
  - Oldest image_id first
  - 45 second per-image timeout
  - Explicit server ACK required
  - On ACK: storage_mark_uploaded()
  - On timeout: increment attempt count, continue to next
  - After 5 failures on same image: flag in health packet
- [ ] Step 4: Receive and process server messages
- [ ] Step 5: Acknowledge server messages, close connection cleanly

### 5D — Server Message Handler
- [ ] SET_SCHEDULE → update NVS stage + interval
- [ ] SET_THRESHOLDS → update NVS quality/battery thresholds
- [ ] FORCE_OTA → set ota_battery_gate_open, store OTA params
- [ ] FORCE_NORMAL_MODE → reset crash_count, reboot
- [ ] LENS_OBSTRUCTION_CONFIRMED → set NVS flag, activate flash ring pattern
- [ ] LENS_OBSTRUCTION_CLEARED / RESOLVED → clear NVS flags
- [ ] SET_SAFE_MODE_INTERVAL → update safe mode sleep interval in NVS
- [ ] FORCE_UPLOAD → trigger immediate upload next wake

### 5E — Offline and Sync Modes
- [ ] Offline mode: capture → save → sleep (no comms attempted after timeout)
- [ ] Sync mode: reconnect → upload entire /pending/ queue before normal ops
- [ ] Tested: 24-hour offline simulation → full backlog uploads correctly on reconnect

### Deliverable
End-to-end upload test: device captures 10 images offline, reconnects, uploads all 10, receives server config update. Verify server receives correct JSON health packet, all images, all metadata.

---

## Phase 6 — Scheduling and Power Management
**Goal:** Complete deep sleep duty cycle per spec Sections 5 and 11.  
**Exit criteria:** Device wakes on schedule, captures, uploads, returns to deep sleep. Battery drain measured and within acceptable range.

### 6A — Deep Sleep Manager
- [ ] esp_deep_sleep_start() with RTC timer wakeup
- [ ] next_capture_timestamp calculated and stored in NVS before sleep
- [ ] next_maintenance_timestamp stored in NVS (OTA window)
- [ ] Wake reason read on boot (scheduled capture vs maintenance vs manual)
- [ ] RTC timer set to earlier of next_capture or next_maintenance

### 6B — Adaptive Schedule Execution
- [ ] Default schedule table hardcoded (Day 0-2: 4hr, Day 2-4: 2hr, Day 4-6: 1hr, Day 6+: 30min)
- [ ] current_stage and capture_interval_minutes read from NVS each wake
- [ ] Falls back to default table if no server stage update received
- [ ] Stage-appropriate interval used to calculate next_capture_timestamp

### 6C — Wake Cycle Timing Budget
- [ ] Phase-specific watchdog timeouts implemented (per spec Section 5.1)
- [ ] Current phase name written to NVS at start of each phase
- [ ] Watchdog reset between phases
- [ ] Total wake cycle timing measured and logged

### 6D — Battery-Aware Behavior
- [ ] Battery level checked at boot (after ADS1115 read)
- [ ] NORMAL / WARNING / CRITICAL state evaluated against NVS thresholds
- [ ] WARNING: all ops normal, auto-OTA blocked, server flagged
- [ ] CRITICAL: skip capture, connect, send alert, skip image upload, sleep immediately
- [ ] ADS1115 fault: continue all ops, block auto-OTA, flag server

### Deliverable
72-hour continuous operation test: device captures on adaptive schedule, deep sleeps between cycles, wakes correctly. Measure actual battery drain vs estimate. Confirm deep sleep current draw is nominal (~20µA).

---

## Phase 7 — Provisioning and OTA
**Goal:** Complete BLE provisioning and OTA firmware update system per spec Sections 12 and 13.  
**Exit criteria:** Device provisionable via nRF Connect. OTA update installs and commits. Rollback fires on deliberately broken firmware.

### 7A — BLE Provisioning
- [ ] BLE advertising: device name PDM-[last 4 MAC digits]
- [ ] GATT service with all provisioning characteristics (per spec Section 12.3)
- [ ] Credential write → stored in NVS
- [ ] Provision Complete write → reboot into normal operation
- [ ] Provisioning mode entry: factory reset or unprovisioned boot
- [ ] NeoPixel: PURPLE fast pulse during provisioning
- [ ] Tested: full provision cycle via nRF Connect

### 7B — Calibration BLE Extension
- [ ] Live sensor read characteristics (LIVE_TEMP_RAW etc.)
- [ ] Offset write characteristics → stored in NVS
- [ ] Certificate and serial write characteristics
- [ ] Tested: write offsets via BLE → corrected values change correctly in health packet

### 7C — OTA Manager
- [ ] OTA announcement received and stored in NVS (Step 4 of upload session)
- [ ] Maintenance window wake: RTC alarm fires at scheduled time
- [ ] Battery gate: abort if battery < 20% AND no FORCE flag
- [ ] Firmware download to OTA slot 1 in chunks over HTTPS
- [ ] SHA256 hash validation before boot
- [ ] esp_ota_set_boot_partition() → reboot
- [ ] New firmware: esp_ota_mark_app_valid_cancel_rollback() on first successful session
- [ ] OTA result packet sent: SUCCESS or ROLLED_BACK
- [ ] ota_battery_gate_open cleared after OTA attempt

### 7D — Factory Reset
- [ ] BTN_POWER_ON_HOLD → clear all NVS → enter provisioning mode
- [ ] BTN_HOLD_10S → same behavior (powered reset)
- [ ] Flash ring countdown pattern (10% → 100% over 10 seconds)
- [ ] Must hold full duration to confirm — release early cancels
- [ ] Tested: factory reset → device enters provisioning mode → reprovision succeeds

### Deliverable
OTA test: push deliberate bad firmware → rollback fires → old firmware reconnects → reports ROLLED_BACK. Push good firmware → commits → reports SUCCESS.

---

## Phase 8 — Error Handling and Fault Recovery
**Goal:** All edge cases and fault behaviors per spec Sections 15 and 16 implemented and tested.  
**Exit criteria:** Every defined fault condition produces the correct defined behavior without crashing or hanging.

### 8A — Reset Reason Handler
- [ ] esp_reset_reason() read on every boot
- [ ] FAULT reasons: crash_count incremented, pending_reset_report set
- [ ] CLEAN reasons: crash_count unchanged
- [ ] Reset reason and phase stored in NVS on FAULT

### 8B — Crash Loop Detection and Safe Mode
- [ ] crash_count >= 3 → SAFE_MODE entry
- [ ] Safe mode: disable camera, flash, SD images, sensors, auto-OTA
- [ ] Safe mode: connect + health packet + button only
- [ ] Safe mode sleep: 30min default, server-overridable
- [ ] Flash ring slow pulse at 15% while awake in safe mode
- [ ] Safe mode exit: FORCE_NORMAL_MODE / successful OTA / factory reset
- [ ] Tested: simulate 3 consecutive WDT resets → safe mode entered

### 8C — I2C Fault Handling
- [ ] I2C health check + recovery in boot Step 4
- [ ] 9-clock-pulse recovery implemented and tested
- [ ] Fault classification reported in health packet
- [ ] Tested: lockup simulation → recovery → correct operation resumes

### 8D — Sensor Fault Handling
- [ ] BME280 unresponsive → null values + bme280_fault flag
- [ ] ADS1115 unresponsive → BATTERY_UNKNOWN + ads1115_fault flag + OTA block
- [ ] Neither sensor blocks capture or upload

### 8E — SD Fault Handling
- [ ] SD missing → no capture, connect, health packet flag
- [ ] SD corrupted → remount attempt → if fails, treat as missing
- [ ] Corrupt JPEG → quarantine → metadata fault record
- [ ] Partial metadata write → CRC mismatch → flag corrupt

### 8F — Camera and Flash Fault Handling
- [ ] Camera init fail → failed capture record → skip to comms
- [ ] Flash not responding → retry at 50% → capture anyway at max → FLASH_FAULT flag
- [ ] AEC lock fail → retry → proceed with flag if still failing

### 8G — Connectivity Fault Handling
- [ ] Both radios fail → offline mode
- [ ] Server unreachable → retry once → offline mode
- [ ] Upload timeout → mark attempt, continue to next image

### 8H — Edge Cases
- [ ] Battery critically low behavior
- [ ] OTA deferred low battery → health packet flag
- [ ] Image counter rollover detection
- [ ] Lens obstruction detection and flash ring pattern

### Deliverable
Fault injection test suite: simulate every defined fault condition. Verify correct behavior for each. No fault causes a hang, crash loop, or silent failure.

---

## Phase 9 — Health Packet and Telemetry
**Goal:** Complete health packet implementation per spec Section 19.  
**Exit criteria:** Health packet contains all defined fields. Server receives parseable JSON every session.

### 9A — Health Packet Builder
- [ ] All fields defined in spec Section 19 implemented
- [ ] JSON serialization (ArduinoJson or equivalent)
- [ ] Calibration fields included (raw + corrected sensor values)
- [ ] Reset reason and fault flags populated from NVS
- [ ] Rolling quality metric averages calculated from NVS circular buffer
- [ ] cal_expiry_warning set if within 30 days of expiry
- [ ] Packet size measured — verify within reasonable bounds

### 9B — Telemetry Validation
- [ ] Server receives and parses health packet correctly
- [ ] All fields present and correctly typed
- [ ] Fault flags correctly set/cleared across scenarios
- [ ] Calibration fields correctly populated for calibrated and uncalibrated devices

### Deliverable
Health packet review with backend teammate. Confirm all fields parseable, all types correct, no missing fields.

---

## Phase 10 — Integration and System Test
**Goal:** Full system operating end-to-end as a complete device.  
**Exit criteria:** Device operates continuously for 7 days without intervention, producing correct captures, uploading reliably, recovering from injected faults.

### 10A — Full Integration Test
- [ ] Complete boot sequence executes correctly
- [ ] Adaptive schedule fires at correct intervals
- [ ] All captures well-exposed across greenhouse lighting conditions
- [ ] All health packets received by server every session
- [ ] All images uploaded and confirmed by server
- [ ] SD card management thresholds fire correctly
- [ ] Deep sleep current draw confirmed nominal

### 10B — Fault Injection Integration
- [ ] Pull SD card mid-cycle → recovery correct
- [ ] Kill HaLow connection → fallback fires → online when restored
- [ ] Cut power mid-capture → clean recovery on reboot
- [ ] Cut power mid-upload → no data loss, resumes correctly
- [ ] Trigger watchdog manually → crash count increments → safe mode at 3

### 10C — OTA Integration
- [ ] Push OTA update during normal operation
- [ ] Maintenance window fires correctly
- [ ] Update installs and commits
- [ ] All NVS state survives OTA
- [ ] image_count survives OTA
- [ ] Rollback test: deliberately broken firmware rolls back cleanly

### 10D — Provisioning Integration
- [ ] Factory reset → provision via BLE → connect → normal operation
- [ ] Reprovision with different credentials → connects to new network
- [ ] Calibration offsets entered via BLE → reflected in health packet and metadata

### 10E — Performance Baseline
- [ ] Measure average wake cycle duration
- [ ] Measure average upload session duration per image
- [ ] Measure battery drain per 24 hours at each capture interval
- [ ] Project runtime to empty at each interval vs V50 13,400mAh capacity
- [ ] Document results for operational planning

### Deliverable
7-day continuous operation log. Pass/fail report for all integration and fault injection tests. Performance baseline documented.

---

## Phase 11 — Field Validation
**Goal:** Validate firmware in real greenhouse conditions with real petri dishes.  
**Exit criteria:** 3 devices operating correctly in field conditions for 14 days. Server receiving correct data. No critical faults.

### 11A — Test Deployment Setup
- [ ] 3 devices provisioned and deployed
  - Device 1: HaLow configuration
  - Device 2: 2.4GHz WiFi configuration
  - Device 3: HaLow with 2.4GHz fallback credentials
- [ ] HaLowLink 2 router installed and connected to site internet
- [ ] Server receiving data from all 3 devices
- [ ] Baseline health packets reviewed — all devices nominal

### 11B — Field Monitoring (14 days)
- [ ] Daily review of health packets from all 3 devices
- [ ] Image quality review — exposure, focus, lens cleanliness
- [ ] Battery drain tracking vs projected
- [ ] Connectivity uptime tracking
- [ ] Any fault events reviewed and root-caused

### 11C — Field Fault Scenarios
- [ ] Simulate battery swap: confirm device recovers, NTP resyncs, NVS intact
- [ ] Simulate petri dish swap: confirm server detects new plate correctly
- [ ] Simulate HaLow router offline for 4 hours: confirm offline mode, sync on restore
- [ ] Push OTA update to all 3 devices remotely: confirm all update cleanly

### 11D — Lens Cleaning Protocol Validation
- [ ] Verify lens cleaning at each dish swap prevents obstruction flags
- [ ] Document any obstruction events and root cause

### Deliverable
Field validation report: 14-day operation log, fault events, image quality assessment, battery performance, connectivity uptime. Sign-off before production deployment.

---

## Development Dependencies

```
Phase 0  ──► Phase 1  ──► Phase 2
                               │
                    ┌──────────┼──────────┐
                    ▼          ▼          ▼
                 Phase 3    Phase 4    Phase 5
                 (Capture)  (Storage)  (Comms)
                    │          │          │
                    └──────────┼──────────┘
                               ▼
                            Phase 6
                          (Scheduling)
                               │
                    ┌──────────┼──────────┐
                    ▼          ▼          ▼
                 Phase 7    Phase 8    Phase 9
                 (Prov/OTA) (Faults)  (Telemetry)
                    │          │          │
                    └──────────┼──────────┘
                               ▼
                           Phase 10
                         (Integration)
                               │
                               ▼
                           Phase 11
                        (Field Validation)
```

Phases 3, 4, and 5 can be developed in parallel after Phase 2 is complete.  
Phases 7, 8, and 9 can be developed in parallel after Phase 6 is complete.

---

## Protocol Decision Gate

The communication protocol decision (HTTP/HTTPS vs MQTT) must be made before Phase 5 implementation begins. This decision also determines the storage implementation choice in Phase 4:

| Protocol | Storage Implementation |
|---|---|
| HTTP/HTTPS | File-per-image (Option 2) — discrete transactions, self-contained |
| MQTT | Circular indexed records (Option 3) — streaming, batch-friendly |

**Action:** Schedule protocol decision meeting with backend teammate before Phase 4 ends.

---

*End of V2 Firmware Development Roadmap — Version 1.0*  
*Reference: V2 Firmware Specification v1.0*
