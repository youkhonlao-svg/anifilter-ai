import os
import urllib.parse
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any, List

from backend.anilist_service import search_anime, get_anime_details, classify_related_content
from backend.filler_service import find_best_slug, get_episodes_from_filler_list, generate_smart_episodes, generate_default_episodes
from backend.ai_curator import group_episodes_into_arcs, generate_ai_analysis, answer_ai_question
from backend.database import save_user_progress, get_user_progress
from backend.series_service import search_live_action_series, get_series_guide

app = FastAPI(title="AniFilter AI API", description="AI Anime & Movie & TV Series Canon/Filler Assistant")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AskRequest(BaseModel):
    question: str
    anime_title: str
    context: Dict[str, Any]

class SaveProgressRequest(BaseModel):
    sync_code: str
    anime_id: str
    watched_episodes: List[int]

def get_legal_streaming_links(title: str) -> List[Dict[str, str]]:
    """Generate legal streaming search links for Thailand audiences."""
    q = urllib.parse.quote(title)
    return [
        {
            "name": "Bilibili Thailand",
            "url": f"https://www.bilibili.tv/th/search-result?q={q}",
            "color": "from-sky-500 to-blue-600",
            "icon": "tv"
        },
        {
            "name": "Netflix",
            "url": f"https://www.netflix.com/search?q={q}",
            "color": "from-red-600 to-rose-700",
            "icon": "film"
        },
        {
            "name": "iQIYI",
            "url": f"https://www.iq.com/search?query={q}",
            "color": "from-emerald-500 to-green-600",
            "icon": "play-circle"
        },
        {
            "name": "TrueID",
            "url": f"https://movie.trueid.net/th-th/search?q={q}",
            "color": "from-orange-500 to-red-500",
            "icon": "play"
        },
        {
            "name": "Crunchyroll",
            "url": f"https://www.crunchyroll.com/search?q={q}",
            "color": "from-amber-500 to-orange-600",
            "icon": "globe"
        }
    ]

@app.get("/api/search")
def api_search(q: str = Query(..., min_length=1), media_type: str = Query("all")):
    """Universal search for Anime, Live-Action K-Drama, J-Drama, US Series, and Movies."""
    import re as _re

    anime_results = []
    series_results = []

    # 1. Search Anime via AniList
    if media_type in ("all", "anime"):
        anime_results = search_anime(q)

    # 2. Search Live-Action Series (Korean, US, Japanese, etc.) via TVMaze
    if media_type in ("all", "series"):
        series_results = search_live_action_series(q)

    # 3. Deduplicate: if AniList already has a title, remove TVMaze duplicate
    #    AniList anime always takes priority over TVMaze for the same title
    def _norm(t: str) -> str:
        return _re.sub(r"[^a-z0-9]", "", (t or "").lower())

    anime_titles = {_norm(r.get("title_english", "") or r.get("title_romaji", "")) for r in anime_results}

    deduped_series = []
    for s in series_results:
        s_title = _norm(s.get("title_english", "") or "")
        # Skip TVMaze result if AniList already has a very similar title
        if s_title and s_title in anime_titles:
            continue
        deduped_series.append(s)

    # Anime first, then live-action series
    results = anime_results + deduped_series

    return {"query": q, "results": results}

@app.get("/api/guide")
def api_guide(id: str = Query(...), title: Optional[str] = Query(None)):
    """Get complete episode guide for either Anime or Live-Action Series."""
    # Check if this is a live-action series (ID format: tv_12345)
    if str(id).startswith("tv_"):
        series_id = int(str(id).replace("tv_", ""))
        guide = get_series_guide(series_id)
        if not guide:
            raise HTTPException(status_code=404, detail="Series not found")
        return guide

    # Otherwise, handle as Anime via AniList
    try:
        anime_id = int(id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid anime ID format")

    details = get_anime_details(anime_id)
    if not details:
        raise HTTPException(status_code=404, detail="Anime not found on AniList")

    primary_title = title or details.get("title", {}).get("english") or details.get("title", {}).get("romaji") or ""
    romaji_title = details.get("title", {}).get("romaji") or ""
    english_title = details.get("title", {}).get("english") or ""
    alt_candidates = [english_title, romaji_title]
    anime_format = details.get("format", "TV")

    slug = find_best_slug(primary_title, alt_candidates)
    filler_data = None
    if slug:
        filler_data = get_episodes_from_filler_list(slug)

    if not filler_data:
        ep_count = details.get("episodes")
        filler_data = generate_smart_episodes(ep_count, primary_title, anime_format)

    # ── Classify related content (OVA / Special / Sequel / etc.) ──────────
    relations_edges = details.get("relations", {}).get("edges", [])
    related_content = classify_related_content(relations_edges)

    ai_summary = generate_ai_analysis({
        "title_english": english_title or primary_title,
        "title_romaji": romaji_title
    }, filler_data)

    arcs = group_episodes_into_arcs(filler_data["episodes"], primary_title)
    streaming_links = get_legal_streaming_links(english_title or primary_title)

    return {
        "metadata": {
            "id": details["id"],
            "title_english": english_title or primary_title,
            "title_romaji": romaji_title,
            "title_native": details.get("title", {}).get("native", ""),
            "format": details.get("format"),
            "status": details.get("status"),
            "episodes": details.get("episodes"),
            "score": details.get("averageScore"),
            "year": details.get("seasonYear"),
            "cover_image": details.get("coverImage", {}).get("extraLarge") or details.get("coverImage", {}).get("large"),
            "banner_image": details.get("bannerImage"),
            "description": details.get("description", ""),
            "genres": details.get("genres", [])
        },
        "stats": {
            "total_episodes": filler_data["total_episodes"],
            "canon_count": filler_data["canon_count"],
            "mixed_count": filler_data["mixed_count"],
            "filler_count": filler_data["filler_count"],
            "filler_percentage": filler_data["filler_percentage"],
            "time_saved_hours": filler_data["time_saved_hours"],
            "watch_ranges": filler_data["watch_ranges"],
            "skip_ranges": filler_data["skip_ranges"],
            "source": filler_data.get("source", "AniList"),
            "note": filler_data.get("note", ""),
        },
        "ai_analysis": ai_summary,
        "arcs": arcs,
        "episodes": filler_data["episodes"],
        "related_content": related_content,
        "streaming_links": streaming_links
    }

@app.post("/api/ask")
def api_ask(req: AskRequest):
    """Ask AI Copilot about the anime or episode recommendations."""
    answer = answer_ai_question(req.question, req.anime_title, req.context)
    return {"answer": answer}

@app.post("/api/progress/save")
def api_save_progress(req: SaveProgressRequest):
    """Save watched progress to server for multi-device sync."""
    save_user_progress(req.sync_code, req.anime_id, req.watched_episodes)
    return {"status": "ok", "message": "Progress synced successfully"}

@app.get("/api/progress/load")
def api_load_progress(sync_code: str = Query(...), anime_id: str = Query(...)):
    """Load watched progress from server using sync code."""
    episodes = get_user_progress(sync_code, anime_id)
    return {"sync_code": sync_code, "anime_id": anime_id, "watched_episodes": episodes}

# Serve frontend & PWA assets
FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))

@app.get("/")
def serve_index():
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(
            index_path,
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0"
            }
        )
    return {"message": "AniFilter AI Backend is running."}

@app.get("/manifest.json")
def serve_manifest():
    return FileResponse(os.path.join(FRONTEND_DIR, "manifest.json"), media_type="application/json")

@app.get("/sw.js")
def serve_sw():
    return FileResponse(os.path.join(FRONTEND_DIR, "sw.js"), media_type="application/javascript")

if os.path.exists(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")
