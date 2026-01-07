"""
Market data fetching module.
Provides historical market data for verification of predictions.
Uses multiple sources: nselib for Indian markets, Exa AI for web search.
"""
import os
import re
from datetime import datetime, timedelta
from typing import Optional
import json

from config import EXA_API_KEY, MARKET_ASSETS


def get_nifty_data(start_date: str, end_date: str) -> Optional[dict]:
    """
    Fetch NIFTY 50 historical data.
    
    Args:
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        
    Returns:
        Dictionary with date-indexed price data
    """
    try:
        from nselib import capital_market
        
        # Convert date format
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        
        # nselib expects DD-MM-YYYY
        start_str = start.strftime("%d-%m-%Y")
        end_str = end.strftime("%d-%m-%Y")
        
        df = capital_market.index_data("NIFTY 50", start_str, end_str)
        
        if df is not None and not df.empty:
            # Convert to dict with date keys
            data = {}
            for _, row in df.iterrows():
                date_str = row.get('Date', row.get('HistoricalDate', ''))
                if date_str:
                    data[str(date_str)] = {
                        'open': float(row.get('Open', 0)),
                        'high': float(row.get('High', 0)),
                        'low': float(row.get('Low', 0)),
                        'close': float(row.get('Close', row.get('CLOSE', 0))),
                    }
            return data
        
        return None
        
    except ImportError:
        print("nselib not installed. Install with: pip install nselib")
        return None
    except Exception as e:
        print(f"Error fetching NIFTY data: {e}")
        return None


def get_stock_data(symbol: str, start_date: str, end_date: str) -> Optional[dict]:
    """
    Fetch historical data for an NSE stock.
    
    Args:
        symbol: Stock symbol (e.g., "RELIANCE")
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        
    Returns:
        Dictionary with date-indexed price data
    """
    try:
        from nselib import capital_market
        
        # Convert date format
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        
        start_str = start.strftime("%d-%m-%Y")
        end_str = end.strftime("%d-%m-%Y")
        
        df = capital_market.price_volume_and_deliverable_position_data(
            symbol.upper(), 
            start_str, 
            end_str
        )
        
        if df is not None and not df.empty:
            data = {}
            for _, row in df.iterrows():
                date_str = str(row.get('Date', ''))
                if date_str:
                    data[date_str] = {
                        'open': float(row.get('OpenPrice', 0)),
                        'high': float(row.get('HighPrice', 0)),
                        'low': float(row.get('LowPrice', 0)),
                        'close': float(row.get('ClosePrice', 0)),
                        'volume': int(row.get('TotalTradedQuantity', 0)),
                    }
            return data
        
        return None
        
    except ImportError:
        print("nselib not installed")
        return None
    except Exception as e:
        print(f"Error fetching stock data for {symbol}: {e}")
        return None


def search_market_outcome_exa(
    prediction_statement: str,
    asset: str,
    timeframe: str,
    prediction_date: str
) -> Optional[dict]:
    """
    Use Exa AI to search for what actually happened after a prediction.
    
    Args:
        prediction_statement: The prediction text
        asset: Asset being predicted
        timeframe: When the prediction was for
        prediction_date: When the prediction was made
        
    Returns:
        Dictionary with search results and summary
    """
    if not EXA_API_KEY:
        print("Warning: Exa API key not configured")
        return None
    
    try:
        from exa_py import Exa
        
        exa = Exa(api_key=EXA_API_KEY)
        
        # Construct search query
        query = f"{asset} market performance {timeframe} India stock market actual"
        
        # Search for relevant articles
        results = exa.search_and_contents(
            query,
            type="neural",
            num_results=5,
            text=True,
            highlights=True
        )
        
        if results and results.results:
            summaries = []
            sources = []
            
            for result in results.results:
                if result.text:
                    summaries.append(result.text[:500])
                if result.url:
                    sources.append(result.url)
            
            return {
                'query': query,
                'summaries': summaries,
                'sources': sources,
                'result_count': len(results.results)
            }
        
        return None
        
    except ImportError:
        print("exa_py not installed. Install with: pip install exa-py")
        return None
    except Exception as e:
        print(f"Error searching with Exa: {e}")
        return None


def get_price_at_date(asset: str, date: str) -> Optional[float]:
    """
    Get the closing price of an asset at a specific date.
    
    Args:
        asset: Asset name (e.g., "NIFTY 50", "RELIANCE")
        date: Date in YYYY-MM-DD format
        
    Returns:
        Closing price or None if not found
    """
    # Try to get data for a small range around the date
    target_date = datetime.strptime(date, "%Y-%m-%d")
    start = (target_date - timedelta(days=7)).strftime("%Y-%m-%d")
    end = (target_date + timedelta(days=7)).strftime("%Y-%m-%d")
    
    if asset in ["NIFTY 50", "NIFTY", "NIFTY50"]:
        data = get_nifty_data(start, end)
    elif asset in ["SENSEX", "BSE SENSEX"]:
        # For Sensex, we'd need BSE data - fall back to Exa search
        return None
    else:
        # Try as stock symbol
        data = get_stock_data(asset, start, end)
    
    if data:
        # Find closest date
        for d in sorted(data.keys()):
            try:
                data_date = datetime.strptime(d, "%Y-%m-%d")
                if data_date >= target_date:
                    return data[d].get('close')
            except:
                continue
    
    return None


def get_price_range(asset: str, start_date: str, end_date: str) -> Optional[dict]:
    """
    Get price statistics for an asset over a date range.
    
    Args:
        asset: Asset name
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        
    Returns:
        Dictionary with high, low, start_price, end_price
    """
    if asset in ["NIFTY 50", "NIFTY", "NIFTY50"]:
        data = get_nifty_data(start_date, end_date)
    else:
        data = get_stock_data(asset, start_date, end_date)
    
    if not data:
        return None
    
    dates = sorted(data.keys())
    if not dates:
        return None
    
    prices = [data[d]['close'] for d in dates if data[d].get('close')]
    
    return {
        'start_price': data[dates[0]].get('close'),
        'end_price': data[dates[-1]].get('close'),
        'high': max(prices) if prices else None,
        'low': min(prices) if prices else None,
        'start_date': dates[0],
        'end_date': dates[-1]
    }


def parse_timeframe(timeframe: str, reference_date: str) -> tuple[str, str]:
    """
    Parse a timeframe string into start and end dates.
    
    Args:
        timeframe: Timeframe string (e.g., "Dec 2023", "6 months", "end of year")
        reference_date: Reference date for relative timeframes (YYYY-MM-DD)
        
    Returns:
        Tuple of (start_date, end_date) in YYYY-MM-DD format
    """
    ref = datetime.strptime(reference_date, "%Y-%m-%d")
    timeframe_lower = timeframe.lower().strip()
    
    # Handle specific month-year patterns
    month_year_pattern = r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\s*(\d{4})'
    match = re.search(month_year_pattern, timeframe_lower)
    if match:
        month_abbr = match.group(1)[:3]
        year = int(match.group(2))
        month_map = {
            'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
            'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
        }
        month = month_map.get(month_abbr, 1)
        
        start = datetime(year, month, 1)
        if month == 12:
            end = datetime(year + 1, 1, 1) - timedelta(days=1)
        else:
            end = datetime(year, month + 1, 1) - timedelta(days=1)
        
        return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")
    
    # Handle year patterns (2023, 2024, etc.)
    year_pattern = r'\b(20[2-3]\d)\b'
    year_match = re.search(year_pattern, timeframe_lower)
    if year_match and 'end' in timeframe_lower:
        year = int(year_match.group(1))
        start = datetime(year, 10, 1)  # Q4
        end = datetime(year, 12, 31)
        return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")
    elif year_match:
        year = int(year_match.group(1))
        start = datetime(year, 1, 1)
        end = datetime(year, 12, 31)
        return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")
    
    # Handle relative patterns
    if 'month' in timeframe_lower:
        months_match = re.search(r'(\d+)\s*month', timeframe_lower)
        months = int(months_match.group(1)) if months_match else 6
        start = ref
        end = ref + timedelta(days=months * 30)
        return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")
    
    if 'year' in timeframe_lower:
        years_match = re.search(r'(\d+)\s*year', timeframe_lower)
        years = int(years_match.group(1)) if years_match else 1
        start = ref
        end = ref + timedelta(days=years * 365)
        return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")
    
    # Default: assume 6 months from reference
    start = ref
    end = ref + timedelta(days=180)
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


def get_market_outcome(
    asset: str,
    direction: str,
    target: Optional[str],
    timeframe: str,
    prediction_date: str
) -> dict:
    """
    Get the actual market outcome for a prediction.
    
    Args:
        asset: Asset name
        direction: Predicted direction (bullish/bearish)
        target: Target price if any
        timeframe: Timeframe of the prediction
        prediction_date: When the prediction was made
        
    Returns:
        Dictionary with outcome data
    """
    result = {
        'asset': asset,
        'prediction_direction': direction,
        'prediction_target': target,
        'timeframe': timeframe,
        'data_source': 'unknown',
        'outcome': None,
        'actual_direction': None,
        'actual_price_change': None,
        'target_reached': None
    }
    
    try:
        start_date, end_date = parse_timeframe(timeframe, prediction_date)
        
        # Check if the end date has passed (we can verify)
        if datetime.strptime(end_date, "%Y-%m-%d") > datetime.now():
            result['outcome'] = 'pending'
            result['note'] = 'Prediction timeframe has not completed yet'
            return result
        
        # Try to get price data
        price_data = get_price_range(asset, start_date, end_date)
        
        if price_data and price_data.get('start_price') and price_data.get('end_price'):
            result['data_source'] = 'nselib'
            result['start_price'] = price_data['start_price']
            result['end_price'] = price_data['end_price']
            result['period_high'] = price_data['high']
            result['period_low'] = price_data['low']
            
            # Calculate change
            change_pct = ((price_data['end_price'] - price_data['start_price']) 
                         / price_data['start_price']) * 100
            result['actual_price_change'] = round(change_pct, 2)
            
            # Determine actual direction
            if change_pct > 5:
                result['actual_direction'] = 'bullish'
            elif change_pct < -5:
                result['actual_direction'] = 'bearish'
            else:
                result['actual_direction'] = 'neutral'
            
            # Check if target was reached
            if target:
                try:
                    target_price = float(re.sub(r'[^\d.]', '', str(target)))
                    if direction == 'bullish':
                        result['target_reached'] = price_data['high'] >= target_price
                    else:
                        result['target_reached'] = price_data['low'] <= target_price
                except:
                    result['target_reached'] = None
            
            result['outcome'] = 'verified'
        else:
            result['outcome'] = 'no_data'
            result['note'] = 'Could not fetch market data for this asset'
        
    except Exception as e:
        result['outcome'] = 'error'
        result['error'] = str(e)
    
    return result
