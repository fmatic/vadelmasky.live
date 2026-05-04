#!/usr/bin/env python3

import json
import os
from datetime import datetime
from pathlib import Path

BASE = Path("/home/dietpi/vadelmasky")
SOURCE = Path("/run/adsb-feeder-ultrafeeder/readsb/aircraft.json")

DOCS = BASE / "docs"
DATA = DOCS / "data"
TODAY = DOCS / "today.json"
INDEX = DOCS / "index.html"

DOCS.mkdir(exist_ok=True)
DATA.mkdir(exist_ok=True)

# --- Lue nykyinen data ---
if TODAY.exists():
    with open(TODAY) as f:
        store = json.load(f)
else:
    store = {"aircraft": {}}

# --- Lue aircraft.json ---
if not SOURCE.exists():
    print("No aircraft.json")
    exit()

with open(SOURCE) as f:
    data = json.load(f)

count_now = 0

for a in data.get("aircraft", []):
    hex_id = a.get("hex")
    if not hex_id:
        continue

    count_now += 1

    store["aircraft"][hex_id] = {
        "flight": a.get("flight", "").strip(),
        "lat": a.get("lat"),
        "lon": a.get("lon"),
        "alt": a.get("alt_baro"),
        "last_seen": datetime.utcnow().isoformat()
    }

# --- Summary ---
store["summary"] = {
    "total_unique_aircraft": len(store["aircraft"]),
    "last_seen_live": count_now,
    "updated": datetime.utcnow().isoformat()
}

# --- Tallenna JSON ---
with open(TODAY, "w") as f:
    json.dump(store, f, indent=2)

# --- HTML ---
html = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>VadelmaSky</title>
<style>
body {{ background:#111; color:#eee; font-family:Arial; }}
h1 {{ color:#0f0; }}
</style>
</head>
<body>
<h1>VadelmaSky ✈️</h1>
<p>Unique aircraft today: {store["summary"]["total_unique_aircraft"]}</p>
<p>Aircraft right now: {store["summary"]["last_seen_live"]}</p>
<p>Last update: {store["summary"]["updated"]}</p>
</body>
</html>
"""

with open(INDEX, "w") as f:
    f.write(html)

# --- GIT ---
os.chdir(BASE)

os.system("git add docs")

# commit vain jos muutoksia
if os.system("git diff --cached --quiet") != 0:
    msg = f"Update flights {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    os.system(f'git commit -m "{msg}"')
    os.system("git push")
else:
    print("No changes, skipping commit")
