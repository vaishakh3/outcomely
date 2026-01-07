"""
Database module for storing and retrieving prediction data.
Uses SQLite for simplicity and portability.
"""
import os
import sqlite3
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, asdict
import json

from config import DATABASE_PATH


@dataclass
class Video:
    """Represents a YouTube video."""
    id: Optional[int] = None
    creator_id: int = 0
    video_id: str = ""
    title: str = ""
    url: str = ""
    publish_date: str = ""
    transcript: str = ""
    processed: bool = False
    created_at: str = ""


@dataclass
class Prediction:
    """Represents an extracted prediction."""
    id: Optional[int] = None
    video_id: int = 0
    statement: str = ""
    timestamp: str = ""  # Video timestamp (e.g., "03:45")
    asset: str = ""
    direction: str = ""  # bullish, bearish, neutral
    target: Optional[str] = None
    timeframe: str = ""
    confidence_level: str = ""  # high, medium, low
    verified: bool = False
    created_at: str = ""


@dataclass
class Verification:
    """Represents the verification of a prediction."""
    id: Optional[int] = None
    prediction_id: int = 0
    actual_outcome: str = ""
    direction_correct: bool = False
    target_accuracy: float = 0.0
    timing_accuracy: float = 0.0
    overall_score: float = 0.0
    explanation: str = ""
    market_data_source: str = ""
    verified_at: str = ""


class Database:
    """SQLite database manager for prediction tracking."""
    
    def __init__(self, db_path: str = DATABASE_PATH):
        self.db_path = db_path
        self._ensure_directory()
        self._init_db()
    
    def _ensure_directory(self):
        """Ensure the database directory exists."""
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir)
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _init_db(self):
        """Initialize database schema."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Creators table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS creators (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                channel_id TEXT UNIQUE NOT NULL,
                channel_url TEXT,
                slug TEXT UNIQUE NOT NULL,
                description TEXT,
                total_predictions INTEGER DEFAULT 0,
                accuracy_score REAL DEFAULT 0.0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Videos table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                creator_id INTEGER NOT NULL,
                video_id TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                url TEXT NOT NULL,
                publish_date TEXT,
                transcript TEXT,
                processed INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (creator_id) REFERENCES creators(id)
            )
        """)
        
        # Predictions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id INTEGER NOT NULL,
                statement TEXT NOT NULL,
                timestamp TEXT,
                asset TEXT,
                direction TEXT,
                target TEXT,
                timeframe TEXT,
                confidence_level TEXT,
                verified INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (video_id) REFERENCES videos(id)
            )
        """)
        
        # Verifications table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS verifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                prediction_id INTEGER UNIQUE NOT NULL,
                actual_outcome TEXT,
                direction_correct INTEGER DEFAULT 0,
                target_accuracy REAL DEFAULT 0.0,
                timing_accuracy REAL DEFAULT 0.0,
                overall_score REAL DEFAULT 0.0,
                explanation TEXT,
                market_data_source TEXT,
                verified_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (prediction_id) REFERENCES predictions(id)
            )
        """)
        
        # Create indexes for performance
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_videos_creator ON videos(creator_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_predictions_video ON predictions(video_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_verifications_prediction ON verifications(prediction_id)")
        
        conn.commit()
        conn.close()
    
    # Creator operations
    def add_creator(self, name: str, channel_id: str, channel_url: str, 
                   slug: str, description: str = "") -> int:
        """Add a new creator to the database."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR IGNORE INTO creators (name, channel_id, channel_url, slug, description)
            VALUES (?, ?, ?, ?, ?)
        """, (name, channel_id, channel_url, slug, description))
        conn.commit()
        creator_id = cursor.lastrowid
        conn.close()
        return creator_id
    
    def get_creator_by_slug(self, slug: str) -> Optional[dict]:
        """Get a creator by their slug."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM creators WHERE slug = ?", (slug,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None
    
    def get_all_creators(self) -> list[dict]:
        """Get all creators."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM creators ORDER BY accuracy_score DESC")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    def update_creator_stats(self, creator_id: int, total_predictions: int, 
                            accuracy_score: float):
        """Update creator statistics."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE creators 
            SET total_predictions = ?, accuracy_score = ?
            WHERE id = ?
        """, (total_predictions, accuracy_score, creator_id))
        conn.commit()
        conn.close()
    
    # Video operations
    def add_video(self, creator_id: int, video_id: str, title: str, 
                  url: str, publish_date: str, transcript: str = "") -> int:
        """Add a new video to the database."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR IGNORE INTO videos 
            (creator_id, video_id, title, url, publish_date, transcript)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (creator_id, video_id, title, url, publish_date, transcript))
        conn.commit()
        vid = cursor.lastrowid
        conn.close()
        return vid
    
    def get_video_by_video_id(self, video_id: str) -> Optional[dict]:
        """Get a video by its YouTube video ID."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM videos WHERE video_id = ?", (video_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None
    
    def get_unprocessed_videos(self, limit: int = 10) -> list[dict]:
        """Get videos that haven't been processed for predictions yet."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM videos 
            WHERE processed = 0 AND transcript != ''
            ORDER BY publish_date DESC
            LIMIT ?
        """, (limit,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    def mark_video_processed(self, video_db_id: int):
        """Mark a video as processed."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE videos SET processed = 1 WHERE id = ?", (video_db_id,))
        conn.commit()
        conn.close()
    
    def get_videos_by_creator(self, creator_id: int) -> list[dict]:
        """Get all videos for a creator."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM videos 
            WHERE creator_id = ?
            ORDER BY publish_date DESC
        """, (creator_id,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    # Prediction operations
    def add_prediction(self, video_id: int, statement: str, timestamp: str,
                      asset: str, direction: str, target: str, 
                      timeframe: str, confidence_level: str) -> int:
        """Add a new prediction to the database."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO predictions 
            (video_id, statement, timestamp, asset, direction, target, timeframe, confidence_level)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (video_id, statement, timestamp, asset, direction, target, timeframe, confidence_level))
        conn.commit()
        pred_id = cursor.lastrowid
        conn.close()
        return pred_id
    
    def get_prediction(self, prediction_id: int) -> Optional[dict]:
        """Get a prediction by ID."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM predictions WHERE id = ?", (prediction_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None
    
    def get_unverified_predictions(self, limit: int = 10) -> list[dict]:
        """Get predictions that haven't been verified yet."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT p.*, v.video_id as youtube_id, v.title as video_title, v.url as video_url
            FROM predictions p
            JOIN videos v ON p.video_id = v.id
            WHERE p.verified = 0
            ORDER BY p.created_at ASC
            LIMIT ?
        """, (limit,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    def mark_prediction_verified(self, prediction_id: int):
        """Mark a prediction as verified."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE predictions SET verified = 1 WHERE id = ?", (prediction_id,))
        conn.commit()
        conn.close()
    
    def get_predictions_by_creator(self, creator_id: int) -> list[dict]:
        """Get all predictions for a creator with verification data."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT p.*, v.video_id as youtube_id, v.title as video_title, 
                   v.url as video_url, v.publish_date,
                   ver.actual_outcome, ver.overall_score, ver.explanation
            FROM predictions p
            JOIN videos v ON p.video_id = v.id
            LEFT JOIN verifications ver ON p.id = ver.prediction_id
            WHERE v.creator_id = ?
            ORDER BY v.publish_date DESC
        """, (creator_id,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    # Verification operations
    def add_verification(self, prediction_id: int, actual_outcome: str,
                        direction_correct: bool, target_accuracy: float,
                        timing_accuracy: float, overall_score: float,
                        explanation: str, market_data_source: str) -> int:
        """Add a verification for a prediction."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO verifications 
            (prediction_id, actual_outcome, direction_correct, target_accuracy,
             timing_accuracy, overall_score, explanation, market_data_source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (prediction_id, actual_outcome, int(direction_correct), target_accuracy,
              timing_accuracy, overall_score, explanation, market_data_source))
        conn.commit()
        ver_id = cursor.lastrowid
        
        # Mark prediction as verified
        self.mark_prediction_verified(prediction_id)
        
        conn.close()
        return ver_id
    
    def get_leaderboard(self) -> list[dict]:
        """Get the creator leaderboard sorted by accuracy score."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT c.id, c.name, c.slug, c.channel_url, c.description,
                   c.total_predictions, c.accuracy_score,
                   COUNT(DISTINCT v.id) as video_count
            FROM creators c
            LEFT JOIN videos v ON c.id = v.creator_id
            GROUP BY c.id
            ORDER BY c.accuracy_score DESC, c.total_predictions DESC
        """)
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    def recalculate_creator_scores(self):
        """Recalculate accuracy scores for all creators."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Get all creators
        cursor.execute("SELECT id FROM creators")
        creators = cursor.fetchall()
        
        for creator_row in creators:
            creator_id = creator_row['id']
            
            # Calculate average score from verifications
            cursor.execute("""
                SELECT COUNT(*) as total, AVG(ver.overall_score) as avg_score
                FROM predictions p
                JOIN videos v ON p.video_id = v.id
                JOIN verifications ver ON p.id = ver.prediction_id
                WHERE v.creator_id = ?
            """, (creator_id,))
            
            result = cursor.fetchone()
            total = result['total'] or 0
            avg_score = result['avg_score'] or 0.0
            
            cursor.execute("""
                UPDATE creators 
                SET total_predictions = ?, accuracy_score = ?
                WHERE id = ?
            """, (total, avg_score, creator_id))
        
        conn.commit()
        conn.close()


# Singleton instance
_db_instance = None

def get_db() -> Database:
    """Get the database singleton instance."""
    global _db_instance
    if _db_instance is None:
        _db_instance = Database()
    return _db_instance
