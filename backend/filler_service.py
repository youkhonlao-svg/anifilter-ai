import re
import requests
from bs4 import BeautifulSoup
from typing import Dict, List, Any, Optional
from backend.database import get_cached_filler, set_cached_filler

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

_SHOWS_CACHE: Dict[str, str] = {}  # title_lower -> slug or url

def get_shows_index() -> Dict[str, str]:
    """Fetch and cache list of shows from AnimeFillerList."""
    global _SHOWS_CACHE
    if _SHOWS_CACHE:
        return _SHOWS_CACHE

    url = "https://www.animefillerlist.com/shows"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            links = soup.select("#ShowList a, div.view-shows a, div.Group a")
            cache = {}
            for a in links:
                title = a.get_text(strip=True)
                href = a.get("href", "")
                if "/shows/" in href:
                    slug = href.split("/shows/")[-1].strip("/")
                    cache[title.lower()] = slug
                    clean_title = re.sub(r"[^a-zA-Z0-9\s]", "", title).lower()
                    cache[clean_title] = slug
            _SHOWS_CACHE = cache
            return _SHOWS_CACHE
    except Exception as e:
        print(f"Error fetching shows index: {e}")
    return {}

def find_best_slug(title: str, alt_titles: List[str] = None) -> Optional[str]:
    """Find matching slug for anime title."""
    shows = get_shows_index()
    candidates = [title] + (alt_titles or [])

    for c in candidates:
        if not c:
            continue
        c_low = c.lower().strip()
        c_clean = re.sub(r"[^a-zA-Z0-9\s]", "", c_low)

        if c_low in shows:
            return shows[c_low]
        if c_clean in shows:
            return shows[c_clean]

        direct_slug = re.sub(r"\s+", "-", re.sub(r"[^a-zA-Z0-9\s-]", "", c_low))
        if direct_slug in shows.values():
            return direct_slug

    for c in candidates:
        if not c:
            continue
        c_low = c.lower().strip()
        for show_title, slug in shows.items():
            if c_low in show_title or show_title in c_low:
                return slug

    clean = re.sub(r"[^a-zA-Z0-9\s-]", "", title.lower())
    return re.sub(r"\s+", "-", clean.strip())

def get_episodes_from_filler_list(slug: str) -> Optional[Dict[str, Any]]:
    """Fetch episode list and classifications (uses SQLite cache for instant load)."""
    # 1. Check SQLite database cache first
    cached = get_cached_filler(slug)
    if cached:
        return cached

    # 2. Scrape live from AnimeFillerList
    url = f"https://www.animefillerlist.com/shows/{slug}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        if resp.status_code != 200:
            return None

        soup = BeautifulSoup(resp.text, "html.parser")
        table = soup.select_one("table.EpisodeList")
        if not table:
            return None

        episodes = []
        rows = table.select("tr")
        for row in rows:
            tds = row.find_all("td")
            if len(tds) < 3:
                continue

            ep_num_str = tds[0].get_text(strip=True)
            ep_title = tds[1].get_text(strip=True)
            ep_type_raw = tds[2].get_text(strip=True)
            air_date = tds[3].get_text(strip=True) if len(tds) > 3 else ""

            try:
                ep_num = int(ep_num_str)
            except ValueError:
                continue

            ep_type_lower = ep_type_raw.lower()
            if "manga canon" in ep_type_lower:
                canonical_type = "Manga Canon"
                badge = "canon"
                watch_rec = "MUST_WATCH"
            elif "mixed" in ep_type_lower:
                canonical_type = "Mixed Canon/Filler"
                badge = "mixed"
                watch_rec = "RECOMMENDED"
            elif "anime canon" in ep_type_lower:
                canonical_type = "Anime Canon"
                badge = "anime_canon"
                watch_rec = "RECOMMENDED"
            else:
                canonical_type = "Filler"
                badge = "filler"
                watch_rec = "SKIP"

            episodes.append({
                "number": ep_num,
                "title": ep_title,
                "type": canonical_type,
                "badge": badge,
                "watch_recommendation": watch_rec,
                "air_date": air_date
            })

        if not episodes:
            return None

        total = len(episodes)
        canon_count = sum(1 for e in episodes if e["badge"] in ("canon", "anime_canon"))
        mixed_count = sum(1 for e in episodes if e["badge"] == "mixed")
        filler_count = sum(1 for e in episodes if e["badge"] == "filler")

        # Compute watch ranges
        watch_ranges = []
        start = None
        prev = None
        watchable_set = set(e["number"] for e in episodes if e["badge"] != "filler")

        for i in range(1, total + 1):
            if i in watchable_set:
                if start is None:
                    start = i
                prev = i
            else:
                if start is not None:
                    watch_ranges.append(f"{start}" if start == prev else f"{start}-{prev}")
                    start = None
                    prev = None
        if start is not None:
            watch_ranges.append(f"{start}" if start == prev else f"{start}-{prev}")

        # Compute skip ranges
        skip_ranges = []
        start = None
        prev = None
        filler_set = set(e["number"] for e in episodes if e["badge"] == "filler")

        for i in range(1, total + 1):
            if i in filler_set:
                if start is None:
                    start = i
                prev = i
            else:
                if start is not None:
                    skip_ranges.append(f"{start}" if start == prev else f"{start}-{prev}")
                    start = None
                    prev = None
        if start is not None:
            skip_ranges.append(f"{start}" if start == prev else f"{start}-{prev}")

        time_saved_minutes = filler_count * 22
        time_saved_hours = round(time_saved_minutes / 60, 1)

        result = {
            "source": "AnimeFillerList (Cached)",
            "total_episodes": total,
            "canon_count": canon_count,
            "mixed_count": mixed_count,
            "filler_count": filler_count,
            "filler_percentage": round((filler_count / total) * 100, 1) if total > 0 else 0,
            "time_saved_hours": time_saved_hours,
            "watch_ranges": watch_ranges,
            "skip_ranges": skip_ranges,
            "episodes": episodes
        }

        # Save to database cache
        set_cached_filler(slug, result)
        return result

    except Exception as e:
        print(f"Error scraping AnimeFillerList for slug {slug}: {e}")
    return None

def generate_default_episodes(total_episodes: Optional[int], title: str) -> Dict[str, Any]:
    """Fallback generator for anime without filler lists (100% canon/seasonal anime)."""
    count = total_episodes if total_episodes and total_episodes > 0 else 12
    episodes = []
    for i in range(1, count + 1):
        episodes.append({
            "number": i,
            "title": f"Episode {i}",
            "type": "Manga Canon",
            "badge": "canon",
            "watch_recommendation": "MUST_WATCH",
            "air_date": ""
        })

    return {
        "source": "AniList (All Canon)",
        "total_episodes": count,
        "canon_count": count,
        "mixed_count": 0,
        "filler_count": 0,
        "filler_percentage": 0.0,
        "time_saved_hours": 0.0,
        "watch_ranges": [f"1-{count}"] if count > 1 else ["1"],
        "skip_ranges": [],
        "episodes": episodes,
        "note": "เรื่องนี้เป็นอนิเมะที่สร้างตามเนื้อเรื่องหลักทั้งหมด (ไม่มีตอนคั่นหรือ Filler) สามารถดูเรียงตามตอนได้ครบทุกตอนครับ"
    }
