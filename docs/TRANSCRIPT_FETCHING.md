# YouTube Transcript Fetching

This document explains how the Seerah Q&A application fetches transcripts from Yasir Qadhi's 104-video Seerah lecture series on YouTube.

## Overview

The transcript fetching pipeline:
1. Extracts video metadata from the YouTube playlist using `yt-dlp`
2. Downloads transcripts using **Supadata API** (reliable, no rate limiting)
3. Saves transcripts as structured JSON files

## Tools Used

| Library | Purpose |
|---------|---------|
| `yt-dlp` | Extract playlist and video metadata |
| `Supadata API` | Download video transcripts/captions |

### Why Supadata API?

- **No rate limiting**: Unlike YouTube's direct API, Supadata doesn't block your IP
- **Reliable**: Works consistently for most videos with captions
- **Simple API**: Single HTTP request to get transcripts
- **Timestamps included**: Returns segments with start times and durations

## The Playlist

```
Playlist: Yasir Qadhi's Seerah of the Prophet
URL: https://youtube.com/playlist?list=PLLN02x1UwIfLvnUiycprqWOG0M_dp8cOL
Videos: 104 lectures
Total Duration: ~150+ hours
```

## Pipeline Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        TRANSCRIPT FETCHING PIPELINE                      │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  Step 1: Get Playlist Videos                                            │
│  ─────────────────────────────                                          │
│  Input:  Playlist ID (PLLN02x1UwIfLvnUiycprqWOG0M_dp8cOL)              │
│  Tool:   yt-dlp                                                         │
│  Output: List of video metadata                                         │
│          [{video_id, title, duration, upload_date, playlist_index}]     │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  Step 2: Fetch Transcript for Each Video                                │
│  ───────────────────────────────────────                                │
│  Input:  Video ID                                                       │
│  Tool:   Supadata API                                                   │
│  Output: Transcript segments with timestamps                            │
│          [{text, start, duration}, ...]                                 │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  Step 3: Save as JSON                                                   │
│  ────────────────────                                                   │
│  Format: {metadata + transcript}                                        │
│  Path:   data/transcripts/001_VIDEO_ID.json                            │
└─────────────────────────────────────────────────────────────────────────┘
```

## Step-by-Step Process

### Step 1: Extracting Playlist Videos

```python
import yt_dlp

def get_playlist_videos(playlist_id: str) -> list[dict]:
    """Fetch all video information from a YouTube playlist."""
    
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,    # Get full metadata
        'ignoreerrors': True,     # Skip unavailable videos
    }
    
    playlist_url = f"https://www.youtube.com/playlist?list={playlist_id}"
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        playlist_info = ydl.extract_info(playlist_url, download=False)
        
        videos = []
        for index, entry in enumerate(playlist_info['entries'], start=1):
            if entry is None:  # Skip unavailable videos
                continue
                
            videos.append({
                'video_id': entry.get('id'),
                'title': entry.get('title'),
                'duration': entry.get('duration'),      # seconds
                'upload_date': entry.get('upload_date'),
                'playlist_index': index,
            })
    
    return videos
```

**Output example:**
```python
[
    {
        'video_id': 'VOUp3ZZ9t3A',
        'title': 'Seerah of Prophet Muhammed 1 - Specialities of Prophet Muhammed...',
        'duration': 2730,
        'upload_date': '20120720',
        'playlist_index': 1
    },
    # ... 103 more videos
]
```

### Step 2: Fetching Transcripts with Supadata API

```python
import requests

SUPADATA_API_KEY = "your_api_key_here"
SUPADATA_ENDPOINT = "https://api.supadata.ai/v1/youtube/transcript"

def fetch_transcript(video_id: str) -> dict:
    """Fetch transcript using Supadata API."""
    
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    
    headers = {
        'x-api-key': SUPADATA_API_KEY,
    }
    
    params = {
        'url': video_url,
    }
    
    response = requests.get(SUPADATA_ENDPOINT, headers=headers, params=params)
    
    if response.status_code == 200:
        data = response.json()
        
        # Parse segments
        segments = []
        for seg in data.get('content', []):
            segments.append({
                'text': seg.get('text', ''),
                'start': float(seg.get('offset', 0)),
                'duration': float(seg.get('duration', 0))
            })
        
        full_text = ' '.join(s['text'] for s in segments)
        
        return {
            'segments': segments,
            'full_text': full_text,
            'language': data.get('lang', 'en'),
        }
    
    return None
```

**Segment format:**
```python
{
    'text': 'Bismillah Ar-Rahman Ar-Raheem',
    'start': 29.56,     # Start time in seconds
    'duration': 3.68    # Duration in seconds
}
```

### Step 3: Saving Transcripts

```python
def save_transcript(video_metadata: dict, transcript_data: dict, output_dir: Path):
    """Save transcript to a JSON file."""
    
    # Filename format: 001_VIDEO_ID.json
    filename = f"{video_metadata['playlist_index']:03d}_{video_metadata['video_id']}.json"
    filepath = output_dir / filename
    
    # Combine metadata and transcript
    full_data = {
        **video_metadata,
        'transcript': transcript_data,
        'fetched_at': datetime.now().isoformat(),
    }
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(full_data, f, ensure_ascii=False, indent=2)
```

**File structure:**
```
data/transcripts/
├── 001_VOUp3ZZ9t3A.json
├── 002_udjM4dBVicE.json
├── 003_4F5qzMI2IKs.json
├── ...
└── 104_95K8HQbbeS0.json
```

## JSON Output Format

Each transcript file contains:

```json
{
  "video_id": "VOUp3ZZ9t3A",
  "title": "Seerah of Prophet Muhammed 1 - Specialities...",
  "duration": 2730,
  "upload_date": "20120720",
  "description": "First lecture in the series...",
  "playlist_index": 1,
  "transcript": {
    "segments": [
      {
        "text": "Bismillah Ar-Rahman Ar-Raheem",
        "start": 29.56,
        "duration": 3.68
      },
      {
        "text": "All praise is due to Allah",
        "start": 73.08,
        "duration": 6.64
      }
    ],
    "full_text": "Bismillah Ar-Rahman Ar-Raheem All praise is due to Allah...",
    "language": "en"
  },
  "fetched_at": "2024-01-15T10:30:00.000000"
}
```

## Running the Fetcher

### Command Line

```bash
# Fetch all transcripts (skips existing)
python -m data_pipeline.transcript_fetcher

# Specify custom output directory
python -m data_pipeline.transcript_fetcher --output-dir ./my_transcripts

# Re-fetch existing transcripts
python -m data_pipeline.transcript_fetcher --no-skip

# Use custom API key
python -m data_pipeline.transcript_fetcher --api-key YOUR_API_KEY
```

### Programmatic Usage

```python
from data_pipeline.transcript_fetcher import fetch_all_transcripts

# Fetch all transcripts
results = fetch_all_transcripts(
    playlist_id="PLLN02x1UwIfLvnUiycprqWOG0M_dp8cOL",
    output_dir=Path("data/transcripts"),
    skip_existing=True,
    api_key="your_supadata_api_key"
)

print(f"Success: {results['success']}")
print(f"Failed: {results['failed']}")
print(f"Skipped: {results['skipped']}")
```

## Handling Edge Cases

### Missing Transcripts

Some videos may not have captions available:

```python
# Supadata returns 206 status for unavailable transcripts
if response.status_code == 206:
    error = response.json()
    if error.get('error') == 'transcript-unavailable':
        print(f"No transcript available for: {video_id}")
        return None
```

### Rate Limiting

Supadata has generous rate limits, but we still add small delays:

```python
# Small delay between requests to be nice to the API
delay = random.uniform(0.5, 1.5)
time.sleep(delay)
```

## Expected Output

For the 104-video Seerah series:

| Metric | Expected Value |
|--------|----------------|
| Total videos | 104 |
| Videos with transcripts | ~100 (96%) |
| Average transcript size | ~150-300 KB |
| Total data size | ~25 MB |
| Fetch time | ~5-10 minutes |

**Note:** 4 videos in the series don't have captions available on YouTube.

## Resumable Fetching

The fetcher supports resuming interrupted downloads:

```python
def fetch_all_transcripts(skip_existing=True):
    # Check for existing files
    existing_ids = set()
    for f in output_dir.glob("*.json"):
        if not f.name.startswith('_'):
            video_id = f.stem.split('_', 1)[1]
            existing_ids.add(video_id)
    
    # Skip already downloaded
    for video in videos:
        if video['video_id'] in existing_ids:
            continue  # Skip
        
        # Fetch new transcript
        transcript = fetch_transcript(video['video_id'])
```

This means you can safely interrupt and restart the process.

## Summary File

After fetching, a summary is saved:

```json
// data/transcripts/_fetch_summary.json
{
  "total": 104,
  "success": 100,
  "failed": 4,
  "skipped": 0,
  "details": [
    {"video_id": "VOUp3ZZ9t3A", "title": "...", "status": "success"},
    {"video_id": "o_LsNYWbddk", "title": "...", "status": "failed"}
  ]
}
```

## Troubleshooting

### "transcript-unavailable"

**Cause:**
- Video has no captions on YouTube
- This is a YouTube limitation, not an API issue

**Solution:**
- These videos are skipped automatically
- Check `_fetch_summary.json` for details

### API Key Issues

**Cause:**
- Invalid or missing API key

**Solution:**
- Set `SUPADATA_API_KEY` environment variable
- Or pass `--api-key` flag

### Slow fetching

**Cause:**
- Network latency

**Solution:**
- The fetcher has built-in delays
- ~5-10 minutes for all 104 videos is normal

## Next Steps

After fetching transcripts:

1. **Verify downloads:**
   ```bash
   ls data/transcripts/*.json | wc -l
   # Should show ~100 files
   ```

2. **Check summary:**
   ```bash
   cat data/transcripts/_fetch_summary.json
   ```

3. **Build knowledge base:**
   ```bash
   python -m data_pipeline.knowledge_base
   ```

## Code Location

The transcript fetcher is implemented in:

```
data_pipeline/transcript_fetcher.py
```

Key functions:
- `get_playlist_videos()` - Fetch video list from playlist (yt-dlp)
- `fetch_transcript()` - Download single video transcript (Supadata)
- `fetch_all_transcripts()` - Main pipeline function
- `load_all_transcripts()` - Load saved transcripts for processing
