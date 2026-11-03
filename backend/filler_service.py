import re
import requests
from bs4 import BeautifulSoup
from typing import Dict, List, Any, Optional
from backend.database import get_cached_filler, set_cached_filler

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
}

_SHOWS_CACHE: Dict[str, str] = {}   # normalized_title → slug
_SLUG_CACHE: Dict[str, bool] = {}   # slug → exists?

# ── Manual overrides for titles that don't match automatically ──────────────
TITLE_SLUG_MAP = {
    "naruto": "naruto",
    "naruto shippuden": "naruto-shippuden",
    "bleach": "bleach",
    "one piece": "one-piece",
    "dragon ball z": "dragon-ball-z",
    "dragon ball super": "dragon-ball-super",
    "dragon ball gt": "dragon-ball-gt",
    "fairy tail": "fairy-tail",
    "inuyasha": "inuyasha",
    "pokemon": "pokemon",
    "hunter x hunter": "hunter-x-hunter",
    "fullmetal alchemist": "fullmetal-alchemist",
    "fullmetal alchemist brotherhood": "fullmetal-alchemist-brotherhood",
    "sword art online": "sword-art-online",
    "sword art online ii": "sword-art-online-ii",
    "black clover": "black-clover",
    "boruto naruto next generations": "boruto-naruto-next-generations",
    "boruto: naruto next generations": "boruto-naruto-next-generations",
    "yu yu hakusho": "yu-yu-hakusho",
    "yu-yu-hakusho": "yu-yu-hakusho",
    "saint seiya": "saint-seiya",
    "rurouni kenshin": "rurouni-kenshin",
    "gintama": "gintama",
    "toaru majutsu no index": "a-certain-magical-index",
    "a certain magical index": "a-certain-magical-index",
    "soul eater": "soul-eater",
    "katekyo hitman reborn": "katekyo-hitman-reborn",
    "reborn!": "katekyo-hitman-reborn",
    "d.gray-man": "d-gray-man",
    "d gray man": "d-gray-man",
    "the promised neverland": "the-promised-neverland",
    "shokugeki no souma": "food-wars-shokugeki-no-soma",
    "food wars": "food-wars-shokugeki-no-soma",
}

def _normalize(text: str) -> str:
    """Normalize a title for comparison."""
    return re.sub(r"[^a-z0-9\s]", "", text.lower()).strip()

def _to_slug(text: str) -> str:
    """Convert a title to a slug format."""
    clean = re.sub(r"[^a-z0-9\s-]", "", text.lower())
    return re.sub(r"\s+", "-", clean.strip())

def get_shows_index() -> Dict[str, str]:
    """Fetch and cache the AnimeFillerList shows index."""
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
                    # Store multiple normalized versions
                    norm = _normalize(title)
                    cache[norm] = slug
                    cache[_normalize(title.replace(":", ""))] = slug
                    cache[_normalize(re.sub(r"\bthe\b", "", title))] = slug
            _SHOWS_CACHE = cache
            return _SHOWS_CACHE
    except Exception as e:
        print(f"Error fetching shows index: {e}")
    return {}

def _slug_exists(slug: str) -> bool:
    """Check if a slug actually exists on AnimeFillerList (with cache)."""
    if slug in _SLUG_CACHE:
        return _SLUG_CACHE[slug]
    try:
        resp = requests.head(
            f"https://www.animefillerlist.com/shows/{slug}",
            headers=HEADERS, timeout=5, allow_redirects=True
        )
        exists = resp.status_code == 200
        _SLUG_CACHE[slug] = exists
        return exists
    except Exception:
        return False

def find_best_slug(title: str, alt_titles: List[str] = None) -> Optional[str]:
    """Find the best matching AnimeFillerList slug for an anime title."""
    candidates = [title] + (alt_titles or [])

    # 1. Check manual overrides first
    for c in candidates:
        if not c:
            continue
        norm = _normalize(c)
        if norm in TITLE_SLUG_MAP:
            return TITLE_SLUG_MAP[norm]
        # Also try without articles and special chars
        clean = _normalize(re.sub(r"\b(the|a|an)\b", "", norm))
        if clean in TITLE_SLUG_MAP:
            return TITLE_SLUG_MAP[clean]

    # 2. Check AnimeFillerList index (fetched from their website)
    shows = get_shows_index()
    for c in candidates:
        if not c:
            continue
        variants = [
            _normalize(c),
            _normalize(re.sub(r"\b(the|a|an)\b", "", c)),
            _normalize(re.sub(r"[^a-z0-9\s]", "", c.lower())),
            _normalize(c.replace(":", "").replace("-", " ")),
        ]
        for v in variants:
            if v in shows:
                return shows[v]
            # Substring match
            for show_norm, slug in shows.items():
                if len(v) > 4 and (v in show_norm or show_norm in v):
                    return slug

    # 3. Try constructing a slug directly and verify it exists
    for c in candidates:
        if not c:
            continue
        slug = _to_slug(re.sub(r"[^a-z0-9\s-]", "", c.lower()))
        if slug and _slug_exists(slug):
            return slug

    return None

def get_episodes_from_filler_list(slug: str) -> Optional[Dict[str, Any]]:
    """Fetch episode list from AnimeFillerList (with SQLite cache)."""
    cached = get_cached_filler(slug)
    if cached:
        return cached

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
        for row in table.select("tr"):
            tds = row.find_all("td")
            if len(tds) < 3:
                continue
            ep_num_str = tds[0].get_text(strip=True)
            ep_title    = tds[1].get_text(strip=True)
            ep_type_raw = tds[2].get_text(strip=True)
            air_date    = tds[3].get_text(strip=True) if len(tds) > 3 else ""

            try:
                ep_num = int(ep_num_str)
            except ValueError:
                continue

            t = ep_type_raw.lower()
            if "manga canon" in t:
                canonical_type = "Manga Canon"
                badge = "canon"
                watch_rec = "MUST_WATCH"
            elif "mixed" in t:
                canonical_type = "Mixed Canon/Filler"
                badge = "mixed"
                watch_rec = "RECOMMENDED"
            elif "anime canon" in t:
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
                "air_date": air_date,
                "summary": ""
            })

        if not episodes:
            return None

        total = len(episodes)
        canon_count = sum(1 for e in episodes if e["badge"] in ("canon", "anime_canon"))
        mixed_count = sum(1 for e in episodes if e["badge"] == "mixed")
        filler_count = sum(1 for e in episodes if e["badge"] == "filler")

        watch_ranges = _compute_ranges(episodes, exclude_badge="filler")
        skip_ranges  = _compute_ranges(episodes, include_only_badge="filler")

        time_saved_hours = round((filler_count * 22) / 60, 1)

        result = {
            "source": "AnimeFillerList",
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
        set_cached_filler(slug, result)
        return result

    except Exception as e:
        print(f"Error scraping AnimeFillerList for {slug}: {e}")
    return None

def _compute_ranges(episodes: List[Dict], exclude_badge: str = None,
                    include_only_badge: str = None) -> List[str]:
    """Compute compact range strings like ['1-19', '21', '25-30']."""
    nums = set()
    for ep in episodes:
        if exclude_badge and ep["badge"] == exclude_badge:
            continue
        if include_only_badge and ep["badge"] != include_only_badge:
            continue
        nums.add(ep["number"])

    if not nums:
        return []

    sorted_nums = sorted(nums)
    ranges = []
    start = prev = sorted_nums[0]
    for n in sorted_nums[1:]:
        if n == prev + 1:
            prev = n
        else:
            ranges.append(str(start) if start == prev else f"{start}-{prev}")
            start = prev = n
    ranges.append(str(start) if start == prev else f"{start}-{prev}")
    return ranges

def generate_smart_episodes(ep_count: Optional[int], title: str,
                             fmt: str = "TV") -> Dict[str, Any]:
    """
    Generate episode data for anime NOT in AnimeFillerList.
    Uses format + episode count to give smarter guidance.
    """
    count = ep_count if ep_count and ep_count > 0 else 12
    fmt = (fmt or "TV").upper()

    # Determine if this format can have filler at all
    no_filler_formats = {"MOVIE", "OVA", "SPECIAL", "ONA", "TV_SHORT", "MUSIC"}
    if fmt in no_filler_formats:
        note = _format_note(fmt, count)
        episodes = _all_canon(count, fmt)
        return {
            "source": f"AniList ({FORMAT_LABELS.get(fmt, fmt)} — No Filler Data Needed)",
            "total_episodes": count,
            "canon_count": count,
            "mixed_count": 0,
            "filler_count": 0,
            "filler_percentage": 0.0,
            "time_saved_hours": 0.0,
            "watch_ranges": [f"1-{count}" if count > 1 else "1"],
            "skip_ranges": [],
            "episodes": episodes,
            "note": note,
        }

    # TV anime: episode count guides assumption
    if count <= 26:
        # Short/seasonal TV anime — almost always all-canon, no filler
        note = (
            f"🎯 อนิเมะ {count} ตอน (**{_ep_label(count)}**) — "
            f"อนิเมะขนาดสั้นถึงกลางมักไม่มีตอน Filler ระบบแนะนำดูครบทุกตอน "
            f"(ไม่พบข้อมูล Filler อย่างเป็นทางการใน AnimeFillerList)"
        )
        return {
            "source": "AniList (TV Anime — Short/Seasonal, Assumed All-Canon)",
            "total_episodes": count,
            "canon_count": count,
            "mixed_count": 0,
            "filler_count": 0,
            "filler_percentage": 0.0,
            "time_saved_hours": 0.0,
            "watch_ranges": [f"1-{count}" if count > 1 else "1"],
            "skip_ranges": [],
            "episodes": _all_canon(count, "TV"),
            "note": note,
        }
    else:
        # Long-running TV anime — may have filler but we don't have exact data
        note = (
            f"⚠️ อนิเมะ {count} ตอน (**ยาว**) — "
            f"ระบบไม่พบข้อมูล Filler อย่างเป็นทางการใน AnimeFillerList สำหรับเรื่องนี้ "
            f"แสดงผลตอนทั้งหมดเป็น Canon (อาจมี Filler บ้าง แต่ไม่มีข้อมูลยืนยัน) "
            f"แนะนำดูเรียงตามลำดับและข้ามเฉพาะตอนที่รู้สึกว่าหลุดจากเนื้อเรื่องหลัก"
        )
        return {
            "source": "AniList (TV Anime — Long-Running, No Filler Data Found)",
            "total_episodes": count,
            "canon_count": count,
            "mixed_count": 0,
            "filler_count": 0,
            "filler_percentage": 0.0,
            "time_saved_hours": 0.0,
            "watch_ranges": [f"1-{count}"],
            "skip_ranges": [],
            "episodes": _all_canon(count, "TV"),
            "note": note,
        }

def _all_canon(count: int, fmt: str) -> List[Dict]:
    """Generate a list of all-canon episodes."""
    label = FORMAT_LABELS.get(fmt, "Episode")
    return [
        {
            "number": i,
            "title": f"{label} {i}",
            "type": "Canon",
            "badge": "canon",
            "watch_recommendation": "MUST_WATCH",
            "air_date": "",
            "summary": ""
        }
        for i in range(1, count + 1)
    ]

def _ep_label(count: int) -> str:
    if count <= 13:  return "1 คูร์"
    if count <= 26:  return "2 คูร์"
    if count <= 52:  return "4 คูร์"
    return "Long-Running"

def _format_note(fmt: str, count: int) -> str:
    notes = {
        "MOVIE": "🎬 ภาพยนตร์อนิเมะ — ดูได้เลย ไม่มี Filler",
        "OVA":   f"📀 OVA {count} ตอน — ตอนพิเศษที่ผลิตแยกจาก TV Series ดูหลังจบ TV หลักครับ",
        "SPECIAL": f"⭐ Special {count} ตอน — ตอนพิเศษ ดูได้ตามอัธยาศัย",
        "ONA":   f"🌐 ONA {count} ตอน — ออกอากาศออนไลน์ ดูได้เรียงตามลำดับ",
        "TV_SHORT": f"📺 TV Short {count} ตอน — ตอนสั้น ดูได้ทั้งหมด",
    }
    return notes.get(fmt, f"✅ {count} ตอน — ดูครบทุกตอนได้เลย")

# Backward-compatible alias
FORMAT_LABELS = {
    "TV": "TV Anime",
    "TV_SHORT": "TV Short",
    "MOVIE": "Movie",
    "SPECIAL": "Special",
    "OVA": "OVA",
    "ONA": "ONA",
    "MUSIC": "Music",
}

# Legacy alias so main.py doesn't break
def generate_default_episodes(ep_count, title, fmt="TV"):
    return generate_smart_episodes(ep_count, title, fmt)
