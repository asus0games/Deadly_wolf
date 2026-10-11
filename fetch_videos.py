#!/usr/bin/env python3
import json, urllib.request, urllib.parse, os, sys, re, html

CONFIG_FILE = "config.json"
OUTPUT_FILE = "videos.json"
MAX_VIDEOS = 12
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}

def find_value(cfg, keys):
    """Ищет первое значение по списку ключей, рекурсивно."""
    if isinstance(cfg, dict):
        for k, v in cfg.items():
            if k in keys and isinstance(v, str) and v.strip():
                return v.strip()
            found = find_value(v, keys)
            if found:
                return found
    elif isinstance(cfg, list):
        for item in cfg:
            found = find_value(item, keys)
            if found:
                return found
    return None

def valid_channel_id(s):
    return bool(re.fullmatch(r"UC[A-Za-z0-9_-]{22}", s or ""))

def try_fetch(url, timeout=30):
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8")
    except Exception as e:
        print(f"  ! {url[:80]} -> {e}")
        return None

def resolve_channel_id_from_handle(handle):
    """Скачивает страницу канала и достаёт channelId."""
    handle = handle.lstrip("@")
    for url in (f"https://www.youtube.com/@{handle}",
                f"https://www.youtube.com/user/{handle}"):
        text = try_fetch(url)
        if not text:
            continue
        m = re.search(r'"channelId":"(UC[A-Za-z0-9_-]{22})"', text)
        if m:
            return m.group(1)
    return None

def parse_xml(xml_text):
    import xml.etree.ElementTree as ET
    ns = {"a": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015",
          "m": "http://search.yahoo.com/mrss/"}
    videos = []
    try:
        root = ET.fromstring(xml_text)
    except Exception as e:
        print(f"  ! XML parse error: {e}")
        return videos
    for entry in root.findall("a:entry", ns)[:MAX_VIDEOS]:
        vid = entry.findtext("yt:videoId", "", ns)
        if not vid:
            continue
        title = html.unescape(entry.findtext("a:title", "", ns) or "")
        pub = (entry.findtext("a:published", "", ns) or "")[:10]
        author = html.unescape(entry.findtext("a:author/a:name", "", ns) or "")
        videos.append({
            "title": title,
            "videoId": vid,
            "url": f"https://www.youtube.com/watch?v={vid}",
            "thumbnail": f"https://img.youtube.com/vi/{vid}/hqdefault.jpg",
            "published": pub,
            "author": author,
        })
    return videos

def parse_json_feed(json_text):
    videos = []
    try:
        data = json.loads(json_text)
        for item in data.get("items", [])[:MAX_VIDEOS]:
            vid = item.get("guid", "")
            if "yt:video:" in vid:
                vid = vid.split("yt:video:")[1]
            videos.append({
                "title": html.unescape(item.get("title", "")),
                "videoId": vid,
                "url": item.get("link", f"https://www.youtube.com/watch?v={vid}"),
                "thumbnail": item.get("thumbnail", f"https://img.youtube.com/vi/{vid}/hqdefault.jpg"),
                "published": (item.get("pubDate", "") or "")[:10],
                "author": html.unescape(item.get("author", "")),
            })
    except Exception as e:
        print(f"  ! JSON parse error: {e}")
    return videos

def write_empty():
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump({"videos": [], "updated": "failed"}, f, ensure_ascii=False, indent=2)
    print(f"OK: wrote empty {OUTPUT_FILE}")

def main():
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        print("OK: config loaded")
    except Exception as e:
        print(f"ERROR: cannot read {CONFIG_FILE}: {e}")
        write_empty()
        return

    channel_id = find_value(cfg, ("channelId", "channel_id"))
    handle = find_value(cfg, ("channelHandle", "handle", "channelUrl"))

    if not valid_channel_id(channel_id):
        if channel_id:
            print(f"WARN: channelId '{channel_id}' is not a valid UC-id, ignoring")
        channel_id = None
        if handle:
            print(f"Resolving channel id from handle {handle}...")
            channel_id = resolve_channel_id_from_handle(handle)
            print(f"Resolved channelId: {channel_id}")

    if not channel_id:
        print("ERROR: no valid channelId and no resolvable handle in config!")
        print('Add to config.json: "channelId": "UCxxxxxxxxxxxxxxxxxxxxxx"')
        write_empty()
        return

    feed = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    urls = [feed,
            "https://api.rss2json.com/v1/api.json?rss_url=" + urllib.parse.quote(feed, safe=""),
            "https://api.allorigins.win/raw?url=" + urllib.parse.quote(feed, safe="")]

    for i, url in enumerate(urls):
        print(f"\nTrying source {i+1}/{len(urls)}: {url[:80]}...")
        text = try_fetch(url)
        if not text:
            continue
        videos = parse_json_feed(text) if "rss2json" in url else parse_xml(text)
        if videos:
            print(f"OK: got {len(videos)} videos from source {i+1}")
            with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                json.dump({"videos": videos, "updated": "auto"}, f, ensure_ascii=False, indent=2)
            print(f"OK: saved to {OUTPUT_FILE}")
            return
        print("  Source responded but no videos found")

    print("\nWARNING: all sources failed, keeping existing videos.json")
    if not os.path.exists(OUTPUT_FILE):
        write_empty()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"FATAL: {e}")
        try:
            if not os.path.exists(OUTPUT_FILE):
                write_empty()
        except Exception:
            pass
    sys.exit(0)
