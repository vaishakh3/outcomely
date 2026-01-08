"""
Title classifier module using Gemini.
Scores video titles for prediction likelihood to skip irrelevant content.
"""
import google.generativeai as genai
from config import GEMINI_API_KEY, GEMINI_MODEL


# Configure Gemini
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)


CLASSIFICATION_PROMPT = """Score this finance video title from 0-100 based on how likely it contains VERIFIABLE market predictions.

HIGH SCORE (70-100): Titles with specific predictions like:
- Price targets ("Nifty 25000", "Gold to $2500")
- Market direction ("Bull run in 2024", "Crash coming")
- Stock picks ("Best stocks for 2024")
- Time-bound forecasts ("Q4 outlook", "2024 predictions")

LOW SCORE (0-30): General educational content like:
- Tutorials ("How to invest")
- News summaries ("Budget explained")
- Personal stories ("My journey")
- Generic advice ("5 tips for investing")

TITLE: {title}

Return ONLY a number 0-100, nothing else."""


def classify_title(title: str) -> int:
    """
    Score a video title for prediction likelihood.
    
    Args:
        title: Video title string
        
    Returns:
        Score 0-100 (higher = more likely to contain predictions)
    """
    if not GEMINI_API_KEY:
        # Fallback to keyword matching
        return _keyword_score(title)
    
    try:
        model = genai.GenerativeModel(GEMINI_MODEL)
        response = model.generate_content(
            CLASSIFICATION_PROMPT.format(title=title),
            generation_config={
                "temperature": 0.0,
                "max_output_tokens": 10,
            }
        )
        
        score_text = response.text.strip()
        # Extract number from response
        import re
        match = re.search(r'\d+', score_text)
        if match:
            return min(100, max(0, int(match.group())))
        return 50  # Default if parsing fails
        
    except Exception as e:
        print(f"Classification error: {e}")
        return _keyword_score(title)


def _keyword_score(title: str) -> int:
    """Fallback keyword-based scoring."""
    title_lower = title.lower()
    
    high_value_keywords = [
        'prediction', 'forecast', 'target', 'outlook',
        '2023', '2024', '2025', '2026',
        'nifty', 'sensex', 'crash', 'rally', 'bull', 'bear',
        'buy', 'sell', 'multibagger', 'portfolio'
    ]
    
    low_value_keywords = [
        'how to', 'tutorial', 'explained', 'basics',
        'beginner', 'journey', 'story', 'vlog'
    ]
    
    score = 50
    for kw in high_value_keywords:
        if kw in title_lower:
            score += 8
    for kw in low_value_keywords:
        if kw in title_lower:
            score -= 15
    
    return min(100, max(0, score))


def classify_titles_batch(titles: list[str]) -> list[int]:
    """
    Classify multiple titles in a single API call for efficiency.
    
    Args:
        titles: List of video titles
        
    Returns:
        List of scores (0-100)
    """
    if not GEMINI_API_KEY or not titles:
        return [_keyword_score(t) for t in titles]
    
    if len(titles) == 1:
        return [classify_title(titles[0])]
    
    batch_prompt = """Score each video title from 0-100 for prediction likelihood.
Return scores as comma-separated numbers in order.

Titles:
"""
    for i, title in enumerate(titles[:10], 1):  # Max 10 per batch
        batch_prompt += f"{i}. {title}\n"
    
    batch_prompt += "\nReturn ONLY comma-separated numbers like: 75, 30, 85, 40"
    
    try:
        model = genai.GenerativeModel(GEMINI_MODEL)
        response = model.generate_content(
            batch_prompt,
            generation_config={
                "temperature": 0.0,
                "max_output_tokens": 100,
            }
        )
        
        import re
        scores_text = response.text.strip()
        numbers = re.findall(r'\d+', scores_text)
        scores = [min(100, max(0, int(n))) for n in numbers]
        
        # Pad with fallback if needed
        while len(scores) < len(titles):
            scores.append(_keyword_score(titles[len(scores)]))
        
        return scores[:len(titles)]
        
    except Exception as e:
        print(f"Batch classification error: {e}")
        return [_keyword_score(t) for t in titles]


def filter_videos_by_title(videos: list[dict], threshold: int = 50) -> list[dict]:
    """
    Filter videos to only those likely to contain predictions.
    
    Args:
        videos: List of video dicts with 'title' key
        threshold: Minimum score to include (default 50)
        
    Returns:
        Filtered list of videos
    """
    if not videos:
        return []
    
    titles = [v.get('title', '') for v in videos]
    scores = classify_titles_batch(titles)
    
    filtered = []
    for video, score in zip(videos, scores):
        video['prediction_score'] = score
        if score >= threshold:
            filtered.append(video)
        else:
            print(f"  Skipping (score {score}): {video.get('title', '')[:50]}")
    
    print(f"  Filtered: {len(filtered)}/{len(videos)} videos passed threshold {threshold}")
    return filtered
