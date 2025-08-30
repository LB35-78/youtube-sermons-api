# app.py — YouTube→Transcript API with Title Fallback
# Fetches ALL videos from your channel using YouTube Data API v3

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import requests
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound, VideoUnavailable

# Your YouTube Data API key (DO NOT share this publicly)
YOUTUBE_API_KEY = "AIzaSyCpt941lW3QXzk2VVQeV_RNU5FhOocWN_w"

# Your channel uploads playlist ID
# Formula: UU + (channel_id without the first 2 characters "UC")
UPLOADS_PLAYLIST_ID = "UUXe0rNb7t4_FKtH92-lJOqw"

app = FastAPI(
    title="YouTube Sermons API",
    description="Fetches ALL channel sermons and transcripts for GPT.",
    version="2.0.0",
)

# Allow all origins (needed for GPT Action calls)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

# -------- Models --------
class VideoItem(BaseModel):
    video_id: str
    title: str
    published: str
    url: str

class TranscriptResponse(BaseModel):
    video_id: str
    title: str
    url: str
    text: str
    used_title_fallback: bool

# -------- Helpers --------
def get_all_videos(api_key: str, playlist_id: str, max_results: int = 50) -> List[Dict[str, Any]]:
    """Fetch ALL videos from the uploads playlist using pagination"""
    url = "https://www.googleapis.com/youtube/v3/playlistItems"
    params = {
        "part": "snippet",
        "playlistId": playlist_id,
        "maxResults": max_results,
        "key": api_key,
    }

    videos = []
    while True:
        resp = requests.get(url, params=params).json()
        for item in resp.get("items", []):
            snippet = item["snippet"]
            videos.append({
                "video_id": snippet["resourceId"]["videoId"],
                "title": snippet["title"],
                "published": snippet["publishedAt"],
                "url": f"https://www.youtube.com/watch?v={snippet['resourceId']['videoId']}"
            })
        if "nextPageToken" in resp:
            params["pageToken"] = resp["nextPageToken"]
        else:
            break
    return videos

def _get_transcript_text(video_id: str, languages_priority: List[str]) -> Dict[str, Any]:
    """Fetch transcript if available"""
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=languages_priority)
        text = " ".join([seg.get("text", "").strip() for seg in transcript if seg.get("text")])
        return {"video_id": video_id, "text": text, "has_transcript": True}
    except (TranscriptsDisabled, NoTranscriptFound, VideoUnavailable):
        return {"video_id": video_id, "text": "", "has_transcript": False}
    except Exception as e:
        return {"video_id": video_id, "text": "", "has_transcript": False, "error": str(e)}

# -------- Endpoints --------
@app.get("/videos")
def list_videos():
    """Return ALL sermons from channel"""
    items = get_all_videos(YOUTUBE_API_KEY, UPLOADS_PLAYLIST_ID)
    return {"playlist_id": UPLOADS_PLAYLIST_ID, "count": len(items), "items": items}

@app.get("/transcript", response_model=TranscriptResponse)
def transcript(video_id: str, title: str = "", url: str = "", languages: List[str] = ["pt-BR","pt","en"]):
    """Return transcript if available, else fallback to title"""
    t = _get_transcript_text(video_id, languages)
    if t.get("has_transcript"):
        return {"video_id": video_id, "title": title, "url": url, "text": t["text"], "used_title_fallback": False}
    else:
        return {"video_id": video_id, "title": title, "url": url, "text": f"(No transcript. Title suggests: {title})", "used_title_fallback": True}