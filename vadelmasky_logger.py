#!/usr/bin/env python3

import csv
import gzip
import html
import json
from datetime import datetime
from pathlib import Path

BASE = Path("/home/dietpi/vadelmasky")
SOURCE = Path("/run/adsb-feeder-ultrafeeder/readsb/aircraft.json")
AIRCRAFT_DB = Path("/usr/local/share/tar1090/aircraft.csv.gz")

DOCS = BASE / "docs"
DATA = DOCS / "data"
HISTORY = DOCS / "history"
MESSAGES = BASE / "messages"

TODAY_FILE = DOCS / "today.json"
INDEX = DOCS / "index.html"
HISTORY_INDEX = HISTORY / "index.html"
HISTORY_DAY = HISTORY / "day.html"
HISTORY_MANIFEST = HISTORY / "history.json"
ACARS_FILE = MESSAGES / "acars_latest.json"

HOME_LAT = 62.24
HOME_LON = 25.75
STALE_SECONDS = 7200

DOCS.mkdir(exist_ok=True)
DATA.mkdir(exist_ok=True)
HISTORY.mkdir(exist_ok=True)
MESSAGES.mkdir(exist_ok=True)


def esc(value):
    return html.escape(str(value)) if value is not None else "-"


def fmt_time(value):
    if not value:
        return "-"
    try:
        return datetime.fromisoformat(value).strftime("%d.%m.%Y %H:%M") + " UTC"
    except Exception:
        return "-"


def load_aircraft_db():
    db = {}

    if not AIRCRAFT_DB.exists():
        return db

    try:
        with gzip.open(AIRCRAFT_DB, "rt", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)

            for row in reader:
                hex_id = (
                    row.get("icao24")
                    or row.get("icao")
                    or row.get("hex")
                    or row.get("mode_s")
                    or ""
                ).strip().lower()

                if not hex_id:
                    continue

                db[hex_id] = {
                    "reg": (
                        row.get("registration")
                        or row.get("reg")
                        or row.get("r")
                        or ""
                    ).strip(),
                    "type": (
                        row.get("typecode")
                        or row.get("type")
                        or row.get("t")
                        or ""
                    ).strip(),
                }

    except Exception as e:
        print(f"Aircraft DB load failed: {e}")

    return db


def load_store():
    today_utc = datetime.utcnow().strftime("%Y-%m-%d")

    if TODAY_FILE.exists():
        try:
            data = json.loads(TODAY_FILE.read_text(encoding="utf-8"))
            updated = data.get("summary", {}).get("updated", "")

            if updated.startswith(today_utc):
                if "aircraft" not in data:
                    data["aircraft"] = {}
                return data

            print("New UTC day detected -> resetting today store")

        except Exception as e:
            print(f"Failed loading today.json: {e}")

    return {"aircraft": {}, "summary": {}}


def save_json(path, payload):
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )


def daily_stats(payload):
    aircraft = payload.get("aircraft", {})
    vals = list(aircraft.values())

    with_position = sum(
        1 for a in vals
        if a.get("lat") is not None and a.get("lon") is not None
    )

    highest_alt = max(
        [a.get("alt") or 0 for a in vals if isinstance(a.get("alt"), int)] or [0]
    )

    max_speed = max(
        [a.get("speed") or 0 for a in vals if isinstance(a.get("speed"), (int, float))] or [0]
    )

    return {
        "unique": len(aircraft),
        "with_position": with_position,
        "highest_alt": highest_alt,
        "max_speed": round(max_speed, 1),
    }


def live_aircraft_items(store):
    now = datetime.utcnow()
    items = []

    for hex_id, aircraft in store.get("aircraft", {}).items():
        try:
            last_seen = datetime.fromisoformat(aircraft.get("last_seen", ""))
            age = (now - last_seen).total_seconds()

            if age <= STALE_SECONDS:
                items.append((hex_id, aircraft))
        except Exception:
            continue

    return sorted(
        items,
        key=lambda x: x[1].get("last_seen", ""),
        reverse=True
    )


def load_messages(path, label):
    if not path.exists():
        return []

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        items = data if isinstance(data, list) else data.get("messages", [])
        for item in items:
            item["source"] = label
        return items[-12:]
    except Exception:
        return []


def alt_class(alt):
    if not isinstance(alt, int):
        return "unknown"
    if alt < 10000:
        return "low"
    if alt < 25000:
        return "mid"
    return "high"


def page_template(title, body):
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{esc(title)}</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="stylesheet" href="https://unpkg.com/maplibre-gl@6.6.0/dist/maplibre-gl.css">
<style>
body {{
    margin: 0;
    font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    background: #0f1418;
    color: #e8edf2;
}}
header {{
    padding: 2rem;
    background: linear-gradient(135deg, #07110c, #132019);
    border-bottom: 1px solid #243225;
}}
h1 {{
    margin: 0;
    font-size: 2.4rem;
    color: #41ff41;
}}
a {{
    color: #7dd3fc;
    text-decoration: none;
}}
a:hover {{
    text-decoration: underline;
}}
.subtitle {{
    color: #a8b3bd;
    margin-top: .4rem;
}}
nav {{
    margin-top: 1rem;
}}
nav a {{
    margin-right: 1rem;
}}
main {{
    max-width: 1150px;
    margin: 0 auto;
    padding: 1.5rem;
}}
.cards {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
    gap: 1rem;
    margin-bottom: 1.5rem;
}}
.card {{
    background: #171d22;
    border: 1px solid #2b363d;
    border-radius: 14px;
    padding: 1rem;
}}
.card .value {{
    font-size: 2rem;
    font-weight: 700;
    color: #7dd3fc;
}}
.card .label {{
    color: #a8b3bd;
    margin-top: .25rem;
}}
section {{
    background: #171d22;
    border: 1px solid #2b363d;
    border-radius: 14px;
    padding: 1rem;
    overflow-x: auto;
    margin-bottom: 1.5rem;
}}
#map {{
    height: 520px;
    width: 100%;
    border-radius: 14px;
    border: 1px solid #2b363d;
    margin-top: 1rem;
}}
table {{
    width: 100%;
    border-collapse: collapse;
}}
th, td {{
    text-align: left;
    padding: .65rem;
    border-bottom: 1px solid #2b363d;
    white-space: nowrap;
}}
th {{
    color: #93c5fd;
    font-weight: 600;
}}
tr:hover {{
    background: #1f2933;
}}
.note {{
    color: #a8b3bd;
    font-size: .95rem;
}}

.aircraft-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 1rem;
}}
.aircraft-card {{
    background: #101820;
    border: 1px solid #2b363d;
    border-radius: 14px;
    padding: 1rem;
}}
.aircraft-top {{
    display: flex;
    justify-content: space-between;
    gap: 1rem;
}}
.flight {{
    font-size: 1.25rem;
    font-weight: 800;
}}
.meta {{
    color: #7b8794;
    font-size: .9rem;
}}
.alt-badge {{
    padding: .25rem .65rem;
    border-radius: 999px;
    font-weight: 800;
    font-size: .85rem;
    white-space: nowrap;
}}
.alt-badge.low {{ background: rgba(65,255,65,.15); color: #41ff41; }}
.alt-badge.mid {{ background: rgba(250,204,21,.15); color: #facc15; }}
.alt-badge.high {{ background: rgba(248,113,113,.15); color: #f87171; }}
.alt-badge.unknown {{ background: rgba(156,163,175,.15); color: #9ca3af; }}

.aircraft-body {{
    display: flex;
    gap: 1rem;
    margin-top: 1rem;
}}
.aircraft-silhouette {{
    width: 72px;
    height: 72px;
    border-radius: 12px;
    background: #17212b;
    display: grid;
    place-items: center;
    font-size: 2rem;
    color: #41ff41;
}}
.aircraft-data {{
    flex: 1;
    display: grid;
    gap: .35rem;
}}
.aircraft-data div {{
    display: flex;
    justify-content: space-between;
    border-bottom: 1px solid #26313a;
    padding-bottom: .25rem;
}}
.aircraft-data span {{
    color: #7b8794;
}}
.aircraft-data b {{
    text-align: right;
}}
.photo-link {{
    display: inline-block;
    margin-top: 1rem;
    font-weight: 700;
}}

.acars-grid {{
    display: grid;
    gap: .75rem;
}}
.acars-card {{
    background: #101820;
    border: 1px solid #2b363d;
    border-radius: 12px;
    padding: .9rem;
}}
.acars-head {{
    display: flex;
    justify-content: space-between;
    gap: 1rem;
}}
.acars-flight {{
    font-size: 1.1rem;
    font-weight: 800;
}}
.acars-meta {{
    color: #7b8794;
    font-size: .9rem;
}}
.acars-text {{
    margin-top: .75rem;
    padding: .75rem;
    background: #0b1117;
    border-radius: 10px;
    white-space: pre-wrap;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}}

footer {{
    color: #6b7280;
    padding: 2rem;
    text-align: center;
    font-size: .9rem;
}}
</style>
</head>
<body>
<header>
    <h1>VadelmaSky ✈️</h1>
    <div class="subtitle">Local ADS-B aviation log from Jyväskylä, Finland</div>
    <nav>
        <a href="/">Live</a>
        <a href="/history/">History</a>
        <a href="/today.json">Today JSON</a>
    </nav>
</header>

<main>
{body}
</main>

<footer>
    VadelmaSky.live · Powered by local SDR receivers · Data updates automatically
</footer>
</body>
</html>
"""


def build_aircraft_cards(aircraft_items, limit=50):
    cards = ""
    items = aircraft_items[:limit] if limit else aircraft_items

    for hex_id, a in items:
        flight_raw = a.get("flight") or "Unknown"
        flight = esc(flight_raw)

        icao_raw = hex_id.upper()
        icao = esc(icao_raw)

        reg_raw = a.get("reg")
        aircraft_type_raw = a.get("type")

        reg = esc(reg_raw or "-")
        aircraft_type = esc(aircraft_type_raw or "-")

        alt = a.get("alt")
        speed = esc(a.get("speed") or "-")
        track = esc(a.get("track") or "-")
        lat = a.get("lat")
        lon = a.get("lon")
        last_seen = esc(fmt_time(a.get("last_seen")))

        alt_text = f"{alt} ft" if alt else "-"
        pos_text = (
            f"{lat:.4f}, {lon:.4f}"
            if isinstance(lat, (int, float)) and isinstance(lon, (int, float))
            else "No position"
        )

        if reg_raw:
            photo_url = f"https://www.jetphotos.com/photo/keyword/{esc(reg_raw)}"
            photo_label = "Search aircraft photo"
        else:
            photo_url = f"https://globe.adsbexchange.com/?icao={icao_raw.lower()}"
            photo_label = "View aircraft info"

        cards += f"""
        <article class="aircraft-card">
            <div class="aircraft-top">
                <div>
                    <div class="flight">{flight}</div>
                    <div class="meta">ICAO {icao} · REG {reg} · TYPE {aircraft_type}</div>
                </div>
                <div class="alt-badge {alt_class(alt)}">{esc(alt_text)}</div>
            </div>

            <div class="aircraft-body">
                <div class="aircraft-silhouette">✈</div>
                <div class="aircraft-data">
                    <div><span>Speed</span><b>{speed} kt</b></div>
                    <div><span>Track</span><b>{track}°</b></div>
                    <div><span>Position</span><b>{esc(pos_text)}</b></div>
                    <div><span>Last seen</span><b>{last_seen}</b></div>
                </div>
            </div>

            <a class="photo-link" href="{photo_url}" target="_blank" rel="noopener">
                {photo_label}
            </a>
        </article>
        """

    return cards


def build_markers(aircraft_items, limit=50):
    markers = []

    for hex_id, a in aircraft_items[:limit]:
        if a.get("lat") is not None and a.get("lon") is not None:
            markers.append({
                "hex": hex_id.upper(),
                "flight": a.get("flight") or "-",
                "lat": a.get("lat"),
                "lon": a.get("lon"),
                "alt": a.get("alt") or "-",
                "speed": a.get("speed") or "-",
                "last_seen": fmt_time(a.get("last_seen")),
            })

    return json.dumps(markers, ensure_ascii=False)


def build_acars_cards():
    messages = load_messages(ACARS_FILE, "ACARS")
    messages = messages[-12:]

    if not messages:
        return '<p class="note">No ACARS messages logged yet.</p>'

    cards = ""

    for m in reversed(messages):
        cards += f"""
        <article class="acars-card">
            <div class="acars-head">
                <div>
                    <div class="acars-flight">{esc(m.get("flight", "-"))}</div>
                    <div class="acars-meta">
                        ACARS · Tail {esc(m.get("tail", "-"))} · {esc(m.get("freq", "-"))} MHz
                    </div>
                </div>
                <div class="acars-meta">{esc(m.get("time", "-"))}</div>
            </div>

            <div class="acars-meta">
                Label {esc(m.get("label", "-"))} · Msg {esc(m.get("msgno", "-"))} · Level {esc(m.get("level", "-"))} dB
            </div>

            <div class="acars-text">{esc(m.get("text", "No text"))}</div>
        </article>
        """

    return cards


def build_live_page(store):
    aircraft_list = sorted(
        store["aircraft"].items(),
        key=lambda x: x[1].get("last_seen", ""),
        reverse=True
    )

    stats = daily_stats(store)

    aircraft_cards = build_aircraft_cards(
        aircraft_list,
        limit=50
    )

    markers_json = build_markers(
        aircraft_list,
        limit=50
    )

    last_update = fmt_time(
        store["summary"].get("updated")
    )

    acars_cards = build_acars_cards()

    body = f"""
<section>
    <h2>Map</h2>
    <div id="map"></div>
    <p class="note">Map shows aircraft with known position captured today.</p>
</section>

<div class="cards">
    <div class="card">
        <div class="value">{stats["unique"]}</div>
        <div class="label">Unique aircraft today</div>
    </div>

    <div class="card">
        <div class="value">{store["summary"].get("last_seen_live", 0)}</div>
        <div class="label">Aircraft currently visible</div>
    </div>

    <div class="card">
        <div class="value">{stats["with_position"]}</div>
        <div class="label">With position</div>
    </div>

    <div class="card">
        <div class="value">{stats["highest_alt"]} ft</div>
        <div class="label">Highest altitude</div>
    </div>

    <div class="card">
        <div class="value">{stats["max_speed"]} kt</div>
        <div class="label">Max speed</div>
    </div>

    <div class="card">
        <div class="value">{last_update}</div>
        <div class="label">Last update</div>
    </div>
</div>

<section>
    <h2>Latest aircraft</h2>
    <div class="aircraft-grid">
        {aircraft_cards}
    </div>
</section>

<section>
    <h2>Latest ACARS messages</h2>
    <div class="acars-grid">
        {acars_cards}
    </div>
</section>

<script type="module">
import * as maplibregl from 'https://unpkg.com/maplibre-gl@6.6.0/dist/maplibre-gl.mjs';
const aircraft = {markers_json};

const map = new maplibregl.Map({{
    container: 'map',
    style: 'https://tiles.openfreemap.org/styles/dark',
    center: [{HOME_LON}, {HOME_LAT}],
    zoom: 6.5
}});

map.addControl(
    new maplibregl.NavigationControl({{
        showCompass: false
    }}),
    'top-right'
);


// Receiver marker
const receiver = document.createElement('div');

receiver.style.width = '20px';
receiver.style.height = '20px';
receiver.style.borderRadius = '50%';
receiver.style.background = '#41ff41';
receiver.style.border = '3px solid white';
receiver.style.boxShadow = '0 0 18px #41ff41';

new maplibregl.Marker({{
    element: receiver,
    anchor: 'center'
}})
    .setLngLat([{HOME_LON}, {HOME_LAT}])
    .setPopup(
        new maplibregl.Popup({{ offset: 15 }})
            .setHTML(
                '<b>VadelmaSky receiver</b><br>Jyväskylä, Finland'
            )
    )
    .addTo(map);


function altitudeColor(alt) {{
    if (!alt || alt === '-') return '#9ca3af';
    if (alt < 10000) return '#41ff41';
    if (alt < 25000) return '#facc15';
    if (alt < 35000) return '#fb923c';
    return '#f87171';
}}


// Aircraft markers
aircraft.forEach(a => {{

    const color = altitudeColor(Number(a.alt));

    const marker = document.createElement('div');

    marker.style.width = '14px';
    marker.style.height = '14px';
    marker.style.borderRadius = '50%';
    marker.style.background = color;
    marker.style.border = `2px solid ${{color}}`;
    marker.style.boxShadow = `0 0 8px ${{color}}`;
    marker.style.cursor = 'pointer';

    new maplibregl.Marker({{
        element: marker,
        anchor: 'center'
    }})
        .setLngLat([a.lon, a.lat])
        .setPopup(
            new maplibregl.Popup({{ offset: 12 }})
                .setHTML(`
                    <b>${{a.flight}}</b><br>
                    ICAO: ${{a.hex}}<br>
                    Alt: ${{a.alt}} ft<br>
                    Speed: ${{a.speed}} kt<br>
                    Last seen: ${{a.last_seen}}
                `)
        )
        .addTo(map);
}});
</script>
"""
    INDEX.write_text(page_template("VadelmaSky.live", body), encoding="utf-8")


def load_history_manifest():
    if not HISTORY_MANIFEST.exists():
        return {"days": {}}

    try:
        data = json.loads(HISTORY_MANIFEST.read_text(encoding="utf-8"))

        if "days" not in data:
            data["days"] = {}

        return data

    except Exception as e:
        print(f"History manifest load failed: {e}")
        return {"days": {}}


def ensure_history_manifest():
    """
    First run only:
    build the small history manifest from existing local JSON archives.
    After that we never need to scan old history again.
    """

    if HISTORY_MANIFEST.exists():
        return load_history_manifest()

    print("Building initial history manifest...")

    manifest = {"days": {}}

    for file in sorted(DATA.glob("*.json")):
        date_name = file.stem

        try:
            payload = json.loads(file.read_text(encoding="utf-8"))
        except Exception:
            continue

        stats = daily_stats(payload)

        manifest["days"][date_name] = {
            "unique": stats["unique"],
            "with_position": stats["with_position"],
            "highest_alt": stats["highest_alt"],
            "max_speed": stats["max_speed"],
            "updated": payload.get("summary", {}).get("updated"),
            "data_url": f"/data/{date_name}.json",
        }

    save_json(HISTORY_MANIFEST, manifest)

    print(f"History manifest created: {len(manifest['days'])} days")

    return manifest


def update_history_manifest(date_name, payload):
    manifest = ensure_history_manifest()

    stats = daily_stats(payload)

    manifest["days"][date_name] = {
        "unique": stats["unique"],
        "with_position": stats["with_position"],
        "highest_alt": stats["highest_alt"],
        "max_speed": stats["max_speed"],
        "updated": payload.get("summary", {}).get("updated"),
        "data_url": f"/data/{date_name}.json",
    }

    save_json(HISTORY_MANIFEST, manifest)

    return manifest


def build_history_day_viewer():
    body = r"""
<section>
    <h2 id="day-title">History</h2>
    <p><a href="/history/">← Back to history</a></p>
    <p id="day-status" class="note">Loading daily aircraft log…</p>
</section>

<div id="day-stats" class="cards"></div>

<section>
    <h2>Aircraft for this day</h2>
    <div id="day-aircraft" class="aircraft-grid"></div>
</section>

<script>
function escapeHtml(value) {
    return String(value ?? '-')
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#039;');
}


function altitudeClass(alt) {
    if (!Number.isFinite(alt)) return 'unknown';
    if (alt < 10000) return 'low';
    if (alt < 25000) return 'mid';
    return 'high';
}


function fmtTime(value) {
    if (!value) return '-';

    const iso = value.endsWith('Z') ? value : value + 'Z';
    const d = new Date(iso);

    if (Number.isNaN(d.getTime()))
        return escapeHtml(value);

    return d.toISOString()
        .slice(0, 16)
        .replace('T', ' ') + ' UTC';
}


function calculateStats(payload) {
    const aircraft = Object.values(payload.aircraft || {});

    const withPosition = aircraft.filter(
        a => a.lat != null && a.lon != null
    ).length;

    const highestAlt = Math.max(
        0,
        ...aircraft.map(a =>
            Number.isFinite(a.alt) ? a.alt : 0
        )
    );

    const maxSpeed = Math.max(
        0,
        ...aircraft.map(a =>
            Number.isFinite(a.speed) ? a.speed : 0
        )
    );

    return {
        unique: aircraft.length,
        withPosition: withPosition,
        highestAlt: highestAlt,
        maxSpeed: Math.round(maxSpeed * 10) / 10
    };
}


function renderStats(stats) {
    document.getElementById('day-stats').innerHTML = `
        <div class="card">
            <div class="value">${stats.unique}</div>
            <div class="label">Unique aircraft</div>
        </div>

        <div class="card">
            <div class="value">${stats.withPosition}</div>
            <div class="label">With position</div>
        </div>

        <div class="card">
            <div class="value">${stats.highestAlt} ft</div>
            <div class="label">Highest altitude</div>
        </div>

        <div class="card">
            <div class="value">${stats.maxSpeed} kt</div>
            <div class="label">Max speed</div>
        </div>
    `;
}


function renderAircraft(payload) {
    const items = Object.entries(payload.aircraft || {})
        .sort((a, b) =>
            String(b[1].last_seen || '')
                .localeCompare(String(a[1].last_seen || ''))
        );

    const cards = items.map(([hexId, a]) => {

        const flight = escapeHtml(a.flight || 'Unknown');
        const icao = escapeHtml(hexId.toUpperCase());

        const regRaw = a.reg || '';
        const reg = escapeHtml(regRaw || '-');

        const type = escapeHtml(a.type || '-');

        const alt = Number.isFinite(a.alt)
            ? a.alt
            : null;

        const altText = alt !== null
            ? `${alt} ft`
            : '-';

        const speed = escapeHtml(a.speed ?? '-');
        const track = escapeHtml(a.track ?? '-');

        const position =
            Number.isFinite(a.lat) &&
            Number.isFinite(a.lon)

            ? `${a.lat.toFixed(4)}, ${a.lon.toFixed(4)}`
            : 'No position';

        let photoUrl;
        let photoLabel;

        if (regRaw) {
            photoUrl =
                `https://www.jetphotos.com/photo/keyword/${encodeURIComponent(regRaw)}`;
            photoLabel = 'Search aircraft photo';
        }
        else {
            photoUrl =
                `https://globe.adsbexchange.com/?icao=${encodeURIComponent(hexId.toLowerCase())}`;
            photoLabel = 'View aircraft info';
        }

        return `
        <article class="aircraft-card">

            <div class="aircraft-top">
                <div>
                    <div class="flight">${flight}</div>
                    <div class="meta">
                        ICAO ${icao} · REG ${reg} · TYPE ${type}
                    </div>
                </div>

                <div class="alt-badge ${altitudeClass(alt)}">
                    ${escapeHtml(altText)}
                </div>
            </div>

            <div class="aircraft-body">

                <div class="aircraft-silhouette">✈</div>

                <div class="aircraft-data">

                    <div>
                        <span>Speed</span>
                        <b>${speed} kt</b>
                    </div>

                    <div>
                        <span>Track</span>
                        <b>${track}°</b>
                    </div>

                    <div>
                        <span>Position</span>
                        <b>${escapeHtml(position)}</b>
                    </div>

                    <div>
                        <span>Last seen</span>
                        <b>${fmtTime(a.last_seen)}</b>
                    </div>

                </div>
            </div>

            <a
                class="photo-link"
                href="${photoUrl}"
                target="_blank"
                rel="noopener"
            >
                ${photoLabel}
            </a>

        </article>
        `;
    });

    document.getElementById('day-aircraft').innerHTML =
        cards.join('') ||
        '<p class="note">No aircraft stored for this day.</p>';
}


(async function () {

    const params =
        new URLSearchParams(window.location.search);

    const date = params.get('date');

    const status =
        document.getElementById('day-status');

    if (
        !date ||
        !/^\d{4}-\d{2}-\d{2}$/.test(date)
    ) {
        status.textContent =
            'No valid date selected.';
        return;
    }

    document.getElementById('day-title')
        .textContent = date;

    document.title =
        `VadelmaSky history ${date}`;

    try {

        const response = await fetch(
            `/data/${date}.json`,
            { cache: 'no-store' }
        );

        if (!response.ok)
            throw new Error(
                `HTTP ${response.status}`
            );

        const payload =
            await response.json();

        renderStats(
            calculateStats(payload)
        );

        renderAircraft(payload);

        status.textContent =
            `Daily aircraft log · ${fmtTime(
                payload.summary?.updated
            )}`;

    }
    catch (err) {

        status.textContent =
            `Could not load archive: ${err.message}`;

    }

})();
</script>
"""

    HISTORY_DAY.write_text(
        page_template(
            "VadelmaSky history",
            body
        ),
        encoding="utf-8"
    )


def build_history_pages(manifest):
    history_rows = ""

    for date_name in sorted(
        manifest.get("days", {}),
        reverse=True
    ):
        item = manifest["days"][date_name]

        updated = fmt_time(
            item.get("updated")
        )

        history_rows += f"""
        <tr>
            <td>
                <a href="/history/day.html?date={esc(date_name)}">
                    {esc(date_name)}
                </a>
            </td>

            <td>{esc(item.get("unique", 0))}</td>
            <td>{esc(item.get("with_position", 0))}</td>
            <td>{esc(item.get("highest_alt", 0))} ft</td>
            <td>{esc(item.get("max_speed", 0))} kt</td>
            <td>{esc(updated)}</td>

            <td>
                <a href="{esc(item.get("data_url"))}">
                    JSON
                </a>
            </td>
        </tr>
        """

    body = f"""
<section>
    <h2>History</h2>

    <p class="note">
        Daily aircraft logs generated from local ADS-B reception.
        Historical aircraft data is served from the GitHub Pages archive.
    </p>

    <table>
        <thead>
            <tr>
                <th>Date</th>
                <th>Unique aircraft</th>
                <th>With position</th>
                <th>Highest altitude</th>
                <th>Max speed</th>
                <th>Last update</th>
                <th>Data</th>
            </tr>
        </thead>

        <tbody>
            {history_rows}
        </tbody>
    </table>

</section>
"""

    HISTORY_INDEX.write_text(
        page_template(
            "VadelmaSky history",
            body
        ),
        encoding="utf-8"
    )

    build_history_day_viewer()


def main():
    store = load_store()
    aircraft_db = load_aircraft_db()

    if not SOURCE.exists():
        print(f"Missing source: {SOURCE}")
        raise SystemExit(1)

    data = json.loads(SOURCE.read_text(encoding="utf-8"))

    now = datetime.utcnow().isoformat()
    count_now = 0

    for a in data.get("aircraft", []):
        hex_id = a.get("hex")
        if not hex_id:
            continue

        count_now += 1
        old = store["aircraft"].get(hex_id, {})
        flight = (a.get("flight") or old.get("flight") or "").strip()
        db_info = aircraft_db.get(hex_id.lower(), {})

        store["aircraft"][hex_id] = {
            "hex": hex_id,
            "flight": flight,
            "reg": a.get("r") or db_info.get("reg") or old.get("reg"),
            "type": a.get("t") or db_info.get("type") or old.get("type"),
            "lat": a.get("lat", old.get("lat")),
            "lon": a.get("lon", old.get("lon")),
            "alt": a.get("alt_baro", old.get("alt")),
            "speed": a.get("gs", old.get("speed")),
            "track": a.get("track", old.get("track")),
            "seen_first": old.get("seen_first", now),
            "last_seen": now,
        }

    store["summary"] = {
        "total_unique_aircraft": len(store["aircraft"]),
        "last_seen_live": count_now,
        "updated": now,
    }

    date_name = datetime.utcnow().strftime("%Y-%m-%d")

    save_json(TODAY_FILE, store)
    save_json(DATA / f"{date_name}.json", store)

    manifest = update_history_manifest(
    date_name,
    store
    )

    build_live_page(store)
    build_history_pages(manifest)

if __name__ == "__main__":
    main()
