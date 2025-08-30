# app.py — YouTube→Transcript API with Title Fallback
# Uses your channel_id = UCXe0rNb7t4_FKtH92-lJOqw

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import feedparser
from urllib.parse import urlparse, parse_qs
from typing import List, Optional, Dict, Any
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptAvailable, NoTranscriptFound, VideoUnavailable

CHANNEL_ID = "UCXe0rNb7t4_FKtH92-lJOqw"

app = FastAPI(
    title="YouTube Sermons API",
    description="Lists channel videos and returns transcripts (or titles) for GPT.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

def _video_id_from_entry(entry: Any) -> Optional[str]:
    vid = getattr(entry, "yt_videoid", None) or entry.get("yt_videoid")
    if vid:
        return vid
    link = entry.get("link")
    if link:
        q = parse_qs(urlparse(link).query)
        return q.get("v", [None])[0]
    return None

def _rss_entries(max_items: int = 20):
    url = f"https://www.youtube.com/feeds/videos.xml?channel_id={CHANNEL_ID}"
    feed = feedparser.parse(url)
    if feed.bozo:
        raise HTTPException(status_code=400, detail="Could not read channel feed.")
    return feed.entries[:max_items]

def _get_transcript_text(video_id: str, languages_priority: List[str]) -> Dict[str, Any]:
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=languages_priority)
        text = " ".join([seg.get("text", "").strip() for seg in transcript if seg.get("text")])
        return {"video_id": video_id, "text": text, "has_transcript": True}
    except (TranscriptsDisabled, NoTranscriptAvailable, NoTranscriptFound, VideoUnavailable):
        return {"video_id": video_id, "text": "", "has_transcript": False}

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

@app.get("/videos")
def list_videos(max_items: int = 20):
    entries = _rss_entries(max_items=max_items)
    items = []
    for e in entries:
        vid = _video_id_from_entry(e)
        if vid:
            items.append(VideoItem(
                video_id=vid,
                title=e.get("title", ""),
                published=e.get("published", ""),
                url=f"https://www.youtube.com/watch?v={vid}"
            ))
    return {"channel_id": CHANNEL_ID, "items": items}

@app.get("/transcript", response_model=TranscriptResponse)
def transcript(video_id: str, title: str = "", url: str = "", languages: List[str] = ["pt-BR","pt","en"]):
    t = _get_transcript_text(video_id, languages)
    if t["has_transcript"]:
        return {"video_id": video_id, "title": title, "url": url, "text": t["text"], "used_title_fallback": False}
    else:
        return {"video_id": video_id, "title": title, "url": url, "text": f"(No transcript. Title suggests: {title})", "used_title_fallback": True}