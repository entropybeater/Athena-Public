/*
 * PDM V2 — Phase 0 I2C Scanner
 * 
 * WHY: Confirms I2C addresses of BME280 and ADS1115 before any
 *      drivers are written. Results determine Phase 2 driver config.
 *
 * EXPECTED RESULTS:
 *   BME280  → 0x76 (SDO→GND) or 0x77 (SDO→VCC, spec deviation)
 *   ADS1115 → 0x48 (ADDR→GND)
 *
 * Pin assignments per spec §2.3:
 *   SDA → GPIO5 (XIAO D4)
 *   SCL → GPIO6 (XIAO D5)
 */

#include <Wire.h>

void setup() {
  Serial.begin(115200);
  delay(2000); // Give serial monitor time to connect

  // Initialize I2C on spec-defined pins
  Wire.begin(5, 6); // SDA=GPIO5, SCL=GPIO6

  Serial.println("==============================================");
  Serial.println(" PDM V2 — Phase 0 I2C Address Scanner");
  Serial.println("==============================================");
  Serial.println("Scanning I2C bus (GPIO5=SDA, GPIO6=SCL)...");
  Serial.println();

  uint8_t found = 0;

  for (uint8_t addr = 1; addr < 127; addr++) {
    Wire.beginTransmission(addr);
    uint8_t error = Wire.endTransmission();

    if (error == 0) {
      Serial.print("  [FOUND] Device at 0x");
      if (addr < 16) Serial.print("0");
      Serial.print(addr, HEX);

      // Identify known devices
      if (addr == 0x76) Serial.print("  → BME280 (SDO→GND) ✓ Matches spec");
      if (addr == 0x77) Serial.print("  → BME280 (SDO→VCC) ⚠ Spec deviation — driver needs update");
      if (addr == 0x48) Serial.print("  → ADS1115 (ADDR→GND) ✓ Matches spec");
      if (addr == 0x49) Serial.print("  → ADS1115 (ADDR→VCC) ⚠ Spec deviation");
      if (addr == 0x4A) Serial.print("  → ADS1115 (ADDR→SDA) ⚠ Spec deviation");
      if (addr == 0x4B) Serial.print("  → ADS1115 (ADDR→SCL) ⚠ Spec deviation");

      Serial.println();
      found++;
    }
  }

  Serial.println();
  Serial.print("Scan complete. ");
  Serial.print(found);
  Serial.println(" device(s) found.");
  Serial.println();

  // Summary verdict
  Serial.println("--- PHASE 0 CHECK 8/10 VERDICT ---");

  // Re-probe specifically for expected devices
  bool bme_76 = probeAddr(0x76);
  bool bme_77 = probeAddr(0x77);
  bool ads_48 = probeAddr(0x48);

  if (bme_76)       Serial.println("  Check 8:  PASS — BME280 at 0x76 (spec target)");
  else if (bme_77)  Serial.println("  Check 8:  PASS (DEVIATION) — BME280 at 0x77, update driver config");
  else              Serial.println("  Check 8:  FAIL — BME280 not found. Check wiring: SDA/SCL/GND/3V3");

  if (ads_48)       Serial.println("  Check 10: PASS — ADS1115 at 0x48 (spec target)");
  else              Serial.println("  Check 10: FAIL — ADS1115 not found. Confirm ADDR pin → GND");

  Serial.println("==================================");
}

bool probeAddr(uint8_t addr) {
  Wire.beginTransmission(addr);
  return (Wire.endTransmission() == 0);
}

void loop() {
  // Nothing — single-shot scan on boot
}
