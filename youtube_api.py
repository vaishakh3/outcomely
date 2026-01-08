"""
YouTube Data API v3 module for efficient video metadata fetching.
Replaces slow yt-dlp scraping with official API calls.
"""
import os
from datetime import datetime
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")


def get_channel_videos_api(channel_id: str, max_results: int = 50) -> list[dict]:
    """
    Fetch videos from a YouTube channel using the Data API v3.
    
    Args:
        channel_id: YouTube channel ID (e.g., UCqW8jxh4tH1Z1sWPbkGWL4g)
        max_results: Maximum results to return (API max is 50 per call)
        
    Returns:
        List of video metadata dictionaries
    """
    if not YOUTUBE_API_KEY:
        print("Warning: YOUTUBE_API_KEY not set, falling back to yt-dlp")
        return []
    
    try:
        from googleapiclient.discovery import build
        from googleapiclient.errors import HttpError
        
        youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
        
        videos = []
        next_page_token = None
        
        while len(videos) < max_results:
            request = youtube.search().list(
                channelId=channel_id,
                part='snippet',
                order='date',
                maxResults=min(50, max_results - len(videos)),
                type='video',
                pageToken=next_page_token
            )
            response = request.execute()
            
            for item in response.get('items', []):
                snippet = item.get('snippet', {})
                video_id = item.get('id', {}).get('videoId', '')
                
                if video_id:
                    # Parse publish date
                    published_at = snippet.get('publishedAt', '')
                    publish_date = ''
                    if published_at:
                        try:
                            dt = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
                            publish_date = dt.strftime('%Y-%m-%d')
                        except:
                            pass
                    
                    videos.append({
                        'video_id': video_id,
                        'title': snippet.get('title', ''),
                        'upload_date': publish_date,
                        'url': f"https://www.youtube.com/watch?v={video_id}",
                        'description': snippet.get('description', '')[:500],
                        'channel_title': snippet.get('channelTitle', '')
                    })
            
            next_page_token = response.get('nextPageToken')
            if not next_page_token:
                break
        
        return videos
        
    except ImportError:
        print("google-api-python-client not installed. Run: pip install google-api-python-client")
        return []
    except Exception as e:
        print(f"YouTube API error: {e}")
        return []


def get_video_details_batch(video_ids: list[str]) -> dict:
    """
    Get detailed info for multiple videos in a single API call.
    
    Args:
        video_ids: List of video IDs (max 50)
        
    Returns:
        Dictionary mapping video_id to video details
    """
    if not YOUTUBE_API_KEY or not video_ids:
        return {}
    
    try:
        from googleapiclient.discovery import build
        
        youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
        
        # API allows up to 50 IDs per call
        request = youtube.videos().list(
            id=','.join(video_ids[:50]),
            part='snippet,statistics,contentDetails'
        )
        response = request.execute()
        
        results = {}
        for item in response.get('items', []):
            vid = item['id']
            snippet = item.get('snippet', {})
            stats = item.get('statistics', {})
            
            results[vid] = {
                'title': snippet.get('title', ''),
                'description': snippet.get('description', ''),
                'publish_date': snippet.get('publishedAt', ''),
                'view_count': int(stats.get('viewCount', 0)),
                'like_count': int(stats.get('likeCount', 0)),
                'duration': item.get('contentDetails', {}).get('duration', '')
            }
        
        return results
        
    except Exception as e:
        print(f"Error fetching video details: {e}")
        return {}


def check_api_quota() -> bool:
    """Check if YouTube API is configured and working."""
    if not YOUTUBE_API_KEY:
        return False
    
    try:
        from googleapiclient.discovery import build
        youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
        # Simple test call
        youtube.videos().list(id='dQw4w9WgXcQ', part='id').execute()
        return True
    except Exception:
        return False
