#!/usr/bin/env python3
import json, urllib.request, urllib.error, os, sys, re

CONFIG_FILE = "config.json"
OUTPUT_FILE = "videos.json"
MAX_VIDEOS = 12

def find_channel_id(cfg):
    """Search for channelId anywhere in config"""
    if isinstance(cfg, dict):
        for k, v in cfg.items():
            if k == "channelId" and isinstance(v, str) and v.startswith("UC"):
                return v
            found = find_channel_id(v)
            if found:
                return found
    elif isinstance(cfg, list):
        for item in cfg:
            found = find_channel_id(item)
            if found:
                return found
    return None

def find_handle(cfg):
    """Search for channel handle @something"""
    if isinstance(cfg, dict):
        for k, v in cfg.items():
            if k in ("channelHandle", "handle", "channelUrl") and isinstance(v, str):
                m = re.search(r'(@[\w.-]+)', v)
                if m:
                    return m.group(1)
            found = find_handle(v)
            if found:
                return found
    elif isinstance(cfg, list):
        for item in cfg:
            found = find_handle(item)
            if found:
                return found
    return None

def try_fetch(url, timeout=30):
    """Fetch URL, return text or None"""
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
        })
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8")
    except Exception as e:
        print(f"  ! {url[:80]} -> {e}")
        return None

def parse_xml(xml_text):
    """Parse YouTube RSS XML, return list of dicts"""
    videos = []
    entries = re.findall(r'<entry>(.*?)</entry>', xml_text, re.DOTALL)
    for entry in entries[:MAX_VIDEOS]:
        title_m = re.search(r'<title>(.*?)</title>', entry, re.DOTALL)
        vid_m = re.search(r'<yt:videoId>(.*?)</yt:videoId>', entry)
        pub_m = re.search(r'<published>(.*?)</published>', entry)
        author_m = re.search(r'<name>(.*?)</name>', entry, re.DOTALL)
        if vid_m:
            videos.append({
                "title": title_m.group(1) if title_m else "",
                "videoId": vid_m.group(1),
                "url": f"https://www.youtube.com/watch?v={vid_m.group(1)}",
                "thumbnail": f"https://img.youtube.com/vi/{vid_m.group(1)}/hqdefault.jpg",
                "published": pub_m.group(1)[:10] if pub_m else "",
                "author": author_m.group(1) if author_m else ""
            })
    return videos

def parse_json_feed(json_text):
    """Parse rss2json response"""
    videos = []
    try:
        data = json.loads(json_text)
        for item in data.get("items", [])[:MAX_VIDEOS]:
            vid = item.get("guid", "")
            if "yt:video:" in vid:
                vid = vid.split("yt:video:")[1]
            videos.append({
                "title": item.get("title", ""),
                "videoId": vid,
                "url": item.get("link", f"https://www.youtube.com/watch?v={vid}"),
                "thumbnail": item.get("thumbnail", f"https://img.youtube.com/vi/{vid}/hqdefault.jpg"),
                "published": item.get("pubDate", "")[:10],
                "author": item.get("author", "")
            })
    except Exception as e:
        print(f"  ! JSON parse error: {e}")
    return videos

def main():
    # Read config
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        print(f"OK: config loaded")
    except Exception as e:
        print(f"ERROR: cannot read {CONFIG_FILE}: {e}")
        write_empty()
        return

    channel_id = find_channel_id(cfg)
    handle = find_handle(cfg)
    print(f"channelId: {channel_id}")
    print(f"handle: {handle}")

    # Build list of URLs to try
    urls = []
    if channel_id:
        urls.append(f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}")
    if handle and not channel_id:
        urls.append(f"https://www.youtube.com/feeds/videos.xml?user={handle.lstrip('@')}")

    # Also try rss2json as fallback
    if channel_id:
        urls.append(f"https://api.rss2json.com/v1/api.json?rss_url=https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}")

    # Also try allorigins wrapper
    if channel_id:
        yt_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
        urls.append(f"https://api.allorigins.win/raw?url={urllib.request.quote(yt_url)}")

    if not urls:
        print("ERROR: no channelId and no handle found in config!")
        print("Add to config.json: \"channelId\": \"UCxxxxxxxxxxxxxxxxxxxxxx\"")
        write_empty()
        return

    # Try each URL
    for i, url in enumerate(urls):
        print(f"\nTrying source {i+1}/{len(urls)}: {url[:80]}...")
        text = try_fetch(url)
        if not text:
            continue

        # Determine parser
        if "api.json" in url or "rss2json" in url:
            videos = parse_json_feed(text)
        else:
            videos = parse_xml(text)

        if videos:
            print(f"OK: got {len(videos)} videos from source {i+1}")
            output = {"videos": videos, "updated": "auto"}
            with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                json.dump(output, f, ensure_ascii=False, indent=2)
            print(f"OK: saved to {OUTPUT_FILE}")
            return
        else:
            print(f"  Source responded but no videos found")

    print("\nWARNING: all sources failed, keeping existing videos.json")
    # Don't overwrite existing file if all failed
    if not os.path.exists(OUTPUT_FILE):
        write_empty()

def write_empty():
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump({"videos": [], "updated": "failed"}, f, ensure_ascii=False, indent=2)
    print(f"OK: wrote empty {OUTPUT_FILE}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"FATAL: {e}")
        # Still exit 0 so Actions doesn't fail
        try:
            if not os.path.exists(OUTPUT_FILE):
                write_empty()
        except:
            pass
    # Always exit 0
    sys.exit(0)
