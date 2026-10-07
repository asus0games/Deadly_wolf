# -*- coding: utf-8 -*-
"""Скачивает ленту YouTube и сохраняет её в videos.json.
Запускается автоматически по расписанию (GitHub Actions) или вручную."""
import json, sys, urllib.request, xml.etree.ElementTree as ET
from datetime import datetime, timezone

def main():
    try:
        with open('config.json', encoding='utf-8') as f:
            cfg = json.load(f)
        channel_id = cfg['channel']['channelId']
    except Exception as e:
        print('Не удалось прочитать config.json:', e)
        sys.exit(1)

    rss_url = 'https://www.youtube.com/feeds/videos.xml?channel_id=' + channel_id
    req = urllib.request.Request(rss_url, headers={'User-Agent': 'Mozilla/5.0 (site-widget)'})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = r.read()
    except Exception as e:
        print('Не удалось скачать ленту YouTube:', e)
        sys.exit(1)

    ns = {'a': 'http://www.w3.org/2005/Atom',
          'm': 'http://search.yahoo.com/mrss/',
          'yt': 'http://www.youtube.com/xml/schemas/2015'}
    root = ET.fromstring(data)
    videos = []
    for entry in root.findall('a:entry', ns):
        vid = entry.find('yt:videoId', ns)
        title = entry.find('a:title', ns)
        published = entry.find('a:published', ns)
        thumb_el = entry.find('m:group/m:thumbnail', ns)
        desc_el = entry.find('m:group/m:description', ns)
        vid_id = vid.text.strip() if vid is not None else ''
        if not vid_id:
            continue
        videos.append({
            'id': vid_id,
            'title': title.text if title is not None else 'Без названия',
            'published': published.text if published is not None else '',
            'url': 'https://www.youtube.com/watch?v=' + vid_id,
            'thumbnail': (thumb_el.get('url') if thumb_el is not None else '')
                         or ('https://i.ytimg.com/vi/%s/hqdefault.jpg' % vid_id),
            'description': (desc_el.text or '') if desc_el is not None else ''
        })

    out = {
        'updated': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'videos': videos
    }
    with open('videos.json', 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print('Сохранено видео: %d' % len(videos))

if __name__ == '__main__':
    main()
