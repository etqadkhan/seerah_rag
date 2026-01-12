"""
Transcript Fetcher Module

This module handles fetching transcripts from YouTube videos in the Seerah playlist.
It uses Supadata API for transcript extraction and yt-dlp for metadata.

Usage:
    python -m data_pipeline.transcript_fetcher

Functions:
    - get_playlist_videos: Fetches all video IDs and metadata from a playlist
    - fetch_transcript: Downloads transcript for a single video using Supadata
    - save_transcripts: Saves all transcripts to JSON files
"""

import json
import os
import sys
import time
import random
from pathlib import Path
from typing import Optional
from datetime import datetime

import requests
import yt_dlp

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import PLAYLIST_ID, TRANSCRIPTS_DIR

# Supadata API Configuration
# API key must be set via environment variable (no default for security)
SUPADATA_API_KEY = os.getenv("SUPADATA_API_KEY", "")
SUPADATA_ENDPOINT = "https://api.supadata.ai/v1/youtube/transcript"


def get_playlist_videos(playlist_id: str) -> list[dict]:
    """
    Fetch all video information from a YouTube playlist.
    
    Args:
        playlist_id: The YouTube playlist ID
        
    Returns:
        List of dictionaries containing video metadata:
        - video_id: YouTube video ID
        - title: Video title
        - duration: Video duration in seconds
        - upload_date: Upload date string
        - description: Video description
        - playlist_index: Position in playlist (1-indexed)
    """
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        'ignoreerrors': True,  # Skip unavailable videos
    }
    
    playlist_url = f"https://www.youtube.com/playlist?list={playlist_id}"
    videos = []
    
    print(f"Fetching playlist metadata for: {playlist_id}")
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            playlist_info = ydl.extract_info(playlist_url, download=False)
            
            if playlist_info and 'entries' in playlist_info:
                for index, entry in enumerate(playlist_info['entries'], start=1):
                    if entry is None:  # Skip unavailable videos
                        print(f"  Skipping unavailable video at position {index}")
                        continue
                        
                    video_data = {
                        'video_id': entry.get('id', ''),
                        'title': entry.get('title', 'Unknown Title'),
                        'duration': entry.get('duration', 0),
                        'upload_date': entry.get('upload_date', ''),
                        'description': entry.get('description', '')[:500],  # Truncate
                        'playlist_index': index,
                    }
                    videos.append(video_data)
                    print(f"  Found video {index}: {video_data['title'][:50]}...")
                    
        except Exception as e:
            print(f"Error fetching playlist: {e}")
            raise
    
    print(f"Total videos found: {len(videos)}")
    return videos


def fetch_transcript(video_id: str, api_key: str = SUPADATA_API_KEY) -> Optional[dict]:
    """
    Fetch transcript for a single YouTube video using Supadata API.
    
    Args:
        video_id: YouTube video ID
        api_key: Supadata API key
        
    Returns:
        Dictionary containing transcript data:
        - segments: List of transcript segments with text, start, duration
        - full_text: Concatenated full transcript text
        - language: Language of the transcript
        
        Returns None if transcript is not available.
    """
    if not api_key:
        print("  Error: Supadata API key not set")
        return None
    
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    
    headers = {
        'x-api-key': api_key,
    }
    
    params = {
        'url': video_url,
        'text': 'true',  # Get plain text format
    }
    
    try:
        response = requests.get(
            SUPADATA_ENDPOINT,
            headers=headers,
            params=params,
            timeout=60
        )
        
        if response.status_code == 200:
            data = response.json()
            
            # Supadata returns content with segments or full text
            # Handle different response formats
            if 'content' in data:
                # Text format - single content string
                full_text = data.get('content', '')
                
                # Create synthetic segments from full text
                # (Supadata text mode doesn't include timestamps)
                segments = [{
                    'text': full_text,
                    'start': 0,
                    'duration': 0
                }]
                
                return {
                    'segments': segments,
                    'full_text': full_text,
                    'language': data.get('lang', 'en'),
                }
            
            elif 'segments' in data or isinstance(data, list):
                # Segments format with timestamps
                segments_raw = data.get('segments', data) if isinstance(data, dict) else data
                
                segments = []
                text_parts = []
                
                for seg in segments_raw:
                    if isinstance(seg, dict):
                        segment = {
                            'text': seg.get('text', ''),
                            'start': seg.get('start', seg.get('offset', 0)),
                            'duration': seg.get('duration', seg.get('dur', 0))
                        }
                    else:
                        segment = {'text': str(seg), 'start': 0, 'duration': 0}
                    
                    segments.append(segment)
                    text_parts.append(segment['text'])
                
                full_text = ' '.join(text_parts)
                
                return {
                    'segments': segments,
                    'full_text': full_text,
                    'language': data.get('lang', 'en') if isinstance(data, dict) else 'en',
                }
            
            else:
                # Unknown format, try to extract what we can
                print(f"  Unexpected response format: {list(data.keys()) if isinstance(data, dict) else type(data)}")
                return None
                
        elif response.status_code == 404:
            print(f"  Transcript not found for video: {video_id}")
            return None
        elif response.status_code == 429:
            print(f"  Rate limited. Waiting before retry...")
            time.sleep(10)
            return None
        else:
            print(f"  API error {response.status_code}: {response.text[:200]}")
            return None
            
    except requests.exceptions.Timeout:
        print(f"  Request timeout for video: {video_id}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"  Request error for {video_id}: {e}")
        return None
    except Exception as e:
        print(f"  Error fetching transcript for {video_id}: {e}")
        return None


def fetch_transcript_with_timestamps(video_id: str, api_key: str = SUPADATA_API_KEY) -> Optional[dict]:
    """
    Fetch transcript with timestamps using Supadata API.
    
    Args:
        video_id: YouTube video ID
        api_key: Supadata API key
        
    Returns:
        Dictionary containing transcript data with timestamps
    """
    if not api_key:
        print("  Error: Supadata API key not set")
        return None
    
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    
    headers = {
        'x-api-key': api_key,
    }
    
    # Request without text=true to get timestamps
    params = {
        'url': video_url,
    }
    
    try:
        response = requests.get(
            SUPADATA_ENDPOINT,
            headers=headers,
            params=params,
            timeout=60
        )
        
        if response.status_code == 200:
            data = response.json()
            
            # Parse the response
            segments = []
            text_parts = []
            
            # Handle different response structures
            transcript_data = data.get('content', data)
            
            if isinstance(transcript_data, list):
                for seg in transcript_data:
                    if isinstance(seg, dict):
                        segment = {
                            'text': seg.get('text', ''),
                            'start': float(seg.get('offset', seg.get('start', 0))),
                            'duration': float(seg.get('duration', seg.get('dur', 0)))
                        }
                        segments.append(segment)
                        text_parts.append(segment['text'])
            elif isinstance(transcript_data, str):
                # Plain text response
                segments = [{'text': transcript_data, 'start': 0, 'duration': 0}]
                text_parts = [transcript_data]
            
            if not segments:
                return None
                
            full_text = ' '.join(text_parts)
            
            return {
                'segments': segments,
                'full_text': full_text,
                'language': data.get('lang', 'en') if isinstance(data, dict) else 'en',
            }
        else:
            return None
            
    except Exception as e:
        print(f"  Error: {e}")
        return None


def save_transcript(
    video_metadata: dict,
    transcript_data: dict,
    output_dir: Path
) -> str:
    """
    Save a single transcript to a JSON file.
    
    Args:
        video_metadata: Video information dictionary
        transcript_data: Transcript data dictionary
        output_dir: Directory to save the transcript
        
    Returns:
        Path to the saved file
    """
    # Create filename from playlist index and video ID
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
    
    return str(filepath)


def fetch_all_transcripts(
    playlist_id: str = PLAYLIST_ID,
    output_dir: Path = TRANSCRIPTS_DIR,
    skip_existing: bool = True,
    api_key: str = SUPADATA_API_KEY
) -> dict:
    """
    Fetch all transcripts from a YouTube playlist using Supadata API.
    
    Args:
        playlist_id: YouTube playlist ID
        output_dir: Directory to save transcripts
        skip_existing: Skip videos that already have transcripts saved
        api_key: Supadata API key
        
    Returns:
        Summary dictionary with success/failure counts and details
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Get existing video IDs if skipping
    existing_ids = set()
    if skip_existing:
        for f in output_dir.glob("*.json"):
            # Skip summary file
            if f.name.startswith('_'):
                continue
            # Extract video ID from filename (format: XXX_VIDEO_ID.json)
            parts = f.stem.split('_', 1)
            if len(parts) == 2:
                existing_ids.add(parts[1])
    
    print(f"Found {len(existing_ids)} existing transcripts")
    
    # Fetch playlist videos
    videos = get_playlist_videos(playlist_id)
    
    results = {
        'total': len(videos),
        'success': 0,
        'failed': 0,
        'skipped': 0,
        'details': []
    }
    
    for video in videos:
        video_id = video['video_id']
        
        # Skip if already exists
        if video_id in existing_ids:
            print(f"Skipping existing: {video['title'][:50]}...")
            results['skipped'] += 1
            results['details'].append({
                'video_id': video_id,
                'title': video['title'],
                'status': 'skipped'
            })
            continue
        
        print(f"\nFetching transcript {video['playlist_index']}/{len(videos)}: {video['title'][:50]}...")
        
        # Add small delay between requests to be nice to the API
        delay = random.uniform(0.5, 1.5)
        time.sleep(delay)
        
        # Fetch transcript using Supadata
        transcript = fetch_transcript_with_timestamps(video_id, api_key)
        
        # Fallback to text-only if timestamps fail
        if not transcript:
            transcript = fetch_transcript(video_id, api_key)
        
        if transcript:
            # Save transcript
            filepath = save_transcript(video, transcript, output_dir)
            print(f"  Saved to: {filepath}")
            results['success'] += 1
            results['details'].append({
                'video_id': video_id,
                'title': video['title'],
                'status': 'success',
                'filepath': filepath
            })
        else:
            print(f"  Failed to fetch transcript")
            results['failed'] += 1
            results['details'].append({
                'video_id': video_id,
                'title': video['title'],
                'status': 'failed'
            })
    
    return results


def load_transcript(filepath: str) -> dict:
    """
    Load a transcript from a JSON file.
    
    Args:
        filepath: Path to the transcript JSON file
        
    Returns:
        Dictionary containing video metadata and transcript
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_all_transcripts(transcripts_dir: Path = TRANSCRIPTS_DIR) -> list[dict]:
    """
    Load all transcripts from the transcripts directory.
    
    Args:
        transcripts_dir: Directory containing transcript JSON files
        
    Returns:
        List of transcript dictionaries, sorted by playlist index
    """
    transcripts = []
    transcripts_dir = Path(transcripts_dir)
    
    for filepath in sorted(transcripts_dir.glob("*.json")):
        # Skip summary files
        if filepath.name.startswith('_'):
            continue
        transcript = load_transcript(str(filepath))
        transcripts.append(transcript)
    
    return transcripts


# ============================================================================
# CLI Interface
# ============================================================================

def main():
    """Main entry point for transcript fetching."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Fetch transcripts from Yasir Qadhi Seerah YouTube playlist using Supadata API'
    )
    parser.add_argument(
        '--playlist-id',
        default=PLAYLIST_ID,
        help='YouTube playlist ID'
    )
    parser.add_argument(
        '--output-dir',
        default=str(TRANSCRIPTS_DIR),
        help='Output directory for transcripts'
    )
    parser.add_argument(
        '--no-skip',
        action='store_true',
        help='Re-fetch existing transcripts'
    )
    parser.add_argument(
        '--api-key',
        default=SUPADATA_API_KEY,
        help='Supadata API key (or set SUPADATA_API_KEY env var)'
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("Seerah Transcript Fetcher (Supadata API)")
    print("=" * 60)
    print(f"Playlist ID: {args.playlist_id}")
    print(f"Output Directory: {args.output_dir}")
    print(f"API Key: {'*' * 20}{args.api_key[-8:]}" if args.api_key else "NOT SET")
    print("=" * 60)
    
    if not args.api_key:
        print("ERROR: Supadata API key not provided!")
        print("Set SUPADATA_API_KEY environment variable or use --api-key flag")
        return
    
    results = fetch_all_transcripts(
        playlist_id=args.playlist_id,
        output_dir=Path(args.output_dir),
        skip_existing=not args.no_skip,
        api_key=args.api_key
    )
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total videos: {results['total']}")
    print(f"Successfully fetched: {results['success']}")
    print(f"Failed: {results['failed']}")
    print(f"Skipped (existing): {results['skipped']}")
    
    # Save summary
    summary_path = Path(args.output_dir) / "_fetch_summary.json"
    with open(summary_path, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\nSummary saved to: {summary_path}")


if __name__ == "__main__":
    main()
