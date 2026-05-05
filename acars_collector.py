#!/usr/bin/env python3

import json
import re
import subprocess
from datetime import datetime
from pathlib import Path

OUT = Path("/home/dietpi/vadelmasky/messages/acars_latest.json")
OUT.parent.mkdir(exist_ok=True)

CMD = ["sudo", "tcpdump", "-l", "-A", "-s", "0", "-i", "any", "udp", "port", "5550"]

messages = []
seen = set()

print("Listening ACARS UDP 5550 via tcpdump...")

proc = subprocess.Popen(
    CMD,
    stdout=subprocess.PIPE,
    stderr=subprocess.DEVNULL,
    text=True,
    bufsize=1,
)

for line in proc.stdout:
    if "{" not in line:
        continue

    match = re.search(r"(\{.*\})", line)
    if not match:
        continue

    raw = match.group(1)

    try:
        msg = json.loads(raw)
    except Exception:
        continue

    key = (
        msg.get("timestamp"),
        msg.get("flight"),
        msg.get("tail"),
        msg.get("msgno"),
        msg.get("text"),
    )

    if key in seen:
        continue

    seen.add(key)
    if len(seen) > 200:
        seen = set(list(seen)[-100:])

    text = msg.get("text") or "No text"

    item = {
        "time": datetime.utcnow().strftime("%d.%m.%Y %H:%M UTC"),
        "source": "ACARS",
        "flight": msg.get("flight") or "-",
        "tail": msg.get("tail") or "-",
        "freq": msg.get("freq") or "-",
        "level": msg.get("level") or "-",
        "label": msg.get("label") or "-",
        "msgno": msg.get("msgno") or "-",
        "text": text,
    }

    messages.append(item)
    messages = messages[-30:]

    OUT.write_text(
        json.dumps({"messages": messages}, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    print("ACARS:", item["flight"], item["tail"], item["label"], item["text"])
