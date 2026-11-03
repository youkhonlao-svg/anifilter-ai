import os
import json
import requests
from typing import Dict, Any, List

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

def group_episodes_into_arcs(episodes: List[Dict[str, Any]], title: str) -> List[Dict[str, Any]]:
    """Group continuous runs of episodes into thematic or canon/filler arcs."""
    if not episodes:
        return []

    arcs = []
    current_arc_type = episodes[0]["badge"]
    current_eps = []

    for ep in episodes:
        b = ep["badge"]
        # Group similar badges together (canon with anime_canon, or filler with filler)
        is_same_group = (
            (b == current_arc_type) or 
            (b in ("canon", "anime_canon") and current_arc_type in ("canon", "anime_canon"))
        )

        if is_same_group:
            current_eps.append(ep)
        else:
            if current_eps:
                arcs.append(_create_arc_summary(current_eps, current_arc_type, len(arcs) + 1, title))
            current_arc_type = b
            current_eps = [ep]

    if current_eps:
        arcs.append(_create_arc_summary(current_eps, current_arc_type, len(arcs) + 1, title))

    return arcs

def _create_arc_summary(eps: List[Dict[str, Any]], arc_type: str, index: int, title: str) -> Dict[str, Any]:
    first_num = eps[0]["number"]
    last_num = eps[-1]["number"]
    range_str = f"ตอนที่ {first_num}" if first_num == last_num else f"ตอนที่ {first_num} – {last_num}"

    is_filler = arc_type == "filler"
    status_label = "ตอนคั่น / ฟิลเลอร์ (Filler)" if is_filler else "เนื้อเรื่องหลัก (Canon)"
    recommendation = "ข้ามได้ (Skip)" if is_filler else "ต้องดู (Must Watch)"
    badge_color = "red" if is_filler else ("yellow" if arc_type == "mixed" else "green")

    # Meaningful Thai Arc titles
    if is_filler:
        arc_title = f"ช่วงตอนเสริมพิเศษ ({range_str})"
        desc = f"ช่วงนี้เป็นตอนเสริมที่ไม่อยู่ในมังงะต้นฉบับ ({len(eps)} ตอน) ข้ามได้โดยไม่เสียอรรถรสเนื้อเรื่องหลัก"
    else:
        arc_title = f"บทดำเนินเรื่องหลัก ({range_str})"
        desc = f"เนื้อเรื่องหลักตามมังงะ/ต้นฉบับ ({len(eps)} ตอน) สำคัญต่อเส้นเรื่องและพัฒนาการของตัวละคร"

    return {
        "arc_number": index,
        "title": arc_title,
        "range_display": range_str,
        "start_ep": first_num,
        "end_ep": last_num,
        "episodes_count": len(eps),
        "status_label": status_label,
        "recommendation": recommendation,
        "badge_color": badge_color,
        "is_filler": is_filler,
        "description": desc,
        "sample_episodes": eps[:3]
    }

def generate_ai_analysis(anime_meta: Dict[str, Any], filler_data: Dict[str, Any]) -> Dict[str, Any]:
    """Generate intelligent Thai guidance and recommendations."""
    title = anime_meta.get("title_english") or anime_meta.get("title_romaji") or "Anime"
    total = filler_data["total_episodes"]
    filler_cnt = filler_data["filler_count"]
    filler_pct = filler_data["filler_percentage"]
    saved_hours = filler_data["time_saved_hours"]
    watch_ranges = filler_data["watch_ranges"]

    # Natural Thai summary
    if filler_cnt == 0:
        verdict = f"🎉 **{title}** เป็นอนิเมะที่ **ไม่มีตอนฟิลเลอร์เลย (100% Canon)** คุณสามารถดูเรียงตั้งแต่ตอนที่ 1 จนจบได้อย่างสบายใจโดยไม่ต้องข้ามตอนใดๆ เลยครับ!"
        action_plan = "ดูเรียงตามลำดับตอนปกติได้เลย 100%"
    elif filler_pct > 30:
        verdict = (
            f"⚡ **{title}** มีสัดส่วนตอนฟิลเลอร์ค่อนข้างสูงถึง **{filler_pct}%** ({filler_cnt} จาก {total} ตอน) "
            f"การข้ามตอนฟิลเลอร์ตามคำแนะนำของระบบจะช่วยให้คุณประหยัดเวลาได้ถึง **{saved_hours} ชั่วโมง** "
            f"(เทียบเท่ากับการดูซีรีส์สั้นได้อีกเกือบ 3 เรื่อง) และช่วยให้อารมณ์ความต่อเนื่องของเนื้อเรื่องไม่สะดุดครับ"
        )
        action_plan = f"แนะนำให้ดูตามช่วงตอนต่อไปนี้: {' ➔ '.join(watch_ranges)}"
    else:
        verdict = (
            f"✨ **{title}** มีฟิลเลอร์เพียงเล็กน้อย **{filler_pct}%** ({filler_cnt} ตอน) "
            f"โดยรวมเน้นดำเนินเนื้อเรื่องหลักเป็นส่วนใหญ่ สามารถเลือกข้ามเฉพาะช่วงเสริมเพื่อความกระชับได้ ประหยัดเวลาไปได้ {saved_hours} ชั่วโมงครับ"
        )
        action_plan = f"ช่วงตอนเนื้อเรื่องหลักที่แนะนำ: {' ➔ '.join(watch_ranges)}"

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

    # If Gemini API key is present, try Gemini
    if GEMINI_API_KEY:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
            prompt = f"""
คุณคือผู้เชี่ยวชาญด้านอนิเมะและภาพยนตร์ (Anime & Movie Canon Expert)
อนิเมะที่กำลังพูดถึง: {anime_title}
ข้อมูลสถิติ: ทั้งหมด {context.get('total_episodes')} ตอน, ฟิลเลอร์ {context.get('filler_count')} ตอน, ข้ามได้ช่วง: {context.get('skip_ranges')}
คำถามของผู้ใช้: "{question}"

กรุณาตอบเป็นภาษาไทยอย่างกระชับ ตรงประเด็น ชัดเจน และเป็นมิตร เน้นให้ข้อมูลเรื่องตอนไหนควรดูตอนไหนข้ามได้:
"""
            resp = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=10)
            if resp.status_code == 200:
                result = resp.json()
                text = result["candidates"][0]["content"]["parts"][0]["text"]
                return text.strip()
        except Exception as e:
            print(f"Gemini API error: {e}")

    # Smart localized fallback answers
    if "ข้าม" in question or "skip" in q_low or "ไม่ดู" in question:
        skips = context.get("skip_ranges", [])
        if skips:
            return f"สำหรับ **{anime_title}** ตอนที่เป็นฟิลเลอร์และสามารถกดข้ามได้โดยไม่กระทบเนื้อเรื่องหลักเลยคือช่วงตอน: **{', '.join(skips)}** ครับ (ประหยัดเวลาได้ประมาณ {context.get('time_saved_hours', 0)} ชั่วโมง)"
        else:
            return f"สำหรับ **{anime_title}** เรื่องนี้ไม่มีตอนที่จำเป็นต้องข้ามครับ เป็นเนื้อเรื่องหลัก (Canon) ทั้งหมด แนะนำให้ดูครบทุกตอนได้เลยครับ!"

    if "มูฟวี่" in question or "movie" in q_low or "เดอะมูฟวี่" in question:
        return f"สำหรับเดอะมูฟวี่ของ **{anime_title}** ส่วนใหญ่ภาพยนตร์อนิเมะมักจะเป็นเนื้อเรื่องออริจินัลพิเศษ (Non-canon) แยกจากเส้นเรื่องหลัก แต่หากเป็นมูฟวี่ที่เชื่อมโยงเนื้อเรื่องหลักโดยตรง จะแนะนำให้ดูแทรกตามช่วงไทม์ไลน์หลังจบศึกใหญ่ประจำภาคนั้นๆ ครับ"

    if "ดูอะไรก่อน" in question or "ลำดับ" in question or "order" in q_low:
        return f"ลำดับการดูที่แนะนำสำหรับ **{anime_title}** คือเริ่มดูตอนเนื้อเรื่องหลักตามช่วง: **{', '.join(context.get('watch_ranges', []))}** เพื่อให้เข้าใจเส้นเรื่องตรงตามต้นฉบับมากที่สุดครับ"

    # General answer
    return (
        f"เกี่ยวกับ **{anime_title}**: เรื่องนี้มีทั้งหมด {context.get('total_episodes', 0)} ตอน "
        f"โดยมีตอนเนื้อเรื่องหลัก {context.get('canon_count', 0)} ตอน และตอนคั่น {context.get('filler_count', 0)} ตอน "
        f"คุณสามารถดูตามแถบช่วงตอนที่ระบบแนะนำ หรือสลับแท็บเป็น 'เฉพาะเนื้อเรื่องหลัก' เพื่อดูเฉพาะตอนสำคัญได้ทันทีครับ!"
    )
