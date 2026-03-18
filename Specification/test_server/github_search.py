import requests

# Found it: MorseMicro/mm-iot-esp32 (26 stars, updated 2026-03-13)
# This is the official ESP-IDF SDK for the WM6108 chip
# Let's inspect its structure and README to understand what it provides

print("=== MorseMicro/mm-iot-esp32 contents ===")
r = requests.get(
    "https://api.github.com/repos/MorseMicro/mm-iot-esp32/contents",
    headers={"Accept": "application/vnd.github.v3+json"},
    timeout=15
)
if r.status_code == 200:
    for f in r.json():
        print(f"  {f['type']:4s}  {f['name']}")
else:
    print(f"  Error: {r.status_code}")

print("\n=== mm-iot-esp32 README ===")
r2 = requests.get(
    "https://raw.githubusercontent.com/MorseMicro/mm-iot-esp32/main/README.md",
    timeout=15
)
if r2.status_code == 200:
    print(r2.text[:4000])
else:
    # try master branch
    r2b = requests.get(
        "https://raw.githubusercontent.com/MorseMicro/mm-iot-esp32/master/README.md",
        timeout=15
    )
    if r2b.status_code == 200:
        print(r2b.text[:4000])
    else:
        print(f"  Not found ({r2.status_code} / {r2b.status_code})")

print("\n=== mm-iot-esp32 releases ===")
r3 = requests.get(
    "https://api.github.com/repos/MorseMicro/mm-iot-esp32/releases?per_page=5",
    headers={"Accept": "application/vnd.github.v3+json"},
    timeout=15
)
if r3.status_code == 200:
    releases = r3.json()
    if not releases:
        print("  No releases found.")
    for rel in releases:
        print(f"  {rel['tag_name']}  Published: {rel['published_at'][:10]}")
        print(f"    {rel.get('name','')}")
else:
    print(f"  Error: {r3.status_code}")

# Also check HudsonReynolds2 fork which claims to have working iperf example
print("\n=== HudsonReynolds2/mm-iot-esp32 README (working fork) ===")
r4 = requests.get(
    "https://raw.githubusercontent.com/HudsonReynolds2/mm-iot-esp32/main/README.md",
    timeout=15
)
if r4.status_code == 200:
    print(r4.text[:2000])
else:
    print(f"  Not found ({r4.status_code})")
