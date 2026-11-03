import re
import requests
import urllib.parse
from typing import List, Dict, Any, Optional
from backend.database import get_cached_anime, set_cached_anime

TVMAZE_API_URL = "https://api.tvmaze.com"

COUNTRY_MAP = {
    "KR": "K-DRAMA (ซีรีส์เกาหลี)",
    "JP": "J-DRAMA (ซีรีส์ญี่ปุ่น)",
    "US": "US SERIES (ซีรีส์ฝรั่ง)",
    "GB": "UK SERIES (ซีรีส์อังกฤษ)",
    "TH": "THAI SERIES (ซีรีส์ไทย)",
    "CN": "C-DRAMA (ซีรีส์จีน)",
    "TW": "TW-DRAMA (ซีรีส์ไต้หวัน)",
    "HK": "HK-DRAMA (ซีรีส์ฮ่องกง)",
    "ES": "SPANISH SERIES (ซีรีส์สเปน)"
}

def clean_html(text: Optional[str]) -> str:
    if not text:
        return ""
    return re.sub(r"<[^>]*>", "", text).strip()

def search_live_action_series(query: str) -> List[Dict[str, Any]]:
    """Search TVMaze for live-action TV series (Korean, Japanese, US, etc.)."""
    try:
        url = f"{TVMAZE_API_URL}/search/shows?q={urllib.parse.quote(query)}"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            results = []
            for item in resp.json():
                show = item.get("show", {})
                country_code = ""
                network = show.get("network") or show.get("webChannel") or {}
                if isinstance(network, dict):
                    country_info = network.get("country") or {}
                    country_code = country_info.get("code", "")

                fmt_label = COUNTRY_MAP.get(country_code, "TV SERIES")
                img = show.get("image") or {}
                cover = img.get("original") or img.get("medium") or ""

                results.append({
                    "id": f"tv_{show['id']}",
                    "raw_id": show["id"],
                    "media_type": "series",
                    "title_english": show.get("name", ""),
                    "title_romaji": show.get("name", ""),
                    "title_native": "",
                    "episodes": None,  # Will be counted in details
                    "format": fmt_label,
                    "status": show.get("status", ""),
                    "score": int(show.get("rating", {}).get("average", 0) * 10) if show.get("rating", {}).get("average") else None,
                    "year": show.get("premiered", "")[:4] if show.get("premiered") else "",
                    "cover_image": cover,
                    "banner_image": cover,
                    "description": clean_html(show.get("summary")),
                    "genres": show.get("genres", []),
                    "network": network.get("name", "")
                })
            return results
    except Exception as e:
        print(f"Error searching TVMaze: {e}")
    return []

def get_series_guide(series_id: int) -> Optional[Dict[str, Any]]:
    """Get complete episode guide for a live-action series with seasons & specials."""
    cache_key = 9000000 + series_id  # Offset ID for series cache
    cached = get_cached_anime(cache_key)
    if cached:
        return cached

    try:
        # 1. Fetch Show Details
        url_show = f"{TVMAZE_API_URL}/shows/{series_id}"
        resp_show = requests.get(url_show, timeout=10)
        if resp_show.status_code != 200:
            return None
        show = resp_show.json()

        # 2. Fetch Episodes
        url_eps = f"{TVMAZE_API_URL}/shows/{series_id}/episodes?specials=1"
        resp_eps = requests.get(url_eps, timeout=10)
        if resp_eps.status_code != 200:
            return None
        raw_eps = resp_eps.json()

        episodes = []
        filler_count = 0
        canon_count = 0

        for idx, ep in enumerate(raw_eps, start=1):
            ep_name = ep.get("name") or f"Episode {ep.get('number') or idx}"
            ep_name_low = ep_name.lower()
            season_num = ep.get("season", 1)
            ep_num = ep.get("number") or idx
            is_special = (
                "special" in ep_name_low or 
                "recap" in ep_name_low or 
                "behind the scenes" in ep_name_low or 
                "making of" in ep_name_low or
                "interview" in ep_name_low or
                season_num == 0
            )

            if is_special:
                badge = "filler"
                canonical_type = "Special / Recap (ตอนพิเศษ/ย้อนความ)"
                rec = "SKIP"
                filler_count += 1
            else:
                badge = "canon"
                canonical_type = f"Season {season_num} Main Story"
                rec = "MUST_WATCH"
                canon_count += 1

            episodes.append({
                "number": idx,
                "season": season_num,
                "episode_in_season": ep_num,
                "title": f"S{season_num}E{ep_num}: {ep_name}",
                "type": canonical_type,
                "badge": badge,
                "watch_recommendation": rec,
                "air_date": ep.get("airdate", ""),
                "summary": clean_html(ep.get("summary"))
            })

        total = len(episodes)
        filler_pct = round((filler_count / total) * 100, 1) if total > 0 else 0
        time_saved_hours = round((filler_count * 50) / 60, 1)  # Avg 50 mins per TV episode

        # Generate Seasons / Arcs
        seasons_map = {}
        for ep in episodes:
            s_num = ep["season"]
            if s_num not in seasons_map:
                seasons_map[s_num] = []
            seasons_map[s_num].append(ep)

        arcs = []
        for s_num, s_eps in sorted(seasons_map.items()):
            first_ep = s_eps[0]["number"]
            last_ep = s_eps[-1]["number"]
            s_title = f"ซีซัน {s_num} (Season {s_num})" if s_num > 0 else "ตอนพิเศษ / เบื้องหลัง (Specials)"
            arcs.append({
                "arc_number": s_num,
                "title": s_title,
                "range_display": f"ตอนที่ {first_ep} – {last_ep}",
                "start_ep": first_ep,
                "end_ep": last_ep,
                "episodes_count": len(s_eps),
                "status_label": "เนื้อเรื่องหลัก (Canon)" if s_num > 0 else "ตอนเสริมพิเศษ (Special)",
                "recommendation": "ต้องดู (Must Watch)" if s_num > 0 else "เลือกดูได้ (Optional)",
                "badge_color": "green" if s_num > 0 else "yellow",
                "is_filler": s_num == 0,
                "description": f"ดำเนินเรื่องหลักในซีซันที่ {s_num} รวม {len(s_eps)} ตอน",
                "sample_episodes": s_eps[:3]
            })

        network = show.get("network") or show.get("webChannel") or {}
        country_code = ""
        if isinstance(network, dict):
            country_info = network.get("country") or {}
            country_code = country_info.get("code", "")
        fmt_label = COUNTRY_MAP.get(country_code, "TV SERIES")

        # Natural Thai guidance
        title = show.get("name", "")
        if filler_count == 0:
            verdict = f"🎬 **{title}** เป็นซีรีส์ที่ดำเนินเนื้อเรื่องต่อเนื่อง 100% (Serialized Plot) ไม่มีตอนข้ามหรือตอนย้อนความ แนะนำให้ดูเรียงลำดับตั้งแต่ตอนแรกจนจบเพื่ออรรถรสสูงสุดครับ!"
        else:
            verdict = f"🎬 **{title}** มีเนื้อเรื่องหลัก {canon_count} ตอน และมีตอนพิเศษ/ย้อนความ {filler_count} ตอน สามารถดูเฉพาะตอนในซีซันหลักและข้ามตอน Recap เพื่อความกระชับได้ ประหยัดเวลาไปได้ {time_saved_hours} ชั่วโมงครับ"

        # Streaming links for Live-Action
        q_enc = urllib.parse.quote(title)
        streaming_links = [
            {"name": "Netflix", "url": f"https://www.netflix.com/search?q={q_enc}", "color": "from-red-600 to-rose-700", "icon": "film"},
            {"name": "Viu (ซีรีส์เกาหลี/เอเชีย)", "url": f"https://www.viu.com/ott/th/th/search/{q_enc}", "color": "from-amber-500 to-yellow-600", "icon": "tv"},
            {"name": "Disney+ Hotstar", "url": f"https://www.hotstar.com/th/search?q={q_enc}", "color": "from-blue-600 to-indigo-800", "icon": "play-circle"},
            {"name": "Prime Video", "url": f"https://www.primevideo.com/search/ref=atv_nb_sr?phrase={q_enc}", "color": "from-sky-500 to-cyan-600", "icon": "globe"},
            {"name": "HBO GO / Max", "url": f"https://www.hbogo.co.th/search/{q_enc}", "color": "from-purple-600 to-indigo-700", "icon": "play"}
        ]

        img = show.get("image") or {}
        cover = img.get("original") or img.get("medium") or ""

        result = {
            "metadata": {
                "id": f"tv_{series_id}",
                "title_english": title,
                "title_romaji": title,
                "title_native": "",
                "format": fmt_label,
                "status": show.get("status", ""),
                "episodes": total,
                "score": int(show.get("rating", {}).get("average", 0) * 10) if show.get("rating", {}).get("average") else None,
                "year": show.get("premiered", "")[:4] if show.get("premiered") else "",
                "cover_image": cover,
                "banner_image": cover,
                "description": clean_html(show.get("summary")),
                "genres": show.get("genres", [])
            },
            "stats": {
                "total_episodes": total,
                "canon_count": canon_count,
                "mixed_count": 0,
                "filler_count": filler_count,
                "filler_percentage": filler_pct,
                "time_saved_hours": time_saved_hours,
                "watch_ranges": [f"1-{total}"],
                "skip_ranges": [],
                "source": "TVMaze (Live-Action Global)"
            },
            "ai_analysis": {
                "verdict": verdict,
                "action_plan": "ดูเรียงตามลำดับตอนในแต่ละซีซันได้เลย",
                "time_saved_display": f"{time_saved_hours} ชม.",
                "filler_rate_display": f"{filler_pct}%",
                "quick_watch_string": f"1-{total}",
                "quick_skip_string": "ไม่มี"
            },
            "arcs": arcs,
            "episodes": episodes,
            "streaming_links": streaming_links
        }

        # Cache in SQLite
        set_cached_anime(cache_key, title, result)
        return result

    except Exception as e:
        print(f"Error fetching TVMaze guide for series {series_id}: {e}")
    return None
