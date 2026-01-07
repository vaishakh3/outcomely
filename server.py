"""
FastAPI server for the Finfluencer Tracker frontend.
Provides REST API endpoints for the leaderboard and creator details.
"""
import os
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from database import get_db
from config import CREATORS


app = FastAPI(
    title="Finfluencer Tracker API",
    description="API for Finance YouTuber Prediction Accuracy Leaderboard",
    version="1.0.0"
)

# CORS for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files
FRONTEND_DIR = Path(__file__).parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/")
async def root():
    """Serve the main leaderboard page."""
    index_path = FRONTEND_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {"message": "Frontend not found. API available at /api/"}


@app.get("/creator/{slug}")
async def creator_page(slug: str):
    """Serve the creator detail page."""
    creator_path = FRONTEND_DIR / "creator.html"
    if creator_path.exists():
        return FileResponse(creator_path)
    return {"message": "Page not found"}


# API Endpoints
@app.get("/api/leaderboard")
async def get_leaderboard():
    """Get the accuracy leaderboard sorted by score."""
    db = get_db()
    creators = db.get_leaderboard()
    
    # Add rank
    for i, creator in enumerate(creators, 1):
        creator['rank'] = i
        # Convert None to 0 for JSON serialization
        creator['accuracy_score'] = creator['accuracy_score'] or 0
        creator['total_predictions'] = creator['total_predictions'] or 0
        creator['video_count'] = creator['video_count'] or 0
    
    return {"leaderboard": creators}


@app.get("/api/creators")
async def get_creators():
    """Get all tracked creators."""
    db = get_db()
    creators = db.get_all_creators()
    return {"creators": creators}


@app.get("/api/creator/{slug}")
async def get_creator(slug: str):
    """Get detailed information about a creator."""
    db = get_db()
    creator = db.get_creator_by_slug(slug)
    
    if not creator:
        raise HTTPException(status_code=404, detail="Creator not found")
    
    # Get predictions with verification data
    predictions = db.get_predictions_by_creator(creator['id'])
    
    # Get videos
    videos = db.get_videos_by_creator(creator['id'])
    
    return {
        "creator": creator,
        "predictions": predictions,
        "videos": videos,
        "stats": {
            "total_predictions": len(predictions),
            "verified_predictions": len([p for p in predictions if p.get('overall_score') is not None]),
            "total_videos": len(videos),
            "average_score": creator['accuracy_score'] or 0
        }
    }


@app.get("/api/creator/{slug}/predictions")
async def get_creator_predictions(
    slug: str,
    verified_only: bool = False,
    limit: int = 50,
    offset: int = 0
):
    """Get predictions for a specific creator with pagination."""
    db = get_db()
    creator = db.get_creator_by_slug(slug)
    
    if not creator:
        raise HTTPException(status_code=404, detail="Creator not found")
    
    predictions = db.get_predictions_by_creator(creator['id'])
    
    if verified_only:
        predictions = [p for p in predictions if p.get('overall_score') is not None]
    
    total = len(predictions)
    predictions = predictions[offset:offset + limit]
    
    return {
        "predictions": predictions,
        "total": total,
        "limit": limit,
        "offset": offset
    }


@app.get("/api/prediction/{prediction_id}")
async def get_prediction(prediction_id: int):
    """Get detailed information about a specific prediction."""
    db = get_db()
    
    conn = db._get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            p.*,
            v.video_id as youtube_id,
            v.title as video_title,
            v.url as video_url,
            v.publish_date,
            c.name as creator_name,
            c.slug as creator_slug,
            ver.actual_outcome,
            ver.direction_correct,
            ver.target_accuracy,
            ver.timing_accuracy,
            ver.overall_score,
            ver.explanation,
            ver.market_data_source,
            ver.verified_at
        FROM predictions p
        JOIN videos v ON p.video_id = v.id
        JOIN creators c ON v.creator_id = c.id
        LEFT JOIN verifications ver ON p.id = ver.prediction_id
        WHERE p.id = ?
    """, (prediction_id,))
    
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        raise HTTPException(status_code=404, detail="Prediction not found")
    
    prediction = dict(row)
    
    # Generate video link with timestamp
    if prediction.get('youtube_id') and prediction.get('timestamp'):
        try:
            parts = prediction['timestamp'].split(':')
            if len(parts) == 2:
                seconds = int(parts[0]) * 60 + int(parts[1])
                prediction['video_link_with_timestamp'] = (
                    f"https://www.youtube.com/watch?v={prediction['youtube_id']}&t={seconds}s"
                )
        except:
            prediction['video_link_with_timestamp'] = prediction.get('video_url')
    
    return {"prediction": prediction}


@app.get("/api/stats")
async def get_stats():
    """Get overall statistics."""
    db = get_db()
    
    conn = db._get_connection()
    cursor = conn.cursor()
    
    # Total creators
    cursor.execute("SELECT COUNT(*) as count FROM creators")
    total_creators = cursor.fetchone()['count']
    
    # Total videos
    cursor.execute("SELECT COUNT(*) as count FROM videos")
    total_videos = cursor.fetchone()['count']
    
    # Total predictions
    cursor.execute("SELECT COUNT(*) as count FROM predictions")
    total_predictions = cursor.fetchone()['count']
    
    # Verified predictions
    cursor.execute("SELECT COUNT(*) as count FROM verifications")
    verified_predictions = cursor.fetchone()['count']
    
    # Average accuracy
    cursor.execute("SELECT AVG(overall_score) as avg FROM verifications")
    avg_row = cursor.fetchone()
    average_accuracy = avg_row['avg'] if avg_row['avg'] else 0
    
    # Predictions by direction
    cursor.execute("""
        SELECT direction, COUNT(*) as count 
        FROM predictions 
        GROUP BY direction
    """)
    by_direction = {row['direction']: row['count'] for row in cursor.fetchall()}
    
    conn.close()
    
    return {
        "total_creators": total_creators,
        "total_videos": total_videos,
        "total_predictions": total_predictions,
        "verified_predictions": verified_predictions,
        "pending_predictions": total_predictions - verified_predictions,
        "average_accuracy": round(average_accuracy, 3),
        "predictions_by_direction": by_direction
    }


@app.get("/api/search")
async def search_predictions(q: str, limit: int = 20):
    """Search predictions by statement text."""
    db = get_db()
    
    conn = db._get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            p.*,
            v.title as video_title,
            c.name as creator_name,
            c.slug as creator_slug,
            ver.overall_score
        FROM predictions p
        JOIN videos v ON p.video_id = v.id
        JOIN creators c ON v.creator_id = c.id
        LEFT JOIN verifications ver ON p.id = ver.prediction_id
        WHERE p.statement LIKE ?
        ORDER BY ver.overall_score DESC NULLS LAST
        LIMIT ?
    """, (f"%{q}%", limit))
    
    rows = cursor.fetchall()
    conn.close()
    
    return {"results": [dict(row) for row in rows], "query": q}


@app.get("/api/export/{slug}")
async def export_creator_predictions(slug: str):
    """Export a creator's predictions as CSV-ready JSON."""
    db = get_db()
    creator = db.get_creator_by_slug(slug)
    
    if not creator:
        raise HTTPException(status_code=404, detail="Creator not found")
    
    predictions = db.get_predictions_by_creator(creator['id'])
    
    # Format for CSV export
    export_data = []
    for p in predictions:
        export_data.append({
            "statement": p.get('statement', ''),
            "asset": p.get('asset', ''),
            "direction": p.get('direction', ''),
            "target": p.get('target', ''),
            "timeframe": p.get('timeframe', ''),
            "confidence": p.get('confidence', ''),
            "timestamp": p.get('timestamp', ''),
            "verified": p.get('overall_score') is not None,
            "accuracy_score": p.get('overall_score', ''),
            "explanation": p.get('explanation', '')
        })
    
    return {
        "creator": creator['name'],
        "slug": slug,
        "total": len(export_data),
        "predictions": export_data
    }


@app.get("/about")
async def about_page():
    """Serve the about/methodology page."""
    about_path = FRONTEND_DIR / "about.html"
    if about_path.exists():
        return FileResponse(about_path)
    raise HTTPException(status_code=404, detail="Page not found")


# 404 handler - must be last
@app.exception_handler(404)
async def custom_404_handler(request, exc):
    """Serve custom 404 page."""
    # For API routes, return JSON
    if request.url.path.startswith("/api/"):
        return JSONResponse(
            status_code=404,
            content={"detail": "Not found"}
        )
    
    # For frontend routes, serve 404 page
    error_path = FRONTEND_DIR / "404.html"
    if error_path.exists():
        return FileResponse(error_path, status_code=404)
    
    return JSONResponse(
        status_code=404,
        content={"detail": "Not found"}
    )

