# Finance YouTuber Prediction Accuracy Tracker

A tool to scrape finance YouTuber videos, extract predictions, and verify them against actual market outcomes.

## Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys
```

## Environment Variables

```
GEMINI_API_KEY=your_gemini_api_key
EXA_API_KEY=your_exa_api_key
```

## Usage

```bash
# Fetch videos from a creator
python main.py fetch --creator "akshat"

# Extract predictions from videos
python main.py extract

# Verify predictions against market data
python main.py verify

# Calculate accuracy scores
python main.py score

# Start the web server
python main.py serve
```

## Project Structure

```
finfluencer-tracker/
├── config.py              # Configuration and creator definitions
├── youtube_fetcher.py     # Video and transcript fetching
├── prediction_extractor.py # Gemini-powered prediction extraction
├── market_data.py         # Historical market data
├── accuracy_scorer.py     # Scoring algorithm
├── database.py            # SQLite operations
├── server.py              # FastAPI backend
├── main.py                # CLI entry point
├── frontend/              # Web interface
│   ├── index.html
│   ├── creator.html
│   ├── styles.css
│   └── app.js
└── tests/                 # Unit tests
```
