"""
Configuration for the Finfluencer Tracker.
Contains creator definitions, API settings, and constants.
"""
import os
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

# API Configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
EXA_API_KEY = os.getenv("EXA_API_KEY", "")

# Database Configuration
DATABASE_PATH = os.getenv("DATABASE_PATH", "./data/predictions.db")

# Date Range Configuration
START_DATE = os.getenv("START_DATE", "2022-01-01")
END_DATE = os.getenv("END_DATE", "2025-12-31")

# Video filtering keywords (used to identify prediction-related videos)
PREDICTION_KEYWORDS = [
    "prediction", "outlook", "forecast", "target",
    "nifty", "sensex", "market", "bull", "bear",
    "crash", "rally", "investment", "buy", "sell",
    "portfolio", "stock pick", "analysis", "2022",
    "2023", "2024", "2025", "next year", "future"
]


@dataclass
class Creator:
    """Represents a finance YouTuber to track."""
    name: str
    channel_id: str
    channel_url: str
    slug: str
    description: Optional[str] = None
    
    def __post_init__(self):
        if not self.slug:
            self.slug = self.name.lower().replace(" ", "_")


# Target creators to analyze
CREATORS = [
    Creator(
        name="Akshat Shrivastava",
        channel_id="UCqW8jxh4tH1Z1sWPbkGWL4g",
        channel_url="https://www.youtube.com/@AkshatShrivastava",
        slug="akshat",
        description="SEBI Registered Investment Advisor, known for macro analysis and market predictions"
    ),
    Creator(
        name="Ankur Warikoo",
        channel_id="UCRzYN32xtBf3Yxsx5BvJWJw",
        channel_url="https://www.youtube.com/@waaborz",
        slug="warikoo",
        description="Entrepreneur and content creator sharing personal finance advice"
    ),
    Creator(
        name="CA Rachana Ranade",
        channel_id="UCi7Bim9fM2IihZiLRFxhEjw",
        channel_url="https://www.youtube.com/@CArachanaranade",
        slug="rachana",
        description="Chartered Accountant known for stock analysis and educational content"
    ),
    Creator(
        name="Pranjal Kamra",
        channel_id="UCyF8DclRRb6QWy5L4RoT4AA",
        channel_url="https://www.youtube.com/@PranjalKamra",
        slug="pranjal",
        description="Stock market educator with fundamental analysis approach"
    ),
    Creator(
        name="Shashank Udupa",
        channel_id="UC0HTI7Twdo0RdYdqrRG9IIg",
        channel_url="https://www.youtube.com/@1financebyshashankudupa",
        slug="shashank",
        description="1 Finance founder, practical personal finance tips"
    ),
    Creator(
        name="FinnovationZ",
        channel_id="UCCYANsIqGiAn8Gx2Vw6F9Og",
        channel_url="https://www.youtube.com/@FinnovationZ",
        slug="finnovationz",
        description="Stock market analysis and investment education"
    ),
    Creator(
        name="Asset Yogi",
        channel_id="UCKxD3IZpF4YwsVVxmzpKJkw",
        channel_url="https://www.youtube.com/@AssetYogi",
        slug="assetyogi",
        description="Personal finance and investment guidance for beginners"
    ),
    Creator(
        name="Pushkar Raj Thakur",
        channel_id="UCVt4zCLz8AhFszZUzzBpCuw",
        channel_url="https://www.youtube.com/@PushkarRajThakur",
        slug="pushkar",
        description="Business and investment strategies, known for stock picks"
    ),
]


def get_creator_by_slug(slug: str) -> Optional[Creator]:
    """Get a creator by their slug identifier."""
    for creator in CREATORS:
        if creator.slug == slug:
            return creator
    return None


def get_creator_by_channel_id(channel_id: str) -> Optional[Creator]:
    """Get a creator by their YouTube channel ID."""
    for creator in CREATORS:
        if creator.channel_id == channel_id:
            return creator
    return None


# Scoring configuration
SCORING_WEIGHTS = {
    "direction": 0.40,  # Bullish/bearish correct
    "target": 0.40,     # Price target accuracy
    "timing": 0.20      # Timeframe accuracy
}

TARGET_TOLERANCE = 0.10  # 10% tolerance for price targets
TIMING_TOLERANCE_DAYS = 90  # 3 months tolerance for timing


# Gemini API configuration
GEMINI_MODEL = "models/gemini-2.5-flash-lite"
GEMINI_RATE_LIMIT_RPM = 15  # Requests per minute (for flash-lite)
GEMINI_RATE_LIMIT_RPD = 1000  # Requests per day (for flash-lite)


# Common Indian market assets for recognition
MARKET_ASSETS = {
    "NIFTY 50": ["nifty", "nifty50", "nifty 50"],
    "SENSEX": ["sensex", "bse sensex"],
    "BANK NIFTY": ["bank nifty", "banknifty"],
    "NIFTY IT": ["nifty it", "it index"],
    "NIFTY PHARMA": ["nifty pharma", "pharma index"],
    "GOLD": ["gold", "sovereign gold", "sgb"],
    "SILVER": ["silver", "chandi"],
    "CRUDE OIL": ["crude", "crude oil", "oil prices"],
    "USD/INR": ["dollar", "usd inr", "rupee", "dollar rupee"],
}
