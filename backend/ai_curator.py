import os
import json
import requests
import re
from typing import Dict, Any, List, Optional, Tuple

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# ─────────────────────────────────────────────────────────────────────────────
# Named Story Arc Database
# Each entry: {"name": str, "thai": str, "start": int, "end": int, "icon": str}
# start/end are INCLUSIVE episode numbers from AnimeFillerList
# ─────────────────────────────────────────────────────────────────────────────
NAMED_ARCS: Dict[str, List[Dict]] = {
    "naruto": [
        {"name": "Land of Waves Arc",       "thai": "อาร์คแผ่นดินคลื่น",          "start": 1,   "end": 19,  "icon": "🌊"},
        {"name": "Chunin Exams Arc",         "thai": "อาร์คสอบชูนิน",              "start": 20,  "end": 67,  "icon": "📜"},
        {"name": "Konoha Crush Arc",         "thai": "อาร์คโจมตีโคโนฮะ",          "start": 68,  "end": 80,  "icon": "🔥"},
        {"name": "Tsunade Search Arc",       "thai": "อาร์คตามหาสึนาเดะ",          "start": 81,  "end": 106, "icon": "🃏"},
        {"name": "Sasuke Retrieval Arc",     "thai": "อาร์คตามหาซาสึเกะ",          "start": 107, "end": 135, "icon": "⚔️"},
        {"name": "Filler Block",             "thai": "ช่วง Filler (ข้ามได้)",       "start": 136, "end": 220, "icon": "⏭️"},
    ],
    "naruto shippuden": [
        {"name": "Kazekage Rescue Arc",      "thai": "อาร์คช่วยคาเซคาเกะ",         "start": 1,   "end": 32,  "icon": "🏜️"},
        {"name": "Tenchi Bridge Arc",        "thai": "อาร์คสะพานเทนจิ",            "start": 33,  "end": 71,  "icon": "🌉"},
        {"name": "Immortals Arc",            "thai": "อาร์คอมตะ",                  "start": 72,  "end": 88,  "icon": "💀"},
        {"name": "Three-Tails Arc",          "thai": "อาร์คสัตว์หางสาม (Filler)",  "start": 89,  "end": 112, "icon": "⏭️"},
        {"name": "Six-Tails Arc",            "thai": "อาร์คสัตว์หางหก",            "start": 144, "end": 151, "icon": "🌀"},
        {"name": "Pain's Assault Arc",       "thai": "อาร์คเพนบุกโจมตี",           "start": 152, "end": 175, "icon": "👁️"},
        {"name": "Five Kage Summit Arc",     "thai": "อาร์คประชุมไคเงะห้า",        "start": 197, "end": 214, "icon": "🏔️"},
        {"name": "Fourth Shinobi War Arc",   "thai": "อาร์คสงครามนินจาโลก",        "start": 261, "end": 395, "icon": "⚔️"},
        {"name": "Ten-Tails Revival Arc",    "thai": "อาร์คฟื้นคืนชีพสัตว์หางสิบ", "start": 378, "end": 457, "icon": "🌑"},
        {"name": "Kaguya / Finale Arc",      "thai": "อาร์คคางุยะ (บทสุดท้าย)",   "start": 458, "end": 479, "icon": "🌸"},
    ],
    "bleach": [
        {"name": "Agent of Shinigami Arc",   "thai": "อาร์คตัวแทนชินิงามิ",        "start": 1,   "end": 20,  "icon": "⚔️"},
        {"name": "Soul Society Arc",         "thai": "อาร์คโซลโซไซตี้",            "start": 21,  "end": 63,  "icon": "🏯"},
        {"name": "Bount Arc (Filler)",       "thai": "อาร์ค Bount (Filler)",       "start": 64,  "end": 109, "icon": "⏭️"},
        {"name": "Arrancar Arc",             "thai": "อาร์คอาร์รังการ์",            "start": 110, "end": 167, "icon": "🌑"},
        {"name": "Fake Karakura Town Arc",   "thai": "อาร์คเมืองคาราคุระปลอม",     "start": 190, "end": 212, "icon": "🌆"},
        {"name": "Fullbring Arc",            "thai": "อาร์คฟูลบริง",               "start": 343, "end": 366, "icon": "💎"},
    ],
    "one piece": [
        {"name": "East Blue Arc",            "thai": "อาร์คอีสต์บลู",              "start": 1,   "end": 61,   "icon": "🌊"},
        {"name": "Alabasta Arc",             "thai": "อาร์คอลาบาสต้า",             "start": 62,  "end": 135,  "icon": "🏜️"},
        {"name": "Skypiea Arc",              "thai": "อาร์คสกายเปีย",              "start": 144, "end": 195,  "icon": "☁️"},
        {"name": "Water 7 / Enies Lobby",   "thai": "อาร์ควอเตอร์ 7 / เอนิส์",   "start": 207, "end": 325,  "icon": "🚂"},
        {"name": "Thriller Bark Arc",        "thai": "อาร์คทริลเลอร์บาร์ก",        "start": 326, "end": 384,  "icon": "🎃"},
        {"name": "Sabaody Arc",              "thai": "อาร์คซาบาโอดี้",             "start": 385, "end": 405,  "icon": "🫧"},
        {"name": "Marineford Arc",           "thai": "อาร์คมารีนฟอร์ด (สงครามสูงสุด)", "start": 457, "end": 489, "icon": "🔥"},
        {"name": "Fish-Man Island Arc",      "thai": "อาร์คเกาะปลา",              "start": 517, "end": 574,  "icon": "🐟"},
        {"name": "Dressrosa Arc",            "thai": "อาร์คเดรสโรซ่า",             "start": 629, "end": 746,  "icon": "🌹"},
        {"name": "Whole Cake Island Arc",    "thai": "อาร์ควิลแคคไอแลนด์",        "start": 783, "end": 877,  "icon": "🎂"},
        {"name": "Wano Country Arc",         "thai": "อาร์ควาโนะ",                "start": 890, "end": 1085, "icon": "🗾"},
    ],
    "dragon ball z": [
        {"name": "Saiyan Arc",               "thai": "อาร์คไซยาจิน",               "start": 1,   "end": 35,  "icon": "🌙"},
        {"name": "Namek / Frieza Arc",       "thai": "อาร์คดาวนาเมก / ฟรีซ่า",    "start": 36,  "end": 107, "icon": "🪐"},
        {"name": "Android / Cell Arc",       "thai": "อาร์คแอนดรอยด์ / เซลล์",   "start": 118, "end": 194, "icon": "🤖"},
        {"name": "Majin Buu Arc",            "thai": "อาร์คมาจิน บู",              "start": 200, "end": 291, "icon": "👹"},
    ],
    "dragon ball super": [
        {"name": "Battle of Gods Arc",       "thai": "อาร์คเทพเจ้าแห่งการทำลาย",  "start": 1,   "end": 14,  "icon": "🐱"},
        {"name": "Golden Frieza Arc",        "thai": "อาร์คฟรีซ่าทอง",            "start": 15,  "end": 27,  "icon": "👑"},
        {"name": "Universe 6 Arc",           "thai": "อาร์คจักรวาลที่ 6",          "start": 28,  "end": 46,  "icon": "🥊"},
        {"name": "Future Trunks Arc",        "thai": "อาร์คทรังค์จากอนาคต",       "start": 47,  "end": 76,  "icon": "⏳"},
        {"name": "Tournament of Power Arc",  "thai": "อาร์คศึกพลังสูงสุด",         "start": 77,  "end": 131, "icon": "🏆"},
    ],
    "attack on titan": [
        {"name": "Fall of Shiganshina Arc",  "thai": "อาร์คชิกังชิน่าล่มสลาย",    "start": 1,   "end": 5,   "icon": "🧱"},
        {"name": "Battle of Trost Arc",      "thai": "อาร์คศึกทรอสต์",             "start": 5,   "end": 13,  "icon": "⚔️"},
        {"name": "Female Titan Arc",         "thai": "อาร์คไทแทนหญิง",             "start": 17,  "end": 25,  "icon": "👊"},
        {"name": "Clash of Titans Arc",      "thai": "อาร์คปะทะไทแทน",             "start": 26,  "end": 33,  "icon": "💥"},
        {"name": "Royal Government Arc",     "thai": "อาร์ครัฐบาลราชวงศ์",         "start": 34,  "end": 50,  "icon": "👑"},
        {"name": "Return to Shiganshina",    "thai": "อาร์คกลับชิกังชิน่า",        "start": 50,  "end": 59,  "icon": "🏚️"},
        {"name": "Marley Arc",               "thai": "อาร์คมาร์เลย์",              "start": 60,  "end": 73,  "icon": "🌍"},
        {"name": "War for Paradis Arc",      "thai": "อาร์คสงครามพาราดิส (จบ)",   "start": 74,  "end": 87,  "icon": "🌋"},
    ],
    "fullmetal alchemist brotherhood": [
        {"name": "Introduction Arc",         "thai": "อาร์คเปิดเรื่อง",            "start": 1,   "end": 10,  "icon": "⚗️"},
        {"name": "Dublith Arc",              "thai": "อาร์คดับลิธ",                "start": 11,  "end": 26,  "icon": "🏙️"},
        {"name": "Promised Day Prep Arc",    "thai": "อาร์คเตรียมวันแห่งสัญญา",   "start": 27,  "end": 51,  "icon": "🌟"},
        {"name": "Promised Day Arc",         "thai": "อาร์ควันแห่งสัญญา (จบ)",    "start": 52,  "end": 64,  "icon": "🔮"},
    ],
    "demon slayer": [
        {"name": "Final Selection Arc",      "thai": "อาร์คสอบคัดเลือก",           "start": 1,   "end": 5,   "icon": "🌸"},
        {"name": "Asakusa Arc",              "thai": "อาร์คอาซากุสะ",              "start": 6,   "end": 8,   "icon": "🏮"},
        {"name": "Drum House Arc",           "thai": "อาร์คบ้านกลอง",              "start": 9,   "end": 11,  "icon": "🥁"},
        {"name": "Mount Natagumo Arc",       "thai": "อาร์คภูเขาแมงมุม",           "start": 15,  "end": 21,  "icon": "🕷️"},
        {"name": "Rehabilitation Arc",       "thai": "อาร์คฟื้นฟู (Pillar Training)","start": 22, "end": 26,  "icon": "💪"},
    ],
    "hunter x hunter": [
        {"name": "Hunter Exam Arc",          "thai": "อาร์คสอบล่า",                "start": 1,   "end": 21,  "icon": "📋"},
        {"name": "Zoldyck Family Arc",       "thai": "อาร์คตระกูลซอลดิค",          "start": 22,  "end": 26,  "icon": "🏰"},
        {"name": "Heaven's Arena Arc",       "thai": "อาร์คเฮฟเว่นส์อารีน่า",      "start": 27,  "end": 36,  "icon": "🏟️"},
        {"name": "Yorknew City Arc",         "thai": "อาร์คยอร์กนิวซิตี้",         "start": 37,  "end": 58,  "icon": "🌃"},
        {"name": "Greed Island Arc",         "thai": "อาร์คกรีดไอแลนด์",           "start": 59,  "end": 91,  "icon": "🎮"},
        {"name": "Chimera Ant Arc",          "thai": "อาร์คมดไคมีร่า (ยาวที่สุด)", "start": 76,  "end": 136, "icon": "🐜"},
        {"name": "Election Arc",             "thai": "อาร์คเลือกตั้ง",             "start": 137, "end": 148, "icon": "🗳️"},
    ],
    "my hero academia": [
        {"name": "Entrance Exam Arc",        "thai": "อาร์คสอบเข้า",               "start": 1,   "end": 5,   "icon": "📚"},
        {"name": "Battle Trial Arc",         "thai": "อาร์คทดสอบต่อสู้",           "start": 6,   "end": 8,   "icon": "⚔️"},
        {"name": "USJ Arc",                  "thai": "อาร์ค USJ โจมตี",            "start": 9,   "end": 13,  "icon": "🏟️"},
        {"name": "UA Sports Festival Arc",   "thai": "อาร์คงานกีฬา UA",            "start": 14,  "end": 25,  "icon": "🏆"},
        {"name": "Vs. Hero Killer Arc",      "thai": "อาร์ค vs. สเตน",             "start": 26,  "end": 33,  "icon": "🔪"},
        {"name": "Final Exams Arc",          "thai": "อาร์คสอบปลายภาค",            "start": 34,  "end": 40,  "icon": "📝"},
        {"name": "Forest Training Camp Arc", "thai": "อาร์คค่ายฝึก",               "start": 41,  "end": 46,  "icon": "🌲"},
        {"name": "Hideout Raid Arc",         "thai": "อาร์คบุกที่ซ่อน",            "start": 47,  "end": 61,  "icon": "💥"},
        {"name": "Pro Hero Arc",             "thai": "อาร์คโปรฮีโร่",              "start": 76,  "end": 88,  "icon": "🦸"},
        {"name": "Joint Training Arc",       "thai": "อาร์คฝึกร่วม",               "start": 89,  "end": 101, "icon": "🤝"},
        {"name": "Paranormal Liberation War","thai": "อาร์คสงคราม PLF",            "start": 109, "end": 113, "icon": "🌪️"},
    ],
    "sword art online": [
        {"name": "Aincrad Arc",              "thai": "อาร์คไอน์คราด",              "start": 1,   "end": 14,  "icon": "🗡️"},
        {"name": "Fairy Dance Arc",          "thai": "อาร์คแฟรี่แดนซ์ (ALO)",     "start": 15,  "end": 25,  "icon": "🧚"},
        {"name": "Phantom Bullet Arc",       "thai": "อาร์คกระสุนผี (GGO)",        "start": 1,   "end": 14,  "icon": "🔫"},
        {"name": "Alicization Arc",          "thai": "อาร์คอลิไซเซชัน (ยาวที่สุด)","start": 1,  "end": 47,  "icon": "⚔️"},
    ],
    "tokyo ghoul": [
        {"name": "Gourmet Arc",              "thai": "อาร์คนักชิม",                "start": 1,   "end": 5,   "icon": "🍽️"},
        {"name": "Aogiri Arc",               "thai": "อาร์คอาโอกิริ",              "start": 6,   "end": 12,  "icon": "🌳"},
        {"name": "Root A Arc",               "thai": "อาร์ครูท A",                 "start": 1,   "end": 12,  "icon": "🌿"},
        {"name": "Re: Arc",                  "thai": "อาร์ค:Re (ภาค 3)",           "start": 1,   "end": 12,  "icon": "🔄"},
    ],
    "fairy tail": [
        {"name": "Macao Arc",                "thai": "อาร์คมาเกา",                 "start": 1,   "end": 2,   "icon": "🐉"},
        {"name": "Galuna Island Arc",        "thai": "อาร์คเกาะกาลูน่า",           "start": 9,   "end": 20,  "icon": "🌙"},
        {"name": "Phantom Lord Arc",         "thai": "อาร์คแฟนทอมลอร์ด",           "start": 21,  "end": 32,  "icon": "👻"},
        {"name": "Tower of Heaven Arc",      "thai": "อาร์คหอคอยสวรรค์",           "start": 33,  "end": 40,  "icon": "🗼"},
        {"name": "Fighting Festival Arc",    "thai": "อาร์คเทศกาลต่อสู้",          "start": 41,  "end": 51,  "icon": "🎪"},
        {"name": "Oracion Seis Arc",         "thai": "อาร์คออราซิออนเซอิส",        "start": 52,  "end": 68,  "icon": "😈"},
        {"name": "Edolas Arc",               "thai": "อาร์คเอโดลาส",               "start": 76,  "end": 95,  "icon": "🌀"},
        {"name": "Tenrou Island Arc",        "thai": "อาร์คเกาะเทนโร",             "start": 96,  "end": 122, "icon": "🏝️"},
        {"name": "Grand Magic Games Arc",    "thai": "อาร์คเกมส์เวทมนตร์",         "start": 151, "end": 203, "icon": "🏆"},
        {"name": "Tartaros Arc",             "thai": "อาร์คทาร์ทาโรส",             "start": 227, "end": 265, "icon": "💀"},
    ],
}

import unicodedata

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

def _normalize_title(title: str) -> str:
    """Normalize title for lookup in NAMED_ARCS dict."""
    cleaned = clean_diacritics(title)
    return re.sub(r"[^a-z0-9\s]", "", cleaned.lower()).strip()

def _find_named_arcs(title: str) -> Optional[List[Dict]]:
    """Try to find named arcs for a given anime title."""
    norm = _normalize_title(title)
    # Exact match
    if norm in NAMED_ARCS:
        return NAMED_ARCS[norm]
    # Partial match — title contains key or key contains title
    for key, arcs in NAMED_ARCS.items():
        if key in norm or norm in key:
            return arcs
    return None

def group_episodes_into_arcs(episodes: List[Dict[str, Any]], title: str) -> List[Dict[str, Any]]:
    """Group episodes into named story arcs, or fall back to canon/filler blocks."""
    if not episodes:
        return []

    named = _find_named_arcs(title)

    if named:
        return _group_by_named_arcs(episodes, named, title)
    else:
        return _group_by_badge(episodes, title)

def _group_by_named_arcs(episodes: List[Dict], arc_defs: List[Dict], title: str) -> List[Dict]:
    """Overlay named arc definitions on top of episode list."""
    ep_map = {ep["number"]: ep for ep in episodes}
    all_nums = sorted(ep_map.keys())
    covered = set()
    result = []
    arc_index = 1

    for arc_def in arc_defs:
        start, end = arc_def["start"], arc_def["end"]
        arc_eps = [ep_map[n] for n in all_nums if start <= n <= end and n in ep_map]
        if not arc_eps:
            continue

        for ep in arc_eps:
            covered.add(ep["number"])

        canon_in = sum(1 for e in arc_eps if e["badge"] in ("canon", "anime_canon", "mixed"))
        filler_in = sum(1 for e in arc_eps if e["badge"] == "filler")

        # Determine overall arc status
        if filler_in == len(arc_eps):
            status = "filler"
            status_label = "ช่วง Filler (ข้ามได้)"
            rec = "ข้ามได้ (Skip)"
            badge_color = "red"
            is_filler = True
        elif filler_in > canon_in:
            status = "mixed"
            status_label = "Mixed (มีทั้ง Canon และ Filler)"
            rec = "เลือกดูเฉพาะตอน Canon"
            badge_color = "yellow"
            is_filler = False
        else:
            status = "canon"
            status_label = "เนื้อเรื่องหลัก (Canon)"
            rec = "ต้องดู (Must Watch)"
            badge_color = "green"
            is_filler = False

        first_num = arc_eps[0]["number"]
        last_num = arc_eps[-1]["number"]

        result.append({
            "arc_number": arc_index,
            "title": f"{arc_def['icon']} {arc_def['name']} ({arc_def['thai']})",
            "range_display": f"ตอนที่ {first_num}–{last_num}",
            "start_ep": first_num,
            "end_ep": last_num,
            "episodes_count": len(arc_eps),
            "canon_in_arc": canon_in,
            "filler_in_arc": filler_in,
            "status_label": status_label,
            "recommendation": rec,
            "badge_color": badge_color,
            "is_filler": is_filler,
            "description": (
                f"ฟิลเลอร์ {filler_in} ตอน — ข้ามได้ทั้งหมด" if is_filler
                else f"เนื้อเรื่องหลัก {canon_in} ตอน" + (f" / Filler ผสม {filler_in} ตอน" if filler_in > 0 else "")
            ),
            "sample_episodes": arc_eps[:3]
        })
        arc_index += 1

    # Any episodes not covered by named arcs → group by badge
    uncovered = [ep_map[n] for n in all_nums if n not in covered]
    if uncovered:
        extra = _group_by_badge(uncovered, title, start_index=arc_index)
        result.extend(extra)

    return result

def _group_by_badge(episodes: List[Dict], title: str, start_index: int = 1) -> List[Dict]:
    """Fallback: group continuous runs of same badge together."""
    if not episodes:
        return []

    arcs = []
    current_type = episodes[0]["badge"]
    current_eps = []

    for ep in episodes:
        b = ep["badge"]
        same = (b == current_type) or (
            b in ("canon", "anime_canon") and current_type in ("canon", "anime_canon")
        )
        if same:
            current_eps.append(ep)
        else:
            if current_eps:
                arcs.append(_create_arc_summary(current_eps, current_type, start_index + len(arcs), title))
            current_type = b
            current_eps = [ep]

    if current_eps:
        arcs.append(_create_arc_summary(current_eps, current_type, start_index + len(arcs), title))

    return arcs

def _create_arc_summary(eps: List[Dict], arc_type: str, index: int, title: str) -> Dict:
    first_num = eps[0]["number"]
    last_num = eps[-1]["number"]
    range_str = f"ตอนที่ {first_num}" if first_num == last_num else f"ตอนที่ {first_num}–{last_num}"

    is_filler = arc_type == "filler"
    is_mixed = arc_type == "mixed"
    status_label = (
        "ช่วง Filler (ข้ามได้)" if is_filler
        else "Mixed Canon/Filler" if is_mixed
        else "เนื้อเรื่องหลัก (Canon)"
    )
    recommendation = "ข้ามได้ (Skip)" if is_filler else ("เลือกดูตอน Canon" if is_mixed else "ต้องดู (Must Watch)")
    badge_color = "red" if is_filler else ("yellow" if is_mixed else "green")
    icon = "⏭️" if is_filler else ("🔀" if is_mixed else "📖")

    if is_filler:
        arc_title = f"{icon} ช่วง Filler ({range_str})"
        desc = f"ตอนเสริมที่ไม่อยู่ในต้นฉบับ {len(eps)} ตอน — ข้ามได้โดยไม่กระทบเนื้อเรื่องหลัก"
    elif is_mixed:
        arc_title = f"{icon} ช่วง Mixed ({range_str})"
        desc = f"ผสม Canon/Filler {len(eps)} ตอน — แนะนำดูเฉพาะตอนที่ badge เป็น Canon"
    else:
        arc_title = f"{icon} เนื้อเรื่องหลัก ({range_str})"
        desc = f"Canon ตามต้นฉบับ {len(eps)} ตอน"

    return {
        "arc_number": index,
        "title": arc_title,
        "range_display": range_str,
        "start_ep": first_num,
        "end_ep": last_num,
        "episodes_count": len(eps),
        "canon_in_arc": sum(1 for e in eps if e["badge"] in ("canon", "anime_canon", "mixed")),
        "filler_in_arc": sum(1 for e in eps if e["badge"] == "filler"),
        "status_label": status_label,
        "recommendation": recommendation,
        "badge_color": badge_color,
        "is_filler": is_filler,
        "description": desc,
        "sample_episodes": eps[:3]
    }

def generate_ai_analysis(anime_meta: Dict[str, Any], filler_data: Dict[str, Any], related_content: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Generate intelligent Thai guidance and recommendations, including franchise/sequel awareness."""
    title = anime_meta.get("title_english") or anime_meta.get("title_romaji") or "Anime"
    total = filler_data["total_episodes"]
    filler_cnt = filler_data["filler_count"]
    filler_pct = filler_data["filler_percentage"]
    saved_hours = filler_data["time_saved_hours"]
    watch_ranges = filler_data["watch_ranges"]

    if filler_cnt == 0:
        verdict = f"🎉 **{title}** ไม่มีตอนฟิลเลอร์เลย (100% Canon) — ดูเรียงตั้งแต่ตอนที่ 1 จนจบได้เลยครับ!"
        action_plan = "ดูเรียงตามลำดับตอนได้ 100% ไม่ต้องข้ามตอนใดเลย"
    elif filler_pct > 30:
        verdict = (
            f"⚡ **{title}** มีฟิลเลอร์สูงถึง **{filler_pct}%** ({filler_cnt} จาก {total} ตอน) "
            f"ข้ามตามคำแนะนำระบบประหยัดเวลาได้ **{saved_hours} ชั่วโมง** "
            f"เนื้อเรื่องจะไม่สะดุดและกระชับกว่าเดิมมากครับ"
        )
        action_plan = f"ดูตามช่วง: {' ➔ '.join(watch_ranges)}"
    else:
        verdict = (
            f"✨ **{title}** มีฟิลเลอร์/ตอนพิเศษเพียง {filler_pct}% ({filler_cnt} ตอน) "
            f"ส่วนใหญ่เป็นเนื้อเรื่องหลัก ข้ามได้เล็กน้อยประหยัดเวลา {saved_hours} ชั่วโมงครับ"
        )
        action_plan = f"ช่วงเนื้อหลัก: {' ➔ '.join(watch_ranges)}"

    # Add franchise intelligence (sequels, prequels, recap movies)
    if related_content:
        sequels = [r for r in related_content if r.get("kind") == "sequel"]
        summaries = [r for r in related_content if r.get("kind") == "summary"]
        prequels = [r for r in related_content if r.get("kind") == "prequel"]

        extra_notes = []
        if sequels:
            s = sequels[0]
            s_eps = f" ({s.get('episodes')} ตอน)" if s.get('episodes') else ""
            extra_notes.append(f"🔥 **ภาคต่อ:** เรื่องนี้มีภาคต่อคือ **{s['title']}**{s_eps} สามารถคลิกสลับซีซันที่แถบ 'ลำดับซีซัน' เพื่อดูต่อได้ทันที!")
        if prequels:
            p = prequels[0]
            p_eps = f" ({p.get('episodes')} ตอน)" if p.get('episodes') else ""
            extra_notes.append(f"⏮️ **ภาคก่อนหน้า:** เรื่องนี้มีภาคก่อนคือ **{p['title']}**{p_eps} แนะนำดูก่อนเพื่อความเข้าใจครบถ้วน")
        if summaries:
            sm = summaries[0]
            extra_notes.append(f"⏭️ **ตอนสรุป (Recap):** มีมูฟวี่/ตอนพิเศษสรุปคือ **{sm['title']}** สามารถข้ามได้หากดูซีซันหลักมาแล้ว")

        if extra_notes:
            verdict += "<br><br>" + "<br>".join(extra_notes)

    return {
        "verdict": verdict,
        "action_plan": action_plan,
        "time_saved_display": f"{saved_hours} ชม.",
        "filler_rate_display": f"{filler_pct}%",
        "quick_watch_string": ", ".join(watch_ranges),
        "quick_skip_string": ", ".join(filler_data["skip_ranges"]) if filler_data["skip_ranges"] else "ไม่มี"
    }

def answer_ai_question(question: str, anime_title: str, context: Dict[str, Any]) -> str:
    """Answer user questions about the anime, canon status, or watching order."""
    q_low = question.lower()

    if GEMINI_API_KEY:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
            prompt = f"""คุณคือผู้เชี่ยวชาญด้านอนิเมะและซีรีส์ (Canon/Filler Expert)
อนิเมะ: {anime_title}
สถิติ: ทั้งหมด {context.get('total_episodes')} ตอน, ฟิลเลอร์ {context.get('filler_count')} ตอน, ข้ามได้: {context.get('skip_ranges')}
คำถาม: "{question}"
ตอบภาษาไทย กระชับ ตรงประเด็น เน้นตอนควรดู/ข้าม:"""
            resp = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=10)
            if resp.status_code == 200:
                result = resp.json()
                return result["candidates"][0]["content"]["parts"][0]["text"].strip()
        except Exception as e:
            print(f"Gemini API error: {e}")

    if "ข้าม" in question or "skip" in q_low or "ไม่ดู" in question:
        skips = context.get("skip_ranges", [])
        if skips:
            return f"**{anime_title}** ตอนที่ข้ามได้: **{', '.join(skips)}** (ประหยัด {context.get('time_saved_hours', 0)} ชั่วโมง)"
        return f"**{anime_title}** ไม่มีตอน Filler เลย ดูครบทุกตอนได้เลยครับ!"

    if "มูฟวี่" in question or "movie" in q_low:
        return f"ภาพยนตร์ของ **{anime_title}** ส่วนใหญ่เป็น Non-canon (เรื่องราวแยก) แต่มูฟวี่บางเรื่องเชื่อมเนื้อหาหลัก แนะนำดูหลังจบ Arc นั้นๆ ครับ"

    if "ดูอะไรก่อน" in question or "ลำดับ" in question or "order" in q_low:
        return f"ลำดับการดู **{anime_title}**: {', '.join(context.get('watch_ranges', []))} ครับ"

    return (
        f"**{anime_title}**: {context.get('total_episodes', 0)} ตอนรวม — "
        f"Canon {context.get('canon_count', 0)} ตอน, Filler {context.get('filler_count', 0)} ตอน "
        f"ดูตาม Arc ในแท็บด้านบนได้เลยครับ!"
    )
