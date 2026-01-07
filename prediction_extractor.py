"""
Prediction extraction module using Gemini API.
Parses video transcripts to identify and structure prediction statements.
"""
import json
import time
import re
from typing import Optional
from datetime import datetime

import google.generativeai as genai

from config import (
    GEMINI_API_KEY, 
    GEMINI_MODEL, 
    GEMINI_RATE_LIMIT_RPM,
    MARKET_ASSETS
)
from database import get_db


# Configure Gemini
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)


EXTRACTION_PROMPT = """You are an expert financial analyst. Analyze this YouTube video transcript and extract ALL prediction statements made by the speaker.

A prediction is any statement about:
- Future market direction (bull/bear market, rally, crash)
- Price targets for stocks, indices, commodities
- Economic forecasts (inflation, interest rates, GDP)
- Specific stock picks or recommendations with expected outcomes
- Timebound claims about market performance

For each prediction found, extract:
1. statement: The exact prediction (quote or close paraphrase)
2. timestamp: The video timestamp where this was said (in MM:SS format)
3. asset: What asset/index/market is being discussed (e.g., "NIFTY 50", "Reliance", "Gold")
4. direction: Is the prediction bullish, bearish, or neutral?
5. target: Any specific price target mentioned (or null if none)
6. timeframe: When was the prediction expected to come true? (e.g., "Dec 2023", "6 months", "end of year")
7. confidence_level: How confident did the speaker seem? (high, medium, low)

IMPORTANT RULES:
- Only extract CLEAR predictions, not vague commentary
- Include the timestamp from the transcript
- If no specific timeframe is mentioned, infer from context or use "unspecified"
- Focus on actionable predictions that can be verified against market data

Return your response as a JSON array of prediction objects. If no predictions are found, return an empty array [].

VIDEO TITLE: {title}
VIDEO DATE: {publish_date}

TRANSCRIPT:
{transcript}

Respond ONLY with the JSON array, no other text."""


def extract_predictions_from_transcript(
    video_db_id: int,
    video_id: str,
    title: str,
    publish_date: str,
    transcript: str
) -> list[dict]:
    """
    Extract predictions from a video transcript using Gemini.
    
    Args:
        video_db_id: Database ID of the video
        video_id: YouTube video ID
        title: Video title
        publish_date: Video publish date
        transcript: Video transcript text
        
    Returns:
        List of extracted predictions
    """
    if not GEMINI_API_KEY:
        print("Warning: Gemini API key not configured")
        return []
    
    # Truncate transcript if too long (Gemini has token limits)
    max_transcript_length = 25000
    if len(transcript) > max_transcript_length:
        transcript = transcript[:max_transcript_length] + "\n[TRANSCRIPT TRUNCATED]"
    
    prompt = EXTRACTION_PROMPT.format(
        title=title,
        publish_date=publish_date,
        transcript=transcript
    )
    
    try:
        model = genai.GenerativeModel(GEMINI_MODEL)
        response = model.generate_content(
            prompt,
            generation_config={
                "temperature": 0.1,
                "max_output_tokens": 4096,
            }
        )
        
        # Parse response
        response_text = response.text.strip()
        
        # Clean up response - remove markdown code blocks if present
        if response_text.startswith("```"):
            # Remove opening ```json or ``` and closing ```
            response_text = re.sub(r'^```(?:json)?\s*', '', response_text)
            response_text = re.sub(r'\s*```$', '', response_text)
        
        predictions = json.loads(response_text)
        
        if not isinstance(predictions, list):
            print(f"Warning: Expected list, got {type(predictions)}")
            return []
        
        # Validate and clean predictions
        cleaned_predictions = []
        for pred in predictions:
            if isinstance(pred, dict) and pred.get('statement'):
                cleaned_pred = {
                    'video_db_id': video_db_id,
                    'statement': str(pred.get('statement', '')),
                    'timestamp': str(pred.get('timestamp', '00:00')),
                    'asset': normalize_asset(str(pred.get('asset', 'Market'))),
                    'direction': str(pred.get('direction', 'neutral')).lower(),
                    'target': str(pred.get('target')) if pred.get('target') else None,
                    'timeframe': str(pred.get('timeframe', 'unspecified')),
                    'confidence_level': str(pred.get('confidence_level', 'medium')).lower()
                }
                cleaned_predictions.append(cleaned_pred)
        
        return cleaned_predictions
        
    except json.JSONDecodeError as e:
        print(f"Error parsing Gemini response as JSON: {e}")
        print(f"Response was: {response_text[:500]}...")
        return []
    except Exception as e:
        print(f"Error calling Gemini API: {e}")
        return []


def normalize_asset(asset: str) -> str:
    """
    Normalize asset names to standard format.
    
    Args:
        asset: Raw asset name from extraction
        
    Returns:
        Normalized asset name
    """
    asset_lower = asset.lower().strip()
    
    # Check against known assets
    for standard_name, aliases in MARKET_ASSETS.items():
        if asset_lower in aliases or asset_lower == standard_name.lower():
            return standard_name
    
    # Return capitalized version if not found
    return asset.title()


def save_predictions_to_db(predictions: list[dict]) -> int:
    """
    Save extracted predictions to the database.
    
    Args:
        predictions: List of prediction dictionaries
        
    Returns:
        Number of predictions saved
    """
    db = get_db()
    saved = 0
    
    for pred in predictions:
        try:
            db.add_prediction(
                video_id=pred['video_db_id'],
                statement=pred['statement'],
                timestamp=pred['timestamp'],
                asset=pred['asset'],
                direction=pred['direction'],
                target=pred['target'] or '',
                timeframe=pred['timeframe'],
                confidence_level=pred['confidence_level']
            )
            saved += 1
        except Exception as e:
            print(f"Error saving prediction: {e}")
    
    return saved


def process_unprocessed_videos(limit: int = 10, delay: float = 6.0) -> dict:
    """
    Process videos that haven't been analyzed for predictions yet.
    
    Args:
        limit: Maximum number of videos to process
        delay: Delay between API calls (seconds) - respects rate limits
        
    Returns:
        Summary of processing results
    """
    db = get_db()
    videos = db.get_unprocessed_videos(limit=limit)
    
    print(f"Processing {len(videos)} unprocessed videos...")
    
    results = {
        'videos_processed': 0,
        'predictions_extracted': 0,
        'errors': 0
    }
    
    for video in videos:
        print(f"\nProcessing: {video['title'][:50]}...")
        
        if not video.get('transcript'):
            print("  Skipping - no transcript available")
            continue
        
        predictions = extract_predictions_from_transcript(
            video_db_id=video['id'],
            video_id=video['video_id'],
            title=video['title'],
            publish_date=video.get('publish_date', ''),
            transcript=video['transcript']
        )
        
        if predictions:
            saved = save_predictions_to_db(predictions)
            print(f"  ✓ Extracted {len(predictions)} predictions, saved {saved}")
            results['predictions_extracted'] += saved
        else:
            print("  No predictions found")
        
        # Mark video as processed
        db.mark_video_processed(video['id'])
        results['videos_processed'] += 1
        
        # Rate limiting - Gemini free tier is 10 RPM
        time.sleep(delay)
    
    return results


def extract_predictions_for_video(video_id: str) -> list[dict]:
    """
    Extract predictions for a specific video by YouTube video ID.
    
    Args:
        video_id: YouTube video ID
        
    Returns:
        List of extracted predictions
    """
    db = get_db()
    video = db.get_video_by_video_id(video_id)
    
    if not video:
        print(f"Video {video_id} not found in database")
        return []
    
    if not video.get('transcript'):
        print(f"No transcript available for video {video_id}")
        return []
    
    predictions = extract_predictions_from_transcript(
        video_db_id=video['id'],
        video_id=video['video_id'],
        title=video['title'],
        publish_date=video.get('publish_date', ''),
        transcript=video['transcript']
    )
    
    if predictions:
        saved = save_predictions_to_db(predictions)
        db.mark_video_processed(video['id'])
        print(f"Extracted {len(predictions)} predictions, saved {saved}")
    
    return predictions
