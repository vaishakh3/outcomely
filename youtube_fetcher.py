"""
YouTube video and transcript fetching module.
Uses youtube-transcript-api for transcripts and yt-dlp for video metadata.
"""
import re
import time
from datetime import datetime
from typing import Optional
import subprocess
import json
import sys

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    TranscriptsDisabled,
    NoTranscriptFound,
    VideoUnavailable
)

from config import CREATORS, PREDICTION_KEYWORDS, START_DATE, END_DATE, Creator
from database import get_db


def get_channel_videos(channel_url: str, limit: int = 50, channel_id: str = None) -> list[dict]:
    """
    Fetch video list from a YouTube channel using yt-dlp.
    
    Args:
        channel_url: YouTube channel URL
        limit: Maximum number of videos to fetch
        channel_id: Optional channel ID for fallback
        
    Returns:
        List of video metadata dictionaries
    """
    # Try different URL formats
    urls_to_try = [
        f"https://www.youtube.com/channel/{channel_id}/videos" if channel_id else None,
        f"{channel_url}/videos",
        channel_url,
        f"https://www.youtube.com/channel/{channel_id}" if channel_id else None,
    ]
    
    urls_to_try = [u for u in urls_to_try if u]  # Remove None values
    
    for url in urls_to_try:
        try:
            # Use sys.executable to run yt-dlp as a module
            cmd = [
                sys.executable,
                "-m", "yt_dlp",
                "--no-download",
                "--flat-playlist",
                "--print", '{"id": "%(id)s", "title": "%(title)s", "upload_date": "%(upload_date)s"}',
                "--playlist-end", str(limit),
                url
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            
            if result.returncode != 0:
                # Debug info
                # print(f"Debug: yt-dlp failed for {url} with: {result.stderr}")
                continue  # Try next URL format
            
            videos = []
            for line in result.stdout.strip().split('\n'):
                if line:
                    try:
                        video = json.loads(line)
                        if video.get('id') and video.get('title'):
                            # Convert YYYYMMDD to YYYY-MM-DD
                            raw_date = video.get('upload_date', '')
                            formatted_date = ""
                            if raw_date and len(raw_date) == 8:
                                formatted_date = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:]}"

                            videos.append({
                                'video_id': video['id'],
                                'title': video['title'],
                                'upload_date': formatted_date,
                                'url': f"https://www.youtube.com/watch?v={video['id']}"
                            })
                    except json.JSONDecodeError:
                        continue
            
            if videos:
                return videos
            
        except subprocess.TimeoutExpired:
            continue
        except Exception as e:
            continue
    
    print(f"Error: Could not fetch videos from any URL format")
    return []


def filter_prediction_videos(videos: list[dict]) -> list[dict]:
    """
    Filter videos to only include those likely containing predictions.
    
    Args:
        videos: List of video metadata dictionaries
        
    Returns:
        Filtered list of relevant videos
    """
    filtered = []
    
    for video in videos:
        title_lower = video['title'].lower()
        
        # Check if any prediction keyword is in the title
        if any(keyword in title_lower for keyword in PREDICTION_KEYWORDS):
            filtered.append(video)
            continue
        
        # Also include videos with year mentions (often contain predictions)
        year_pattern = r'202[1-5]'
        if re.search(year_pattern, video['title']):
            filtered.append(video)
    
    return filtered


def filter_by_date_range(videos: list[dict], 
                         start_date: str = START_DATE, 
                         end_date: str = END_DATE) -> list[dict]:
    """
    Filter videos by date range.
    Videos without valid dates are included by default.
    
    Args:
        videos: List of video metadata dictionaries
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        
    Returns:
        Filtered list of videos within date range
    """
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    
    filtered = []
    for video in videos:
        upload_date = video.get('upload_date', '')
        
        # Include videos without valid dates (we'll get date from transcript later)
        if not upload_date or upload_date == 'NA':
            video['publish_date'] = ''  # Unknown date
            filtered.append(video)
            continue
            
        try:
            # Expecting YYYY-MM-DD now as it was formatted in get_channel_videos
            if '-' in upload_date:
                video_date = datetime.strptime(upload_date, "%Y-%m-%d")
            else:
                # Fallback for YYYYMMDD
                video_date = datetime.strptime(upload_date, "%Y%m%d")
                
            if start <= video_date <= end:
                video['publish_date'] = video_date.strftime("%Y-%m-%d")
                filtered.append(video)
        except ValueError:
            # Include if date can't be parsed
            video['publish_date'] = ''
            filtered.append(video)
    
    return filtered


def get_transcript(video_id: str) -> Optional[list[dict]]:
    """
    Fetch transcript for a YouTube video.
    
    Args:
        video_id: YouTube video ID
        
    Returns:
        List of transcript segments with text and timestamps, or None if unavailable
    """
    try:
        api = YouTubeTranscriptApi()
        # list() returns a TranscriptList object
        transcript_list = api.list(video_id)
        
        # Try to find a manually created transcript in Hindi or English
        try:
            transcript = transcript_list.find_transcript(['hi', 'en', 'en-IN'])
        except Exception:
            # Fallback to any available transcript (generated or otherwise)
            try:
                transcript = transcript_list.find_generated_transcript(['hi', 'en', 'en-IN'])
            except Exception:
                transcript = next(iter(transcript_list))
        
        data = transcript.fetch()
        return [{'text': item['text'], 'start': item['start'], 'duration': item['duration']} for item in data]
        
    except (TranscriptsDisabled, VideoUnavailable):
        return None
    except Exception as e:
        # print(f"Error fetching transcript for {video_id}: {e}")
        return None
        
    except TranscriptsDisabled:
        print(f"Transcripts are disabled for video {video_id}")
        return None
    except NoTranscriptFound:
        print(f"No transcript found for video {video_id}")
        return None
    except VideoUnavailable:
        print(f"Video {video_id} is unavailable")
        return None
    except Exception as e:
        print(f"Error fetching transcript for {video_id}: {e}")
        return None


def format_transcript(transcript_data: list[dict]) -> str:
    """
    Format transcript data into a single text with timestamps.
    
    Args:
        transcript_data: List of transcript segments
        
    Returns:
        Formatted transcript string
    """
    formatted_lines = []
    
    for segment in transcript_data:
        start_time = segment.get('start', 0)
        text = segment.get('text', '').strip()
        
        # Convert seconds to MM:SS format
        minutes = int(start_time // 60)
        seconds = int(start_time % 60)
        timestamp = f"[{minutes:02d}:{seconds:02d}]"
        
        formatted_lines.append(f"{timestamp} {text}")
    
    return '\n'.join(formatted_lines)


def get_transcript_text_only(transcript_data: list[dict]) -> str:
    """
    Get transcript as plain text without timestamps.
    
    Args:
        transcript_data: List of transcript segments
        
    Returns:
        Plain text transcript
    """
    return ' '.join(segment.get('text', '').strip() for segment in transcript_data)


def fetch_creator_videos(creator_slug: str, limit: int = 50, 
                        save_to_db: bool = True) -> list[dict]:
    """
    Fetch videos for a specific creator.
    
    Args:
        creator_slug: Creator's slug identifier
        limit: Maximum videos to fetch
        save_to_db: Whether to save videos to database
        
    Returns:
        List of fetched videos
    """
    from config import get_creator_by_slug
    
    creator = get_creator_by_slug(creator_slug)
    if not creator:
        print(f"Creator '{creator_slug}' not found")
        return []
    
    print(f"Fetching videos for {creator.name}...")
    
    # Get videos from channel
    videos = get_channel_videos(creator.channel_url, limit, channel_id=creator.channel_id)
    print(f"  Found {len(videos)} total videos")
    
    # Filter by date range
    videos = filter_by_date_range(videos)
    print(f"  {len(videos)} videos in date range")
    
    # Filter for prediction-related content
    videos = filter_prediction_videos(videos)
    print(f"  {len(videos)} prediction-related videos")
    
    if save_to_db and videos:
        db = get_db()
        
        # Ensure creator exists in database
        db.add_creator(
            name=creator.name,
            channel_id=creator.channel_id,
            channel_url=creator.channel_url,
            slug=creator.slug,
            description=creator.description or ""
        )
        
        creator_data = db.get_creator_by_slug(creator.slug)
        if not creator_data:
            print(f"  Error: Could not get creator from database")
            return videos
        
        # Save videos
        saved_count = 0
        for video in videos:
            existing = db.get_video_by_video_id(video['video_id'])
            if not existing:
                db.add_video(
                    creator_id=creator_data['id'],
                    video_id=video['video_id'],
                    title=video['title'],
                    url=video['url'],
                    publish_date=video.get('publish_date', '')
                )
                saved_count += 1
        
        print(f"  Saved {saved_count} new videos to database")
    
    return videos


def fetch_transcripts_for_videos(limit: int = 10, delay: float = 1.0) -> int:
    """
    Fetch transcripts for videos that don't have them yet.
    
    Args:
        limit: Maximum number of videos to process
        delay: Delay between requests (seconds)
        
    Returns:
        Number of transcripts fetched
    """
    db = get_db()
    
    # Get videos without transcripts
    conn = db._get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, video_id, title FROM videos 
        WHERE transcript = '' OR transcript IS NULL
        LIMIT ?
    """, (limit,))
    videos = cursor.fetchall()
    conn.close()
    
    print(f"Fetching transcripts for {len(videos)} videos...")
    
    fetched_count = 0
    for video in videos:
        video_db_id = video['id']
        video_id = video['video_id']
        title = video['title']
        
        print(f"  Fetching transcript for: {title[:50]}...")
        
        transcript_data = get_transcript(video_id)
        
        if transcript_data:
            formatted = format_transcript(transcript_data)
            
            # Update video with transcript
            conn = db._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE videos SET transcript = ? WHERE id = ?",
                (formatted, video_db_id)
            )
            conn.commit()
            conn.close()
            
            fetched_count += 1
            print(f"    ✓ Transcript saved ({len(formatted)} chars)")
        else:
            print(f"    ✗ No transcript available")
        
        # Rate limiting
        time.sleep(delay)
    
    return fetched_count


def fetch_all_creators(limit_per_creator: int = 50):
    """
    Fetch videos for all configured creators.
    
    Args:
        limit_per_creator: Maximum videos per creator
    """
    for creator in CREATORS:
        fetch_creator_videos(creator.slug, limit=limit_per_creator)
        print()
    
    # Fetch transcripts
    print("Fetching transcripts...")
    fetch_transcripts_for_videos(limit=100)


def fetch_all_creators_optimized(limit_per_creator: int = 50, score_threshold: int = 50):
    """
    Optimized fetch using YouTube API and title classification.
    
    This function:
    1. Uses YouTube Data API v3 for faster metadata fetching (if available)
    2. Classifies titles with Gemini to skip irrelevant videos
    3. Only fetches transcripts for high-value videos
    
    Args:
        limit_per_creator: Maximum videos per creator
        score_threshold: Minimum title score to fetch transcript (0-100)
    """
    from youtube_api import get_channel_videos_api, YOUTUBE_API_KEY
    from title_classifier import filter_videos_by_title
    
    db = get_db()
    
    for creator in CREATORS:
        print(f"Fetching videos for {creator.name}...")
        
        # Ensure creator is in database
        db.add_creator(
            name=creator.name,
            channel_id=creator.channel_id,
            channel_url=creator.channel_url,
            slug=creator.slug,
            description=creator.description or ""
        )
        
        creator_data = db.get_creator_by_slug(creator.slug)
        if not creator_data:
            print(f"  Error: Could not get creator from database")
            continue
        
        # Try YouTube API first (faster), fall back to yt-dlp
        videos = []
        if YOUTUBE_API_KEY:
            print(f"  Using YouTube Data API...")
            videos = get_channel_videos_api(creator.channel_id, max_results=limit_per_creator)
        
        if not videos:
            print(f"  Falling back to yt-dlp...")
            videos = get_channel_videos(
                creator.channel_url, 
                limit=limit_per_creator,
                channel_id=creator.channel_id
            )
        
        print(f"  Found {len(videos)} videos")
        
        if not videos:
            continue
        
        # Filter by date range
        videos = filter_by_date_range(videos)
        print(f"  {len(videos)} videos in date range")
        
        # Smart title filtering - skip irrelevant videos
        print(f"  Classifying titles...")
        videos = filter_videos_by_title(videos, threshold=score_threshold)
        
        # Save videos to database
        saved_count = 0
        for video in videos:
            existing = db.get_video_by_video_id(video['video_id'])
            if not existing:
                db.add_video(
                    creator_id=creator_data['id'],
                    video_id=video['video_id'],
                    title=video['title'],
                    url=video['url'],
                    publish_date=video.get('upload_date', '')
                )
                saved_count += 1
        
        print(f"  Saved {saved_count} new videos to database")
        print()
    
    # Fetch transcripts only for high-value videos
    print("Fetching transcripts for high-value videos...")
    fetch_transcripts_for_videos(limit=100)
