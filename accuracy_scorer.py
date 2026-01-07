"""
Accuracy scoring module.
Compares predictions against actual market outcomes and calculates scores.
Uses Gemini API for semantic comparison when needed.
"""
import json
import time
from typing import Optional
from datetime import datetime

import google.generativeai as genai

from config import (
    GEMINI_API_KEY,
    GEMINI_MODEL,
    SCORING_WEIGHTS,
    TARGET_TOLERANCE,
    TIMING_TOLERANCE_DAYS
)
from database import get_db
from market_data import get_market_outcome, search_market_outcome_exa


# Configure Gemini
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)


VERIFICATION_PROMPT = """You are an expert financial analyst verifying a prediction against actual market outcomes.

PREDICTION:
- Statement: {statement}
- Asset: {asset}
- Direction: {direction}
- Target: {target}
- Timeframe: {timeframe}
- Made on: {prediction_date}

ACTUAL MARKET DATA:
{market_data}

ADDITIONAL CONTEXT (from web search):
{search_context}

Analyze whether this prediction was accurate. Consider:
1. Was the direction (bullish/bearish) correct?
2. Was any price target achieved?
3. Was the timing accurate?

Respond with a JSON object:
{{
    "direction_correct": true/false,
    "direction_explanation": "brief explanation",
    "target_accuracy": 0.0-1.0 (1.0 if fully met, 0.5 if partially met, 0 if missed),
    "target_explanation": "brief explanation",
    "timing_accuracy": 0.0-1.0 (1.0 if on time, lower if early/late),
    "timing_explanation": "brief explanation",
    "overall_explanation": "2-3 sentence summary of how the prediction held up against reality"
}}

Respond ONLY with the JSON object, no other text."""


def calculate_base_score(
    market_outcome: dict,
    direction: str,
    target: Optional[str]
) -> dict:
    """
    Calculate base accuracy score from market data without AI.
    
    Args:
        market_outcome: Market outcome data dictionary
        direction: Predicted direction
        target: Predicted target price
        
    Returns:
        Dictionary with score components
    """
    scores = {
        'direction_correct': False,
        'direction_score': 0.0,
        'target_score': 0.0,
        'timing_score': 0.0,
        'overall_score': 0.0
    }
    
    if market_outcome.get('outcome') != 'verified':
        return scores
    
    actual_direction = market_outcome.get('actual_direction', 'neutral')
    
    # Direction scoring
    if direction == actual_direction:
        scores['direction_correct'] = True
        scores['direction_score'] = 1.0
    elif (direction in ['bullish', 'bearish'] and 
          actual_direction == 'neutral'):
        # Partial credit if prediction was directional but result was flat
        scores['direction_score'] = 0.3
    else:
        scores['direction_score'] = 0.0
    
    # Target scoring
    if target and market_outcome.get('target_reached') is not None:
        if market_outcome['target_reached']:
            scores['target_score'] = 1.0
        else:
            # Calculate how close we got
            try:
                import re
                target_price = float(re.sub(r'[^\d.]', '', str(target)))
                end_price = market_outcome.get('end_price', 0)
                high_price = market_outcome.get('period_high', 0)
                
                if direction == 'bullish' and high_price:
                    closeness = min(high_price / target_price, 1.0)
                    scores['target_score'] = closeness * 0.7  # Max 70% for missing
                elif direction == 'bearish':
                    low_price = market_outcome.get('period_low', end_price)
                    closeness = min(target_price / low_price, 1.0) if low_price else 0
                    scores['target_score'] = closeness * 0.7
            except:
                scores['target_score'] = 0.5  # Unknown
    elif not target:
        # No target specified, give neutral score
        scores['target_score'] = 0.5
    
    # Timing scoring
    # If we verified within the timeframe, timing was accurate
    scores['timing_score'] = 0.8  # Default for verified predictions
    
    # Calculate overall score
    scores['overall_score'] = (
        scores['direction_score'] * SCORING_WEIGHTS['direction'] +
        scores['target_score'] * SCORING_WEIGHTS['target'] +
        scores['timing_score'] * SCORING_WEIGHTS['timing']
    )
    
    return scores


def verify_with_gemini(
    statement: str,
    asset: str,
    direction: str,
    target: Optional[str],
    timeframe: str,
    prediction_date: str,
    market_outcome: dict,
    search_results: Optional[dict] = None
) -> dict:
    """
    Use Gemini to perform semantic verification of a prediction.
    
    Args:
        statement: Original prediction statement
        asset: Predicted asset
        direction: Predicted direction
        target: Predicted target
        timeframe: Predicted timeframe
        prediction_date: When prediction was made
        market_outcome: Market data outcome
        search_results: Optional Exa search results
        
    Returns:
        Verification result dictionary
    """
    if not GEMINI_API_KEY:
        # Fall back to base scoring
        base_scores = calculate_base_score(market_outcome, direction, target)
        return {
            'direction_correct': base_scores['direction_correct'],
            'target_accuracy': base_scores['target_score'],
            'timing_accuracy': base_scores['timing_score'],
            'overall_explanation': 'Verified using market data only (no AI analysis)'
        }
    
    # Format market data for prompt
    market_data_str = json.dumps(market_outcome, indent=2, default=str)
    
    # Format search context
    search_context = "No additional context available."
    if search_results and search_results.get('summaries'):
        search_context = "\n".join(search_results['summaries'][:3])
    
    prompt = VERIFICATION_PROMPT.format(
        statement=statement,
        asset=asset,
        direction=direction,
        target=target or "Not specified",
        timeframe=timeframe,
        prediction_date=prediction_date,
        market_data=market_data_str,
        search_context=search_context
    )
    
    try:
        model = genai.GenerativeModel(GEMINI_MODEL)
        response = model.generate_content(
            prompt,
            generation_config={
                "temperature": 0.1,
                "max_output_tokens": 1024,
            }
        )
        
        response_text = response.text.strip()
        
        # Clean up markdown if present
        if response_text.startswith("```"):
            import re
            response_text = re.sub(r'^```(?:json)?\s*', '', response_text)
            response_text = re.sub(r'\s*```$', '', response_text)
        
        return json.loads(response_text)
        
    except Exception as e:
        print(f"Error in Gemini verification: {e}")
        # Fall back to base scoring
        base_scores = calculate_base_score(market_outcome, direction, target)
        return {
            'direction_correct': base_scores['direction_correct'],
            'target_accuracy': base_scores['target_score'],
            'timing_accuracy': base_scores['timing_score'],
            'overall_explanation': f'Verified using market data only (AI error: {str(e)[:50]})'
        }


def verify_prediction(prediction: dict) -> dict:
    """
    Verify a single prediction against market outcomes.
    
    Args:
        prediction: Prediction dictionary from database
        
    Returns:
        Verification result dictionary
    """
    # Get market outcome
    market_outcome = get_market_outcome(
        asset=prediction['asset'],
        direction=prediction['direction'],
        target=prediction.get('target'),
        timeframe=prediction['timeframe'],
        prediction_date=prediction.get('publish_date', prediction.get('created_at', ''))[:10]
    )
    
    if market_outcome['outcome'] == 'pending':
        return {
            'status': 'pending',
            'message': 'Prediction timeframe has not completed yet'
        }
    
    # Try Exa search for additional context
    search_results = None
    if market_outcome['outcome'] in ['no_data', 'error']:
        search_results = search_market_outcome_exa(
            prediction['statement'],
            prediction['asset'],
            prediction['timeframe'],
            prediction.get('publish_date', '')[:10]
        )
    
    # Get prediction date
    prediction_date = prediction.get('publish_date', prediction.get('created_at', ''))[:10]
    if not prediction_date:
        prediction_date = datetime.now().strftime("%Y-%m-%d")
    
    # Verify with Gemini
    gemini_result = verify_with_gemini(
        statement=prediction['statement'],
        asset=prediction['asset'],
        direction=prediction['direction'],
        target=prediction.get('target'),
        timeframe=prediction['timeframe'],
        prediction_date=prediction_date,
        market_outcome=market_outcome,
        search_results=search_results
    )
    
    # Calculate overall score
    direction_score = 1.0 if gemini_result.get('direction_correct') else 0.0
    target_score = float(gemini_result.get('target_accuracy', 0.5))
    timing_score = float(gemini_result.get('timing_accuracy', 0.5))
    
    overall_score = (
        direction_score * SCORING_WEIGHTS['direction'] +
        target_score * SCORING_WEIGHTS['target'] +
        timing_score * SCORING_WEIGHTS['timing']
    )
    
    return {
        'status': 'verified',
        'direction_correct': gemini_result.get('direction_correct', False),
        'target_accuracy': target_score,
        'timing_accuracy': timing_score,
        'overall_score': round(overall_score, 3),
        'explanation': gemini_result.get('overall_explanation', ''),
        'market_outcome': market_outcome,
        'data_source': market_outcome.get('data_source', 'unknown')
    }


def verify_unverified_predictions(limit: int = 10, delay: float = 6.0) -> dict:
    """
    Process predictions that haven't been verified yet.
    
    Args:
        limit: Maximum number of predictions to verify
        delay: Delay between verifications (seconds)
        
    Returns:
        Summary of verification results
    """
    db = get_db()
    predictions = db.get_unverified_predictions(limit=limit)
    
    print(f"Verifying {len(predictions)} predictions...")
    
    results = {
        'verified': 0,
        'pending': 0,
        'errors': 0,
        'average_score': 0.0
    }
    
    scores = []
    
    for pred in predictions:
        print(f"\nVerifying: {pred['statement'][:60]}...")
        
        try:
            verification = verify_prediction(pred)
            
            if verification['status'] == 'pending':
                print("  ⏳ Pending - timeframe not complete")
                results['pending'] += 1
            elif verification['status'] == 'verified':
                # Save to database
                db.add_verification(
                    prediction_id=pred['id'],
                    actual_outcome=json.dumps(verification.get('market_outcome', {})),
                    direction_correct=verification['direction_correct'],
                    target_accuracy=verification['target_accuracy'],
                    timing_accuracy=verification['timing_accuracy'],
                    overall_score=verification['overall_score'],
                    explanation=verification['explanation'],
                    market_data_source=verification.get('data_source', 'unknown')
                )
                
                print(f"  ✓ Score: {verification['overall_score']:.1%}")
                print(f"    {verification['explanation'][:80]}...")
                
                scores.append(verification['overall_score'])
                results['verified'] += 1
            
        except Exception as e:
            print(f"  ✗ Error: {e}")
            results['errors'] += 1
        
        # Rate limiting
        time.sleep(delay)
    
    if scores:
        results['average_score'] = sum(scores) / len(scores)
    
    # Recalculate creator scores
    db.recalculate_creator_scores()
    
    return results


def verify_prediction_by_id(prediction_id: int) -> dict:
    """
    Verify a specific prediction by its ID.
    
    Args:
        prediction_id: Database ID of the prediction
        
    Returns:
        Verification result
    """
    db = get_db()
    prediction = db.get_prediction(prediction_id)
    
    if not prediction:
        return {'status': 'error', 'message': 'Prediction not found'}
    
    # Get video info for the publish date
    conn = db._get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT v.publish_date 
        FROM videos v 
        WHERE v.id = ?
    """, (prediction['video_id'],))
    video = cursor.fetchone()
    conn.close()
    
    if video:
        prediction['publish_date'] = video['publish_date']
    
    verification = verify_prediction(prediction)
    
    if verification['status'] == 'verified':
        db.add_verification(
            prediction_id=prediction_id,
            actual_outcome=json.dumps(verification.get('market_outcome', {})),
            direction_correct=verification['direction_correct'],
            target_accuracy=verification['target_accuracy'],
            timing_accuracy=verification['timing_accuracy'],
            overall_score=verification['overall_score'],
            explanation=verification['explanation'],
            market_data_source=verification.get('data_source', 'unknown')
        )
        
        # Recalculate creator scores
        db.recalculate_creator_scores()
    
    return verification
