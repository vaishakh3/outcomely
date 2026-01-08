"""
Title-based prediction extraction.
Extracts predictions directly from video titles when transcripts are unavailable.
"""
import time
import json
import re
import google.generativeai as genai

from config import GEMINI_API_KEY, GEMINI_MODEL
from database import get_db


if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)


TITLE_EXTRACTION_PROMPT = """Analyze these finance video titles and extract any VERIFIABLE predictions.

For each title that contains a prediction, extract:
- title_index: The number of the title (1-based)
- statement: The prediction statement
- asset: What's being predicted (NIFTY, SENSEX, Gold, specific stocks, Indian Markets, etc.)
- direction: bullish, bearish, or neutral
- target: Any price target mentioned (or null)
- timeframe: When it should happen (2023, 2024, 2025, Q1 2024, etc.)

TITLES:
{titles}

Return a JSON array of predictions. Only include titles with CLEAR, VERIFIABLE predictions.
Example: [{"title_index": 1, "statement": "Nifty will reach 25000", "asset": "NIFTY 50", "direction": "bullish", "target": "25000", "timeframe": "2024"}]

If no predictions found, return [].
"""


def extract_predictions_from_titles(videos: list[dict], batch_size: int = 10) -> list[dict]:
    """
    Extract predictions from video titles in batches.
    
    Args:
        videos: List of video dicts with 'id', 'title', 'publish_date'
        batch_size: Number of titles per Gemini call
        
    Returns:
        List of prediction dicts
    """
    if not GEMINI_API_KEY:
        print("Gemini API key required")
        return []
    
    all_predictions = []
    
    for i in range(0, len(videos), batch_size):
        batch = videos[i:i+batch_size]
        
        # Format titles
        titles_text = ""
        for j, v in enumerate(batch, 1):
            titles_text += f"{j}. {v['title']} (Date: {v.get('publish_date', 'Unknown')})\n"
        
        try:
            model = genai.GenerativeModel(GEMINI_MODEL)
            response = model.generate_content(
                TITLE_EXTRACTION_PROMPT.format(titles=titles_text),
                generation_config={
                    "temperature": 0.1,
                    "max_output_tokens": 2000,
                }
            )
            
            # Parse response
            response_text = response.text.strip()
            # Remove markdown code blocks if present
            if response_text.startswith("```"):
                response_text = re.sub(r'^```(?:json)?\s*', '', response_text)
                response_text = re.sub(r'\s*```$', '', response_text)
            
            predictions = json.loads(response_text)
            
            if isinstance(predictions, list):
                for pred in predictions:
                    # Handle both 'title_index' and numeric index
                    idx = pred.get('title_index', pred.get('index', 1)) - 1
                    if 0 <= idx < len(batch):
                        pred['video_db_id'] = batch[idx]['id']
                        pred['video_title'] = batch[idx]['title']
                        pred['publish_date'] = batch[idx].get('publish_date', '')
                        all_predictions.append(pred)
                        print(f"  ✓ Found: {pred.get('statement', '')[:60]}...")
            
            time.sleep(4)  # Rate limiting
            
        except json.JSONDecodeError as e:
            print(f"  JSON parse error: {e}")
            print(f"  Response: {response_text[:200]}...")
        except Exception as e:
            if "429" in str(e):
                print(f"  Rate limit hit, waiting 60s...")
                time.sleep(60)
            else:
                print(f"  Error: {e}")
    
    return all_predictions


def save_title_predictions(predictions: list[dict]) -> int:
    """Save predictions extracted from titles to database."""
    db = get_db()
    saved = 0
    
    for pred in predictions:
        try:
            db.add_prediction(
                video_id=pred['video_db_id'],
                statement=pred.get('statement', ''),
                timestamp='00:00',
                asset=pred.get('asset', 'Market'),
                direction=pred.get('direction', 'neutral'),
                target=pred.get('target', ''),
                timeframe=pred.get('timeframe', 'unspecified'),
                confidence_level='medium'
            )
            saved += 1
        except Exception as e:
            print(f"  Save error: {e}")
    
    return saved


def run_title_extraction(limit: int = 100):
    """Main function to extract predictions from video titles."""
    db = get_db()
    conn = db._get_connection()
    cursor = conn.cursor()
    
    # Get videos without predictions
    cursor.execute("""
        SELECT v.id, v.video_id, v.title, v.publish_date 
        FROM videos v
        WHERE v.id NOT IN (SELECT DISTINCT video_id FROM predictions)
        LIMIT ?
    """, (limit,))
    videos = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    print(f"Extracting predictions from {len(videos)} video titles...")
    
    predictions = extract_predictions_from_titles(videos)
    
    if predictions:
        saved = save_title_predictions(predictions)
        print(f"\n✓ Saved {saved} predictions from titles")
        
        # Recalculate scores
        db.recalculate_creator_scores()
        print("✓ Scores recalculated")
    else:
        print("No predictions found in titles")
    
    return len(predictions)


if __name__ == "__main__":
    run_title_extraction(limit=100)
