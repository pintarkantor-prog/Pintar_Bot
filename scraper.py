import requests
import re
from config import YOUTUBE_API_KEY

YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"


def extract_identifier(url):
    """
    Ekstrak handle atau channel ID dari URL YouTube.
    Format yang didukung:
      - https://www.youtube.com/@ItsJaneSali  → ('handle', 'ItsJaneSali')
      - @ItsJaneSali                          → ('handle', 'ItsJaneSali')
      - https://www.youtube.com/channel/UCxx  → ('id', 'UCxx...')
      - https://www.youtube.com/c/Name        → ('username', 'Name')
    """
    if not url:
        return None, None

    url = str(url).strip()

    # Format @handle dalam URL
    match = re.search(r'/@([^/\s?&]+)', url)
    if match:
        return 'handle', match.group(1)

    # Format channel ID (UCxxx)
    match = re.search(r'/channel/(UC[a-zA-Z0-9_-]+)', url)
    if match:
        return 'id', match.group(1)

    # Format /c/ atau /user/
    match = re.search(r'/(?:c|user)/([^/\s?&]+)', url)
    if match:
        return 'username', match.group(1)

    # Plain handle: @something (tanpa URL)
    if url.startswith('@'):
        return 'handle', url[1:]

    return None, None


def resolve_handle_to_id(handle, api_key):
    """Resolve @handle ke channel ID via API (1 unit quota)"""
    try:
        r = requests.get(
            f"{YOUTUBE_API_BASE}/channels",
            params={'part': 'id', 'forHandle': handle, 'key': api_key},
            timeout=10
        )
        data = r.json()
        items = data.get('items', [])
        return items[0]['id'] if items else None
    except:
        return None


def get_channels_stats_batch(channel_ids, api_key):
    """
    Ambil statistik batch hingga 50 channel per request.
    Kini termasuk ambil 2 video terbaru untuk cek views (Logic Busuk).
    Return: dict {channel_id: {'subs': int, 'status': str, 'views': [v1, v2]}}
    """
    result = {}
    # Batch 50 per request
    for i in range(0, len(channel_ids), 50):
        batch = channel_ids[i:i+50]
        try:
            # 1. Ambil Stats Dasar (Subs & Privacy)
            r = requests.get(
                f"{YOUTUBE_API_BASE}/channels",
                params={
                    'part': 'statistics,status,contentDetails',
                    'id': ','.join(batch),
                    'key': api_key
                },
                timeout=15
            )
            data = r.json()
            if 'error' in data: continue
            
            for item in data.get('items', []):
                ch_id = item['id']
                stats = item.get('statistics', {})
                status_info = item.get('status', {})
                uploads_playlist = item.get('contentDetails', {}).get('relatedPlaylists', {}).get('uploads')

                privacy = status_info.get('privacyStatus', 'public')
                is_suspend = privacy != 'public'
                hidden = stats.get('hiddenSubscriberCount', False)
                subs = 0 if hidden else int(stats.get('subscriberCount', 0))

                result[ch_id] = {
                    'subs': subs,
                    'status': 'SUSPEND' if is_suspend else 'ACTIVE',
                    'hidden': hidden,
                    'uploads_id': uploads_playlist,
                    'latest_views': []
                }

                # 2. Ambil 2 Video Terbaru via Playlist Uploads (Efisien, 1 unit per channel)
                if uploads_playlist:
                    rv = requests.get(
                        f"{YOUTUBE_API_BASE}/playlistItems",
                        params={
                            'part': 'contentDetails',
                            'playlistId': uploads_playlist,
                            'maxResults': 2,
                            'key': api_key
                        },
                        timeout=10
                    )
                    v_data = rv.json()
                    v_ids = [v['contentDetails']['videoId'] for v in v_data.get('items', [])]
                    
                    if v_ids:
                        # Ambil view count video-video tersebut
                        rv_stats = requests.get(
                            f"{YOUTUBE_API_BASE}/videos",
                            params={
                                'part': 'statistics',
                                'id': ','.join(v_ids),
                                'key': api_key
                            },
                            timeout=10
                        )
                        vs_data = rv_stats.json()
                        views = [int(v['statistics'].get('viewCount', 0)) for v in vs_data.get('items', [])]
                        result[ch_id]['latest_views'] = views
        except:
            continue
    return result


def scrape_youtube_channel(url):
    """
    Entry point single channel — wrapper ke batch function.
    Return: {'subs': int, 'status': str, 'views': list, 'error': str|None}
    """
    result = scrape_youtube_channels_bulk([url])
    return result.get(url, {'subs': 0, 'status': 'ERROR', 'error': 'Tidak dapat diproses'})


def scrape_youtube_channels_bulk(urls):
    """
    BULK scraping: terima list URL, return dict {url: result}.
    Efisien: resolve handle dulu, lalu batch statistics + views.
    """
    if not YOUTUBE_API_KEY:
        return {url: {'subs': 0, 'status': 'ERROR', 'error': 'YOUTUBE_API_KEY belum diset'} for url in urls}

    url_to_identifier = {}
    for url in urls:
        itype, ident = extract_identifier(url)
        if ident: url_to_identifier[url] = (itype, ident)

    url_to_channel_id = {}
    for url, (itype, ident) in url_to_identifier.items():
        if itype == 'id': url_to_channel_id[url] = ident
        elif itype == 'handle':
            ch_id = resolve_handle_to_id(ident, YOUTUBE_API_KEY)
            if ch_id: url_to_channel_id[url] = ch_id
        elif itype == 'username':
            try:
                r = requests.get(f"{YOUTUBE_API_BASE}/channels", params={'part': 'id', 'forUsername': ident, 'key': YOUTUBE_API_KEY}, timeout=10)
                items = r.json().get('items', [])
                if items: url_to_channel_id[url] = items[0]['id']
            except: pass

    all_channel_ids = list(set(url_to_channel_id.values()))
    stats_by_id = get_channels_stats_batch(all_channel_ids, YOUTUBE_API_KEY)

    results = {}
    for url in urls:
        if url not in url_to_identifier:
            results[url] = {'subs': 0, 'status': 'ERROR', 'error': 'Format URL tidak dikenali'}
            continue

        ch_id = url_to_channel_id.get(url)
        if not ch_id:
            results[url] = {'subs': 0, 'status': 'SUSPEND', 'error': 'Channel tidak ditemukan'}
            continue

        stat = stats_by_id.get(ch_id)
        if not stat:
            results[url] = {'subs': 0, 'status': 'SUSPEND', 'error': 'API No Response'}
            continue

        results[url] = {
            'subs': stat['subs'],
            'status': stat['status'],
            'views': stat['latest_views'],
            'error': None,
            'hidden': stat.get('hidden', False)
        }
    return results
