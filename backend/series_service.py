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

# Keywords that mark an episode as a special/bonus — not main story
SPECIAL_KEYWORDS = [
    "recap", "behind the scenes", "making of", "interview",
    "inside the episode", "the story so far", "previously on",
    "last watch", "conquest & rebellion", "animated history",
    "documentary", "featurette", "preview", "first look",
    "web exclusive", "bonus", "extended", "sneak peek",
    "fan questions", "cast", "showrunner"
]

def clean_html(text: Optional[str]) -> str:
    if not text:
        return ""
    return re.sub(r"<[^>]*>", "", text).strip()

def is_special_episode(ep: dict) -> bool:
    """Detect if an episode is a special/bonus rather than main story."""
    season_num = ep.get("season", 1)
    ep_num = ep.get("number")  # None = specials in TVMaze
    name = (ep.get("name") or "").lower()

    # TVMaze uses season=0 OR number=None for specials
    if season_num == 0 or ep_num is None:
        return True

    # Name-based detection
    for kw in SPECIAL_KEYWORDS:
        if kw in name:
            return True

    return False

def search_live_action_series(query: str) -> List[Dict[str, Any]]:
    """Search TVMaze for live-action TV series (Korean, Japanese, US, etc.). Excludes anime/animation."""
    try:
        url = f"{TVMAZE_API_URL}/search/shows?q={urllib.parse.quote(query)}"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            results = []
            for item in resp.json():
                show = item.get("show", {})
                
                # Exclude anime and animation from live-action series search
                show_type = (show.get("type") or "").lower()
                genres = [g.lower() for g in show.get("genres", [])]
                if show_type == "animation" or "anime" in genres:
                    continue

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
                    "episodes": None,
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
    """Get complete episode guide for a live-action series with correct season grouping."""
    cache_key = 9000000 + series_id
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

        # 2. Fetch Episodes with specials=1 so we know what to exclude
        url_eps = f"{TVMAZE_API_URL}/shows/{series_id}/episodes?specials=1"
        resp_eps = requests.get(url_eps, timeout=10)
        if resp_eps.status_code != 200:
            return None
        raw_eps = resp_eps.json()

        # ── Pass 1: Build episode list with correct absolute numbering ──
        # Main episodes (season >= 1, number not None) get sequential absolute numbers
        # Specials are collected separately

        main_episodes = []
        special_episodes = []

        for ep in raw_eps:
            if is_special_episode(ep):
                special_episodes.append(ep)
            else:
                main_episodes.append(ep)

        # Sort main episodes by (season, episode number)
        main_episodes.sort(key=lambda e: (e.get("season", 1), e.get("number", 0)))

        # Build processed episode list with absolute numbering
        episodes = []
        abs_num = 0

        for ep in main_episodes:
            abs_num += 1
            season_num = ep.get("season", 1)
            ep_in_season = ep.get("number", abs_num)
            ep_name = ep.get("name") or f"Episode {ep_in_season}"

            episodes.append({
                "number": abs_num,
                "season": season_num,
                "episode_in_season": ep_in_season,
                "title": f"S{season_num}E{ep_in_season}: {ep_name}",
                "type": f"Season {season_num} Main Story",
                "badge": "canon",
                "watch_recommendation": "MUST_WATCH",
                "air_date": ep.get("airdate", ""),
                "summary": clean_html(ep.get("summary"))
            })

        # Add specials at the end with their own numbering
        special_abs = abs_num
        for ep in special_episodes:
            special_abs += 1
            season_num = ep.get("season", 0)
            ep_in_season = ep.get("number") or 0
            ep_name = ep.get("name") or "Special"

            episodes.append({
                "number": special_abs,
                "season": season_num,
                "episode_in_season": ep_in_season,
                "title": f"Special: {ep_name}",
                "type": "Special / Recap (ตอนพิเศษ/ย้อนความ)",
                "badge": "filler",
                "watch_recommendation": "SKIP",
                "air_date": ep.get("airdate", ""),
                "summary": clean_html(ep.get("summary"))
            })

        canon_count = len(main_episodes)
        filler_count = len(special_episodes)
        total = len(episodes)
        filler_pct = round((filler_count / total) * 100, 1) if total > 0 else 0
        time_saved_hours = round((filler_count * 50) / 60, 1)

        # ── Pass 2: Build Season Arcs from MAIN episodes only ──
        seasons_map: Dict[int, List] = {}
        for ep in episodes:
            if ep["badge"] == "canon":
                s_num = ep["season"]
                if s_num not in seasons_map:
                    seasons_map[s_num] = []
                seasons_map[s_num].append(ep)

        arcs = []
        for s_num, s_eps in sorted(seasons_map.items()):
            first_abs = s_eps[0]["number"]
            last_abs = s_eps[-1]["number"]
            first_in_season = s_eps[0]["episode_in_season"]
            last_in_season = s_eps[-1]["episode_in_season"]
            s_label = f"ซีซัน {s_num} (Season {s_num})"

            arcs.append({
                "arc_number": s_num,
                "title": s_label,
                "range_display": f"ตอนที่ {first_abs}–{last_abs}  (S{s_num}E{first_in_season}–E{last_in_season})",
                "start_ep": first_abs,
                "end_ep": last_abs,
                "episodes_count": len(s_eps),
                "status_label": "เนื้อเรื่องหลัก (Canon)",
                "recommendation": "ต้องดู (Must Watch)",
                "badge_color": "green",
                "is_filler": False,
                "description": f"เนื้อเรื่องหลักซีซัน {s_num} รวม {len(s_eps)} ตอน  (ตอน {first_abs}–{last_abs})",
                "sample_episodes": s_eps[:3]
            })

        # Add specials arc if any
        if special_episodes:
            spec_eps_processed = [e for e in episodes if e["badge"] == "filler"]
            arcs.append({
                "arc_number": 0,
                "title": "ตอนพิเศษ / เบื้องหลัง (Specials)",
                "range_display": f"Special ({filler_count} ตอน)",
                "start_ep": abs_num + 1,
                "end_ep": total,
                "episodes_count": filler_count,
                "status_label": "ตอนเสริมพิเศษ (Special/Recap)",
                "recommendation": "เลือกดูได้ (Optional)",
                "badge_color": "yellow",
                "is_filler": True,
                "description": f"ตอนพิเศษ สารคดีเบื้องหลัง และตอนย้อนความ {filler_count} ตอน",
                "sample_episodes": spec_eps_processed[:3]
            })

        # ── Build accurate watch/skip ranges ──
        watch_ranges = []
        skip_ranges = []
        if canon_count > 0:
            watch_ranges.append(f"1–{canon_count}")
        if filler_count > 0:
            skip_ranges.append(f"Specials ({filler_count} ตอน)")

        # Network / format
        network = show.get("network") or show.get("webChannel") or {}
        country_code = ""
        if isinstance(network, dict):
            country_info = network.get("country") or {}
            country_code = country_info.get("code", "")
        fmt_label = COUNTRY_MAP.get(country_code, "TV SERIES")

        title = show.get("name", "")

        # AI Verdict
        if filler_count == 0:
            verdict = (
                f"🎬 **{title}** เป็นซีรีส์เนื้อเรื่องต่อเนื่อง 100% — ทั้งหมด {canon_count} ตอน "
                f"ใน {len(arcs)} ซีซัน ไม่มีตอน Filler หรือตอนย้อนความ "
                f"แนะนำดูเรียงลำดับตั้งแต่ตอนที่ 1 จนจบ!"
            )
        else:
            verdict = (
                f"🎬 **{title}** มีเนื้อเรื่องหลัก **{canon_count} ตอน** ใน {len(seasons_map)} ซีซัน "
                f"และตอนพิเศษ/เบื้องหลัง {filler_count} ตอน (ข้ามได้) "
                f"ประหยัดเวลาได้ {time_saved_hours} ชั่วโมง"
            )

        action_plan = (
            f"ดูเรียงตาม {len(arcs)} ซีซัน (ตอนที่ 1–{canon_count}) "
            f"{'| ข้าม Specials ได้ทั้งหมด' if filler_count > 0 else '| ดูครบทุกตอนได้เลย!'}"
        )

        # Streaming links
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
                "episodes": canon_count,   # Show MAIN episode count, not including specials
                "score": int(show.get("rating", {}).get("average", 0) * 10) if show.get("rating", {}).get("average") else None,
                "year": show.get("premiered", "")[:4] if show.get("premiered") else "",
                "cover_image": cover,
                "banner_image": cover,
                "description": clean_html(show.get("summary")),
                "genres": show.get("genres", [])
            },
            "stats": {
                "total_episodes": canon_count,    # Main episodes only
                "total_with_specials": total,     # Including specials
                "canon_count": canon_count,
                "mixed_count": 0,
                "filler_count": filler_count,
                "filler_percentage": filler_pct,
                "time_saved_hours": time_saved_hours,
                "watch_ranges": watch_ranges,
                "skip_ranges": skip_ranges,
                "source": "TVMaze (Live-Action Global)"
            },
            "ai_analysis": {
                "verdict": verdict,
                "action_plan": action_plan,
                "time_saved_display": f"{time_saved_hours} ชม.",
                "filler_rate_display": f"{filler_pct}%",
                "quick_watch_string": f"1–{canon_count}",
                "quick_skip_string": f"Specials {filler_count} ตอน" if filler_count > 0 else "ไม่มี"
            },
            "arcs": arcs,
            "episodes": episodes,
            "streaming_links": streaming_links
        }

        set_cached_anime(cache_key, title, result)
        return result

    except Exception as e:
        print(f"Error fetching TVMaze guide for series {series_id}: {e}")
    return None
