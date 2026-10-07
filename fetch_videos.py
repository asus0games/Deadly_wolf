import json
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

with open("config.json", encoding="utf-8") as f:
    config = json.load(f)

channel_id = ""
if isinstance(config.get("channelId"), str):
    channel_id = config["channelId"].strip()
elif isinstance(config.get("channel"), dict):
    channel_id = str(config["channel"].get("channelId") or "").strip()

if not channel_id.startswith("UC"):
    raise SystemExit("channelId не найден в config.json (должен начинаться с UC)")

url = "https://www.youtube.com/feeds/videos.xml?channel_id=" + channel_id
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
with urllib.request.urlopen(req, timeout=30) as resp:
    data = resp.read()

root = ET.fromstring(data)
ns = {
    "a": "http://www.w3.org/2005/Atom",
    "m": "http://search.yahoo.com/mrss/",
    "yt": "http://www.youtube.com/xml/schemas/2015",
}

videos = []
for entry in root.findall("a:entry", ns):
    vid = entry.find("yt:videoId", ns)
    title = entry.find("a:title", ns)
    pub = entry.find("a:published", ns)
    group = entry.find("m:group", ns)
    thumb = group.find("m:thumbnail", ns) if group is not None else None
    desc = group.find("m:description", ns) if group is not None else None
    videos.append({
        "id": (vid.text or "") if vid is not None else "",
        "title": (title.text or "") if title is not None else "",
        "published": (pub.text or "") if pub is not None else "",
        "thumbnail": (thumb.get("url") or "") if thumb is not None else "",
        "description": ((desc.text or "")[:300]) if desc is not None else "",
    })

with open("videos.json", "w", encoding="utf-8") as f:
    json.dump({
        "updated": datetime.now(timezone.utc).isoformat(),
        "channelId": channel_id,
        "videos": videos,
    }, f, ensure_ascii=False, indent=2)

print("Saved", len(videos), "videos for channel", channel_id)
