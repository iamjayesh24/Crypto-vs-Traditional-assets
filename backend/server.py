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
            
            url = f"https://api.coingecko.com/api/v3/coins/{symbol}/market_chart"
            params = {"vs_currency": "usd", "days": days, "interval": "daily"}
            
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                prices = data["prices"]
                
                result = []
                base_price = prices[0][1] if prices else 1
                
                for timestamp, price in prices:
                    date = datetime.fromtimestamp(timestamp / 1000).strftime('%Y-%m-%d')
                    normalized_return = ((price - base_price) / base_price) * 100
                    result.append({
                        "date": date,
                        "price": price,
                        "normalized_return": normalized_return
                    })
                
                return result
            else:
                # Fallback to sample data if API fails
                return generate_sample_crypto_data(period)
        except Exception as e:
            logging.error(f"Error fetching crypto data: {e}")
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
            spy_prices = spy['Close'].values
            tlt_prices = tlt['Close'].values
            dates = spy.index
            
            result = []
            base_spy = spy_prices[0]
            base_tlt = tlt_prices[0]
            
            for i, date in enumerate(dates):
                if i < len(spy_prices) and i < len(tlt_prices):
                    # Calculate individual returns
                    spy_return = ((spy_prices[i] - base_spy) / base_spy)
                    tlt_return = ((tlt_prices[i] - base_tlt) / base_tlt)
                    
                    # 60/40 weighted return
                    portfolio_return = (0.6 * spy_return + 0.4 * tlt_return) * 100
                    portfolio_price = base_spy * 0.6 + base_tlt * 0.4 + (portfolio_return / 100) * (base_spy * 0.6 + base_tlt * 0.4)
                    
                    result.append({
                        "date": date.strftime('%Y-%m-%d'),
                        "price": portfolio_price,
                        "normalized_return": portfolio_return
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
        crypto_task = fetch_crypto_data("bitcoin", timeframe)
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