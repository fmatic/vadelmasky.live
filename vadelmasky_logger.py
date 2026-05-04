#!/usr/bin/env python3

import json
import math
import subprocess
from datetime import datetime
from pathlib import Path

# ===== CONFIG =====

POSSIBLE_PATHS = [
    "/run/adsb-feeder-ultrafeeder/readsb/aircraft.json",
    "/run/readsb/aircraft.json",
    "/run/tar1090/aircraft.json",
]

HOME_LAT = 62.24
HOME_LON = 25.75

BASE = Path.home() / "vadelmasky"
SITE = BASE / "site"
DATA = SITE / "data"

TODAY = datetime.now().strftime("%Y-%m-%d")

DAILY_JSON = DATA / f"{TODAY}.json"
INDEX_JSON = SITE / "today.json"
INDEX_HTML = SITE / "index.html"

# ===== FIND SOURCE =====

SOURCE = None
for p in POSSIBLE_PATHS:
    if Path(p).exists():
        SOURCE = Path(p)
        break

if SOURCE is None:
    raise RuntimeError("aircraft.json not found")

# ===== HELPERS =====

def distance_km(lat1, lon1, lat2, lon2):
    r = 6371
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return round(r * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a)), 1)

def load_seen():
    if DAILY_JSON.exists():
        return json.loads(DAILY_JSON.read_text()).get("aircraft", {})
    return {}

def save(seen):
    aircraft = list(seen.values())

    summary = {
        "date": TODAY,
        "updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "aircraft_seen": len(aircraft),
        "with_position": sum(1 for a in aircraft if "distance_km" in a),
        "max_range_km": max([a.get("max_distance_km", 0) for a in aircraft] or [0]),
        "top_altitude_ft": max([a.get("max_altitude_ft", 0) for a in aircraft] or [0]),
    }

    payload = {
        "summary": summary,
        "aircraft": seen,
    }

    DATA.mkdir(parents=True, exist_ok=True)

    DAILY_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    INDEX_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False))

    latest = sorted(aircraft, key=lambda x: x.get("last_seen", ""), reverse=True)[:40]

    rows = "\n".join(
        f"<tr><td>{a.get('last_seen','')}</td>"
        f"<td>{a.get('flight','')}</td>"
        f"<td>{a.get('hex','')}</td>"
        f"<td>{a.get('alt_baro','')}</td>"
        f"<td>{a.get('distance_km','')}</td></tr>"
        for a in latest
    )

    INDEX_HTML.write_text(f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>VadelmaSky.live</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body {{ font-family: system-ui, sans-serif; max-width: 1000px; margin: 2rem auto; padding: 0 1rem; background:#101214; color:#eee; }}
h1 {{ margin-bottom: .2rem; }}
.card {{ background:#181b1f; border:1px solid #30343a; border-radius:12px; padding:1rem; margin:1rem 0; }}
.stats {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); gap:.75rem; }}
.stat {{ background:#20242a; padding:.8rem; border-radius:10px; }}
.stat b {{ display:block; font-size:1.6rem; }}
table {{ width:100%; border-collapse:collapse; }}
td, th {{ padding:.55rem; border-bottom:1px solid #30343a; text-align:left; }}
small {{ color:#aaa; }}
</style>
</head>
<body>

<h1>VadelmaSky.live</h1>
<small>Live aviation log from Jyväskylä — updated {summary["updated"]}</small>

<div class="card stats">
  <div class="stat"><b>{summary["aircraft_seen"]}</b>Aircraft today</div>
  <div class="stat"><b>{summary["with_position"]}</b>With position</div>
  <div class="stat"><b>{summary["max_range_km"]} km</b>Max range</div>
  <div class="stat"><b>{summary["top_altitude_ft"]} ft</b>Top altitude</div>
</div>

<div class="card">
<h2>Latest aircraft</h2>
<table>
<tr><th>Last seen</th><th>Flight</th><th>ICAO</th><th>Altitude</th><th>Distance km</th></tr>
{rows}
</table>
</div>

</body>
</html>
""")

def git_push():
    subprocess.run(["git", "add", "site"], cwd=BASE)
    subprocess.run(["git", "commit", "-m", f"Update {datetime.now().strftime('%Y-%m-%d %H:%M')}"], cwd=BASE)
    subprocess.run(["git", "push"], cwd=BASE)

# ===== MAIN =====

def main():
    seen = load_seen()
    data = json.loads(SOURCE.read_text())

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for ac in data.get("aircraft", []):
        hexid = ac.get("hex")
        if not hexid:
            continue

        item = seen.get(hexid, {
            "hex": hexid,
            "first_seen": now,
        })

        item["last_seen"] = now

        flight = (ac.get("flight") or "").strip()
        if flight:
            item["flight"] = flight

        if "alt_baro" in ac:
            item["alt_baro"] = ac["alt_baro"]
            if isinstance(ac["alt_baro"], int):
                item["max_altitude_ft"] = max(item.get("max_altitude_ft", 0), ac["alt_baro"])

        if "lat" in ac and "lon" in ac:
            dist = distance_km(HOME_LAT, HOME_LON, ac["lat"], ac["lon"])
            item["distance_km"] = dist
            item["max_distance_km"] = max(item.get("max_distance_km", 0), dist)

        seen[hexid] = item

    save(seen)
    git_push()

if __name__ == "__main__":
    main()
