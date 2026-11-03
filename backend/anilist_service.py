import requests
from typing import List, Dict, Any, Optional
from backend.database import get_cached_anime, set_cached_anime

ANILIST_API_URL = "https://graphql.anilist.co"

SEARCH_QUERY = """
query ($search: String) {
  Page(page: 1, perPage: 10) {
    media(search: $search, type: ANIME, sort: SEARCH_MATCH) {
      id
      title {
        romaji
        english
        native
      }
      format
      episodes
      status
      description(asHtml: false)
      bannerImage
      coverImage {
        large
        medium
      }
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
    title {
      romaji
      english
      native
    }
    format
    episodes
    status
    description(asHtml: false)
    bannerImage
    coverImage {
      large
      extraLarge
    }
    genres
    averageScore
    seasonYear
    startDate {
      year
      month
      day
    }
    relations {
      edges {
        relationType
        node {
          id
          title {
            romaji
            english
          }
          format
          type
        }
      }
    }
  }
}
"""

def search_anime(query: str) -> List[Dict[str, Any]]:
    """Search AniList for anime matching query."""
    try:
        response = requests.post(
            ANILIST_API_URL,
            json={"query": SEARCH_QUERY, "variables": {"search": query}},
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            media_list = data.get("data", {}).get("Page", {}).get("media", [])
            results = []
            for m in media_list:
                results.append({
                    "id": m["id"],
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
                    "description": m.get("description", "")
                })
            return results
    except Exception as e:
        print(f"Error searching AniList: {e}")
    return []

def get_anime_details(anime_id: int) -> Optional[Dict[str, Any]]:
    """Get detailed anime metadata by AniList ID (uses SQLite cache for instant load)."""
    # 1. Check local cache first
    cached = get_cached_anime(anime_id)
    if cached:
        return cached

    # 2. Query AniList
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
                title = media.get("title", {}).get("english") or media.get("title", {}).get("romaji") or ""
                set_cached_anime(anime_id, title, media)
                return media
    except Exception as e:
        print(f"Error fetching AniList details: {e}")
    return None
