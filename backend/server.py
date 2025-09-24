from fastapi import FastAPI, APIRouter, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Dict, Any
import uuid
from datetime import datetime, timedelta, timezone
import yfinance as yf
import requests
import asyncio
from concurrent.futures import ThreadPoolExecutor
import pandas as pd

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Thread pool for blocking I/O operations
executor = ThreadPoolExecutor(max_workers=4)

# Define Models
class PerformanceData(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    asset_type: str  # 'crypto' or 'traditional'
    asset_name: str
    date: str
    price: float
    normalized_return: float
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class PerformanceResponse(BaseModel):
    crypto_data: List[Dict[str, Any]]
    traditional_data: List[Dict[str, Any]]
    timeframe: str

# Helper functions for data fetching
async def fetch_crypto_data(symbol: str, period: str) -> List[Dict]:
    """Fetch crypto data from CoinGecko API"""
    def _fetch():
        try:
            # CoinGecko API for historical data
            if period == "1M":
                days = 30
            elif period == "6M":
                days = 180
            elif period == "1Y":
                days = 365
            else:  # ALL
                days = 1825  # 5 years
            
            # Use free CoinGecko API with proper rate limiting
            url = f"https://api.coingecko.com/api/v3/coins/{symbol}/market_chart"
            params = {"vs_currency": "usd", "days": days, "interval": "daily"}
            
            headers = {
                'User-Agent': 'Financial-Chart-App/1.0',
                'Accept': 'application/json'
            }
            
            response = requests.get(url, params=params, headers=headers, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                if 'prices' in data and data['prices']:
                    prices = data["prices"]
                    
                    result = []
                    base_price = float(prices[0][1]) if prices else 1
                    
                    for timestamp, price in prices:
                        date = datetime.fromtimestamp(timestamp / 1000).strftime('%Y-%m-%d')
                        normalized_return = ((price - base_price) / base_price) * 100
                        result.append({
                            "date": date,
                            "price": float(price),
                            "normalized_return": float(normalized_return)
                        })
                    
                    return result
                else:
                    logging.warning("No price data in CoinGecko response, using sample data")
                    return generate_sample_crypto_data(period)
            else:
                logging.warning(f"CoinGecko API returned status {response.status_code}, using sample data")
                return generate_sample_crypto_data(period)
                
        except requests.exceptions.RequestException as e:
            logging.error(f"Network error fetching crypto data: {e}")
            return generate_sample_crypto_data(period)
        except Exception as e:
            logging.error(f"Error fetching crypto data: {e}")
            return generate_sample_crypto_data(period)
    
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, _fetch)

async def fetch_top_cryptos_list() -> List[Dict]:
    """Fetch top 100 cryptocurrencies by market cap from CoinGecko"""
    def _fetch():
        try:
            url = "https://api.coingecko.com/api/v3/coins/markets"
            params = {
                "vs_currency": "usd",
                "order": "market_cap_desc",
                "per_page": 100,
                "page": 1,
                "sparkline": False
            }
            
            headers = {
                'User-Agent': 'Financial-Chart-App/1.0',
                'Accept': 'application/json'
            }
            
            response = requests.get(url, params=params, headers=headers, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                return [{
                    "id": coin["id"],
                    "symbol": coin["symbol"].upper(),
                    "name": coin["name"],
                    "market_cap_rank": coin["market_cap_rank"],
                    "current_price": coin["current_price"],
                    "market_cap": coin["market_cap"]
                } for coin in data[:100]]
            else:
                logging.warning(f"Failed to fetch top cryptos: {response.status_code}")
                return []
                
        except Exception as e:
            logging.error(f"Error fetching top cryptos: {e}")
            return []
    
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, _fetch)

async def fetch_crypto_portfolio_data(period: str) -> List[Dict]:
    """Fetch top 10 crypto portfolio data from CoinGecko API"""
    def _fetch():
        try:
            # Get top 10 cryptocurrencies for portfolio
            top_cryptos = ["bitcoin", "ethereum", "binancecoin", "solana", "xrp", 
                          "cardano", "avalanche-2", "dogecoin", "polkadot", "chainlink"]
            
            if period == "1M":
                days = 30
            elif period == "6M":
                days = 180
            elif period == "1Y":
                days = 365
            else:  # ALL
                days = 1825
            
            crypto_data = {}
            
            # Fetch data for each crypto
            for crypto_id in top_cryptos:
                try:
                    url = f"https://api.coingecko.com/api/v3/coins/{crypto_id}/market_chart"
                    params = {"vs_currency": "usd", "days": days, "interval": "daily"}
                    
                    headers = {
                        'User-Agent': 'Financial-Chart-App/1.0',
                        'Accept': 'application/json'
                    }
                    
                    response = requests.get(url, params=params, headers=headers, timeout=10)
                    
                    if response.status_code == 200:
                        data = response.json()
                        if 'prices' in data and data['prices']:
                            crypto_data[crypto_id] = data['prices']
                    
                    # Rate limiting
                    import time
                    time.sleep(0.5)  # 500ms delay between requests
                    
                except Exception as e:
                    logging.warning(f"Failed to fetch {crypto_id}: {e}")
                    continue
            
            if not crypto_data:
                logging.warning("No crypto data fetched, using sample data")
                return generate_sample_crypto_data(period)
            
            # Calculate equal-weighted crypto portfolio performance
            result = []
            all_dates = set()
            
            # Collect all unique dates
            for prices in crypto_data.values():
                for timestamp, price in prices:
                    date = datetime.fromtimestamp(timestamp / 1000).strftime('%Y-%m-%d')
                    all_dates.add(date)
            
            sorted_dates = sorted(list(all_dates))
            
            # Calculate portfolio value for each date
            base_values = {}
            for crypto_id, prices in crypto_data.items():
                if prices:
                    base_values[crypto_id] = float(prices[0][1])
            
            for date in sorted_dates:
                portfolio_return = 0
                valid_cryptos = 0
                
                for crypto_id, prices in crypto_data.items():
                    # Find price for this date
                    date_price = None
                    for timestamp, price in prices:
                        price_date = datetime.fromtimestamp(timestamp / 1000).strftime('%Y-%m-%d')
                        if price_date == date:
                            date_price = float(price)
                            break
                    
                    if date_price and crypto_id in base_values:
                        crypto_return = ((date_price - base_values[crypto_id]) / base_values[crypto_id]) * 100
                        portfolio_return += crypto_return
                        valid_cryptos += 1
                
                if valid_cryptos > 0:
                    avg_return = portfolio_return / valid_cryptos
                    avg_price = 100 * (1 + avg_return / 100)  # Normalized to 100 base
                    
                    result.append({
                        "date": date,
                        "price": float(avg_price),
                        "normalized_return": float(avg_return)
                    })
            
            return result if result else generate_sample_crypto_data(period)
            
        except Exception as e:
            logging.error(f"Error fetching crypto portfolio data: {e}")
            return generate_sample_crypto_data(period)
    
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, _fetch)

async def fetch_traditional_data(period: str) -> List[Dict]:
    """Fetch traditional portfolio data (60% SPY, 40% TLT)"""
    def _fetch():
        try:
            # Calculate date range
            end_date = datetime.now()
            if period == "1M":
                start_date = end_date - timedelta(days=30)
            elif period == "6M":
                start_date = end_date - timedelta(days=180)
            elif period == "1Y":
                start_date = end_date - timedelta(days=365)
            else:  # ALL
                start_date = end_date - timedelta(days=1825)
            
            # Fetch SPY (S&P 500) and TLT (20+ Year Treasury Bond) data
            spy = yf.download("SPY", start=start_date, end=end_date, progress=False)
            tlt = yf.download("TLT", start=start_date, end=end_date, progress=False)
            
            if spy.empty or tlt.empty:
                return generate_sample_traditional_data(period)
            
            # Calculate 60/40 portfolio returns
            spy_prices = spy['Close'].tolist()  # Convert to list
            tlt_prices = tlt['Close'].tolist()  # Convert to list
            dates = spy.index.tolist()
            
            result = []
            base_spy = float(spy_prices[0])
            base_tlt = float(tlt_prices[0])
            
            for i, date in enumerate(dates):
                if i < len(spy_prices) and i < len(tlt_prices):
                    # Calculate individual returns
                    spy_return = ((float(spy_prices[i]) - base_spy) / base_spy)
                    tlt_return = ((float(tlt_prices[i]) - base_tlt) / base_tlt)
                    
                    # 60/40 weighted return
                    portfolio_return = (0.6 * spy_return + 0.4 * tlt_return) * 100
                    portfolio_price = base_spy * 0.6 + base_tlt * 0.4 + (portfolio_return / 100) * (base_spy * 0.6 + base_tlt * 0.4)
                    
                    result.append({
                        "date": date.strftime('%Y-%m-%d'),
                        "price": float(portfolio_price),
                        "normalized_return": float(portfolio_return)
                    })
            
            return result
        except Exception as e:
            logging.error(f"Error fetching traditional data: {e}")
            return generate_sample_traditional_data(period)
    
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, _fetch)

def generate_sample_crypto_data(period: str) -> List[Dict]:
    """Generate sample crypto data as fallback"""
    if period == "1M":
        days = 30
    elif period == "6M":
        days = 180
    elif period == "1Y":
        days = 365
    else:
        days = 1825
    
    import random
    result = []
    base_price = 45000
    current_return = 0
    
    for i in range(days):
        date = (datetime.now() - timedelta(days=days-i)).strftime('%Y-%m-%d')
        # Simulate volatile crypto returns
        daily_change = random.uniform(-8, 12)  # Higher volatility for crypto
        current_return += daily_change
        price = base_price * (1 + current_return / 100)
        
        result.append({
            "date": date,
            "price": price,
            "normalized_return": current_return
        })
    
    return result

def generate_sample_traditional_data(period: str) -> List[Dict]:
    """Generate sample traditional portfolio data as fallback"""
    if period == "1M":
        days = 30
    elif period == "6M":
        days = 180
    elif period == "1Y":
        days = 365
    else:
        days = 1825
    
    import random
    result = []
    base_price = 100
    current_return = 0
    
    for i in range(days):
        date = (datetime.now() - timedelta(days=days-i)).strftime('%Y-%m-%d')
        # Simulate more stable traditional returns
        daily_change = random.uniform(-2, 3)  # Lower volatility for traditional
        current_return += daily_change
        price = base_price * (1 + current_return / 100)
        
        result.append({
            "date": date,
            "price": price,
            "normalized_return": current_return
        })
    
    return result

# API Routes
@api_router.get("/")
async def root():
    return {"message": "Financial Performance Chart API"}

@api_router.get("/performance/{timeframe}", response_model=PerformanceResponse)
async def get_performance_data(timeframe: str):
    """Get performance data for crypto vs traditional assets"""
    
    if timeframe not in ["1M", "6M", "1Y", "ALL"]:
        raise HTTPException(status_code=400, detail="Invalid timeframe. Use 1M, 6M, 1Y, or ALL")
    
    try:
        # Fetch data concurrently
        crypto_task = fetch_crypto_portfolio_data(timeframe)
        traditional_task = fetch_traditional_data(timeframe)
        
        crypto_data, traditional_data = await asyncio.gather(crypto_task, traditional_task)
        
        return PerformanceResponse(
            crypto_data=crypto_data,
            traditional_data=traditional_data,
            timeframe=timeframe
        )
    
    except Exception as e:
        logging.error(f"Error in get_performance_data: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch performance data")

@api_router.get("/assets/info")
async def get_assets_info():
    """Get information about the assets being compared"""
    return {
        "crypto": {
            "name": "Bitcoin",
            "symbol": "BTC",
            "description": "Leading cryptocurrency",
            "color": "#f7931a"
        },
        "traditional": {
            "name": "60/40 Portfolio",
            "description": "60% S&P 500 (SPY) + 40% 20+ Year Treasury Bonds (TLT)",
            "color": "#3b82f6"
        }
    }

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
    executor.shutdown(wait=True)