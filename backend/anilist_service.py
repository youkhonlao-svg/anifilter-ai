import re
import requests
import unicodedata
from typing import List, Dict, Any, Optional
from backend.database import get_cached_anime, set_cached_anime

ANILIST_API_URL = "https://graphql.anilist.co"

def clean_diacritics(text: str) -> str:
    """Normalize text by converting macrons (ū->u, ō->o) and removing accents/diacritics."""
    if not text:
        return ""
    rep = {
        'ū': 'u', 'Ū': 'U',
        'ō': 'o', 'Ō': 'O',
        'ā': 'a', 'Ā': 'A',
        'ī': 'i', 'Ī': 'I',
        'ē': 'e', 'Ē': 'E',
    }
    for k, v in rep.items():
        text = text.replace(k, v)
    normalized = unicodedata.normalize('NFKD', text)
    return ''.join(c for c in normalized if not unicodedata.combining(c))

SEARCH_QUERY = """
query ($search: String) {
  Page(page: 1, perPage: 10) {
    media(search: $search, type: ANIME, sort: SEARCH_MATCH) {
      id
      title { romaji english native }
      format
      episodes
      status
      description(asHtml: false)
      bannerImage
      coverImage { large medium }
      genres
      averageScore
      seasonYear
    }
  }
}
"""

DETAILS_QUERY = """
query ($id: Int) {
  Media(id: $id, type: ANIME) {
    id
    title { romaji english native }
    format
    episodes
    status
    description(asHtml: false)
    bannerImage
    coverImage { large extraLarge }
    genres
    averageScore
    seasonYear
    startDate { year month day }
    relations {
      edges {
        relationType
        node {
          id
          title { romaji english }
          format
          type
          episodes
          status
          coverImage { medium }
        }
      }
    }
  }
}
"""

# ── Relation type → classification ─────────────────────────────────────────
# relationType values from AniList: SOURCE, MANGA, PREQUEL, SEQUEL, PARENT,
# SIDE_STORY, CHARACTER, SUMMARY, OTHER, ALTERNATIVE, SPIN_OFF, ADAPTATION
RELATION_GUIDE = {
    "SEQUEL":      ("sequel",     "ภาคต่อ",              "ดูหลังจบซีรีส์นี้",                "blue"),
    "PREQUEL":     ("prequel",    "ภาคก่อน",             "ดูก่อนเรื่องนี้",                  "blue"),
    "SIDE_STORY":  ("side_story", "เรื่องราวเสริม",      "⭐ แนะนำดู — เชื่อมกับเนื้อหลัก", "gold"),
    "SUMMARY":     ("summary",    "ตอนสรุป/รวมฉาก",     "⏭️ ข้ามได้ — เป็น recap เท่านั้น", "red"),
    "OTHER":       ("other",      "ตอนพิเศษอื่น",        "🎲 เลือกดูได้ตามอัธยาศัย",         "yellow"),
    "CHARACTER":   ("character",  "ตอนเน้นตัวละคร",     "🎲 เลือกดูได้ตามอัธยาศัย",         "yellow"),
    "ALTERNATIVE": ("alt",        "ไทม์ไลน์ทางเลือก",   "🌀 ดูแยก ไม่เชื่อมเนื้อหลัก",      "purple"),
    "SPIN_OFF":    ("spinoff",    "ภาคแยก (Spin-off)",   "🌀 ดูแยก ไม่เชื่อมเนื้อหลัก",      "purple"),
    "ADAPTATION":  ("adapt",      "เวอร์ชันดัดแปลง",    "📺 เวอร์ชันต่าง — ดูแยก",           "gray"),
    "PARENT":      ("parent",     "เรื่องหลัก",          "📖 ดูเรื่องหลักก่อน",               "gray"),
    "SOURCE":      ("source",     "ต้นฉบับ",             "📚 ต้นฉบับ (มังงะ/นิยาย)",          "gray"),
    "MANGA":       ("manga",      "มังงะต้นฉบับ",        "📚 มังงะต้นฉบับ",                   "gray"),
}

FORMAT_LABELS = {
    "TV": "TV Anime",
    "TV_SHORT": "TV Short",
    "MOVIE": "Movie",
    "SPECIAL": "Special",
    "OVA": "OVA",
    "ONA": "ONA",
    "MUSIC": "Music",
}

def search_anime(query: str) -> List[Dict[str, Any]]:
    """Search AniList for anime matching query, with automatic diacritic normalization."""
    clean_q = clean_diacritics(query).strip()
    try:
        response = requests.post(
            ANILIST_API_URL,
            json={"query": SEARCH_QUERY, "variables": {"search": clean_q or query}},
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            media_list = data.get("data", {}).get("Page", {}).get("media", [])
            results = []
            for m in media_list:
                results.append({
                    "id": m["id"],
                    "media_type": "anime",
                    "title_romaji": m["title"]["romaji"] or "",
                    "title_english": m["title"]["english"] or m["title"]["romaji"] or "",
                    "title_native": m["title"]["native"] or "",
                    "episodes": m.get("episodes"),
                    "format": m.get("format"),
                    "status": m.get("status"),
                    "score": m.get("averageScore"),
                    "year": m.get("seasonYear"),
                    "cover_image": m.get("coverImage", {}).get("large"),
                    "banner_image": m.get("bannerImage"),
                    "description": m.get("description", ""),
                    "genres": m.get("genres", []),
                })
            return results
    except Exception as e:
        print(f"Error searching AniList: {e}")
    return []

def get_anime_details(anime_id: int) -> Optional[Dict[str, Any]]:
    """Get detailed anime metadata by AniList ID (uses SQLite cache)."""
    cached = get_cached_anime(anime_id)
    if cached:
        return cached
    try:
        response = requests.post(
            ANILIST_API_URL,
            json={"query": DETAILS_QUERY, "variables": {"id": anime_id}},
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            media = data.get("data", {}).get("Media")
            if media:
                title = (media.get("title") or {}).get("english") or (media.get("title") or {}).get("romaji") or ""
                set_cached_anime(anime_id, title, media)
                return media
    except Exception as e:
        print(f"Error fetching AniList details: {e}")
    return None

def classify_related_content(relations_edges: List[Dict]) -> List[Dict]:
    """
    Parse AniList relations edges into a classified list of related content.
    Each item tells the user whether to watch, skip, or choose.
    """
    related = []
    for edge in (relations_edges or []):
        rel_type = edge.get("relationType", "OTHER")
        node = edge.get("node", {})

        # Only include ANIME-type relations (skip manga, source, etc.)
        node_type = node.get("type", "")
        node_format = node.get("format", "")
        if node_type not in ("ANIME",) and rel_type not in ("SEQUEL", "PREQUEL", "SIDE_STORY", "SUMMARY", "CHARACTER", "OTHER", "ALTERNATIVE", "SPIN_OFF"):
            continue

        # Skip non-anime formats
        if node_format in ("MANGA", "NOVEL", "ONE_SHOT", "MUSIC"):
            continue

        guide = RELATION_GUIDE.get(rel_type, ("other", "เนื้อหาที่เกี่ยวข้อง", "🎲 เลือกดูได้", "yellow"))
        kind, thai_label, rec_text, color = guide

        title_en = (node.get("title") or {}).get("english") or ""
        title_ro = (node.get("title") or {}).get("romaji") or ""
        display_title = title_en or title_ro

        ep_count = node.get("episodes")
        fmt = FORMAT_LABELS.get(node_format, node_format or "Anime")
        cover = (node.get("coverImage") or {}).get("medium") or ""

        related.append({
            "id": node.get("id"),
            "relation_type": rel_type,
            "kind": kind,
            "thai_label": thai_label,
            "title": display_title,
            "title_romaji": title_ro,
            "format": fmt,
            "episodes": ep_count,
            "status": node.get("status", ""),
            "cover_image": cover,
            "recommendation": rec_text,
            "badge_color": color,
            # Is this content important for understanding the main story?
            "important": rel_type in ("SEQUEL", "PREQUEL", "SIDE_STORY"),
        })

    # Sort: important first (PREQUEL, SIDE_STORY), then SEQUEL, then rest
    order = {"PREQUEL": 0, "SIDE_STORY": 1, "SEQUEL": 2, "SUMMARY": 3,
             "CHARACTER": 4, "OTHER": 5, "ALTERNATIVE": 6, "SPIN_OFF": 7, "ADAPTATION": 8}
    related.sort(key=lambda r: order.get(r["relation_type"], 99))
    return related
