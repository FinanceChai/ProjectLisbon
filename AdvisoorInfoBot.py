import os
import aiohttp
import logging
import signal
from dotenv import load_dotenv
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackContext
from datetime import datetime, timedelta, timezone
from urllib.parse import quote as safely_quote

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levellevel)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Retrieve the environment variables
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
SOLSCAN_API_KEY = os.getenv('SOLSCAN_API_KEY')

# Check if the TELEGRAM_TOKEN is set
if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN environment variable is not set")

EXCLUDED_SYMBOLS = {"ETH", "BTC", "BONK", "Bonk"}  # Add or modify as necessary

# Initialize the Telegram bot application
application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

async def fetch_token_metadata(session, token_address):
    logger.debug(f"Fetching token metadata for: {token_address}")
    now = datetime.now(timezone.utc)
    one_hour_ago = now - timedelta(hours=1)
    timestamp_now = int(now.timestamp())
    timestamp_one_hour_ago = int(one_hour_ago.timestamp())

    market_url = f"https://pro-api.solscan.io/v1.0/market/token/{safely_quote(token_address)}?limit=10&offset=0&startTime={timestamp_one_hour_ago}&endTime={timestamp_now}"
    meta_url = f"https://pro-api.solscan.io/v1.0/token/meta?tokenAddress={safely_quote(token_address)}"
    headers = {'accept': '*/*', 'token': SOLSCAN_API_KEY}
    
    logger.debug(f"Market URL: {market_url}")
    logger.debug(f"Meta URL: {meta_url}")

    async with session.get(market_url, headers=headers) as market_response, session.get(meta_url, headers=headers) as meta_response:
        if market_response.status == 200 and meta_response.status == 200:
            market_data = await market_response.json()
            meta_data = await meta_response.json()

            if 'markets' in market_data and market_data['markets']:
                market = market_data['markets'][0]  # Assuming you want the first market listed

                decimals = meta_data.get('decimals', 0)
                total_supply_raw = int(meta_data.get('supply', 0))
                total_supply = total_supply_raw / (10 ** decimals) if decimals else total_supply_raw

                result = {
                    'token_symbol': meta_data.get('symbol', 'Unknown'),
                    'token_name': meta_data.get('name', 'Unknown'),
                    'decimals': decimals,
                    'icon_url': meta_data.get('icon'),
                    'price_usdt': meta_data.get('price', 'N/A'),
                    'volume_usdt': sum(market.get('volume24h', 0) for market in market_data['markets'] if market.get('volume24h') is not None),  # Calculate the total volume over the last hour
                    'total_liquidity': sum(market.get('liquidity', 0) for market in market_data['markets'] if market.get('liquidity') is not None),  # Calculate the total liquidity
                    'price_change_24h': market_data.get('priceChange24h'),
                    'total_supply': total_supply,
                    'num_holders': market_data.get('numHolders', 'N/A'),  # Placeholder, replace with actual source if available
                    'token_authority': meta_data.get('tokenAuthority'),  # Get token authority
                    'website': meta_data.get('website'),
                    'twitter': meta_data.get('twitter'),
                    'tag': meta_data.get('tag'),
                    'coingeckoId': meta_data.get('coingeckoId'),
                    'holder': meta_data.get('holder')
                }

                logger.debug(f"Fetched token metadata: {result}")
                return result
            else:
                logger.info(f"No market data available for token: {token_address}")
        else:
            logger.error(f"Failed to fetch metadata, status code: {market_response.status} and {meta_response.status}")
    return None

async def fetch_latest_transaction(session, account):
    url = f"https://pro-api.solscan.io/v1.0/account/transactions?account={account}&limit=1"
    headers = {
        'api-key': SOLSCAN_API_KEY
    }

    async with session.get(url, headers=headers) as response:
        if response.status == 200:
            data = await response.json()
            if data and 'items' in data and data['items']:
                return data['items'][0]['txHash']
        else:
            logger.error(f"Failed to fetch latest transactions, status code: {response.status}")
    return None

async def fetch_transaction_details(session, tx_hash):
    url = f"https://pro-api.solscan.io/v1.0/transaction/{tx_hash}"
    headers = {
        'api-key': SOLSCAN_API_KEY
    }

    async with session.get(url, headers=headers) as response:
        if response.status == 200:
            return await response.json()
        else:
            logger.error(f"Failed to fetch transaction details, status code: {response.status}")
    return None

async def log_transaction_details(tx_details):
    logger.debug(f"Transaction Details: {tx_details}")

async def fetch_top_holders(session, token_address):
    logger.debug(f"Fetching top holders for: {token_address}")
    url = f"https://pro-api.solscan.io/v1.0/token/holders?tokenAddress={safely_quote(token_address)}&limit=10&offset=0&fromAmount=0"
    headers = {'accept': '*/*', 'token': SOLSCAN_API_KEY}
    logger.debug(f"Top holders URL: {url}")

    async with session.get(url, headers=headers) as response:
        if response.status == 200):
            data = await response.json()
            if 'data' in data:
                logger.debug(f"Top holders data: {data['data']}")
                return data['data']
            else:
                logger.info(f"No holder data available for token: {token_address}")
        else:
            logger.error(f"Failed to fetch holders, status code: {response.status}")
    return []

async def create_message(session, token_address):
    logger.debug(f"Creating message for token: {token_address}")
    message_lines = [""]
    token_metadata = await fetch_token_metadata(session, token_address)
    
    if not token_metadata:
        logger.debug("No token metadata found.")
        message_lines.append(
            f"🔫 No data available for the provided token address 🔫\n\n"
            f"<a href='https://solscan.io/token/{safely_quote(token_address)}'>Go to Contract Address</a>\n"
        )
    else:
        # Fetch latest transaction and log its details
        latest_tx_hash = await fetch_latest_transaction(session, token_address)
        if latest_tx_hash:
            tx_details = await fetch_transaction_details(session, latest_tx_hash)
            await log_transaction_details(tx_details)

        token_symbol = token_metadata.get('token_symbol', 'Unknown')
        token_name = token_metadata.get('token_name', 'Unknown')
        price_usdt = token_metadata.get('price_usdt', 'N/A')
        volume_usdt = "${:,.0f}".format(token_metadata.get('volume_usdt', 0))
        total_liquidity = "${:,.0f}".format(token_metadata.get('total_liquidity', 0))
        total_supply = token_metadata.get('total_supply', 0)  # Retrieve total token supply
        num_holders = token_metadata.get('num_holders', 'N/A')  # Retrieve number of token holders
        token_authority = token_metadata.get('token_authority')
        token_authority_str = "🟢" if token_authority is None else "🔴"
        website = token_metadata.get('website')
        twitter = token_metadata
