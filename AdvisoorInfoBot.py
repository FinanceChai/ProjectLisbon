import os
import aiohttp
import logging
import signal
from dotenv import load_dotenv
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackContext, Application
from datetime import datetime, timedelta, timezone
from urllib.parse import quote as safely_quote

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
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
                decimals = meta_data.get('decimals', 0)
                total_supply_raw = int(meta_data.get('supply', 0))
                total_supply = total_supply_raw / (10 ** decimals) if decimals else total_supply_raw

                markets = []
                for market in market_data['markets']:
                    markets.append({
                        'address': market.get('address'),
                        'ammId': market.get('ammId'),
                        'autodetect': market.get('autodetect'),
                        'base_symbol': market.get('base', {}).get('symbol', 'Unknown'),
                        'quote_symbol': market.get('quote', {}).get('symbol', 'Unknown'),
                        'name': market.get('name', 'Unknown'),
                        'price': market.get('price', 'N/A'),
                        'volume24h': market.get('volume24h', 0),
                        'liquidity': market.get('liquidity', 0),
                        'source': market.get('source', 'Unknown')
                    })

                result = {
                    'token_symbol': meta_data.get('symbol', 'Unknown'),
                    'token_name': meta_data.get('name', 'Unknown'),
                    'decimals': decimals,
                    'icon_url': meta_data.get('icon'),
                    'markets': markets,
                    'total_supply': total_supply,
                    'num_holders': meta_data.get('holders', 'N/A'),
                    'token_authority': meta_data.get('tokenAuthority'),
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

async def fetch_top_holders(session, token_address):
    logger.debug(f"Fetching top holders for: {token_address}")
    url = f"https://pro-api.solscan.io/v1.0/token/holders?tokenAddress={safely_quote(token_address)}&limit=10&offset=0&fromAmount=0"
    headers = {'accept': '*/*', 'token': SOLSCAN_API_KEY}
    logger.debug(f"Top holders URL: {url}")

    async with session.get(url, headers=headers) as response:
        if response.status == 200:
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
        token_symbol = token_metadata.get('token_symbol', 'Unknown')
        token_name = token_metadata.get('token_name', 'Unknown')
        total_supply = token_metadata.get('total_supply', 0)  # Retrieve total token supply
        num_holders = token_metadata.get('num_holders', 'N/A')  # Retrieve number of token holders
        token_authority = token_metadata.get('token_authority')
        token_authority_str = "🟢" if token_authority is None else "🔴"
        website = token_metadata.get('website')
        twitter = token_metadata.get('twitter')
        tag = token_metadata.get('tag')
        coingeckoId = token_metadata.get('coingeckoId')
        holder = token_metadata.get('holder')

        # Calculate market cap
        market_cap = total_supply * float(token_metadata['markets'][0]['price']) if token_metadata['markets'][0]['price'] != 'N/A' else 'N/A'
        if market_cap != 'N/A':
            market_cap = "${:,.2f}".format(market_cap)

        logger.debug("Token Metadata for message creation: %s", {
            'token_symbol': token_symbol,
            'token_name': token_name,
            'total_supply': total_supply,
            'num_holders': num_holders,
            'token_authority': token_authority_str,
            'market_cap': market_cap,
            'website': website,
            'twitter': twitter,
            'tag': tag,
            'coingeckoId': coingeckoId,
            'holder': holder
        })

        message_lines.append("🤵🏼 <b>Advisoor Token Info Bot</b> 🤵🏼\n")
        message_lines.append(f"Token Name: {token_name} \n")

        message_lines.append("<b>Token Overview</b>")
        message_lines.append(f"🔣 Symbol: {token_symbol}")
        message_lines.append(f"🪙 Total Supply: {total_supply:,.0f}")
        message_lines.append(f"💰 Market Cap: {market_cap}")
        message_lines.append(f"📍 Token Authority: {token_authority_str}")
        
        message_lines.append(f"<b>Markets</b>")

        for market in token_metadata['markets']:
            price_usdt = market.get('price', 0) if market.get('price') != 'N/A' else 0
            volume_usdt = "${:,.0f}".format(market.get('volume24h', 0))
            total_liquidity = "${:,.0f}".format(market.get('liquidity') or 0)
            market_name = market.get('name', 'Unknown')
            source = market.get('source', 'Unknown')

            message_lines.append(f"<b>Market: {market_name} ({source})</b>")
            message_lines.append(f"📈 Price: ${price_usdt}")
            message_lines.append(f"📊 Total Volume (24h): {volume_usdt}")
            message_lines.append(f"💧 Total Liquidity: {total_liquidity}\n\n")

        top_holders = await fetch_top_holders(session, token_address)

        if top_holders:
            message_lines.append("<b>Holder Distribution</b>")
            holder_links = []
            for holder in top_holders:
                scaled_amount = holder['amount'] / (10 ** token_metadata['decimals'])
                percentage = (scaled_amount / total_supply) * 100
                holder_links.append(f"<a href='https://solscan.io/token/{safely_quote(holder['address'])}'>{percentage:.2f}%</a>")
            message_lines.append(f"Top10 Distro: {' | '.join(holder_links)}")

            top5_sum = sum(holder['amount'] for holder in top_holders[:5]) / (10 ** token_metadata['decimals'])
            top10_sum = sum(holder['amount'] for holder in top_holders[:10]) / (10 ** token_metadata['decimals'])
            message_lines.append(f"Σ Top 5: {top5_sum / total_supply * 100:.2f}% | Σ Top 10: {top10_sum / total_supply * 100:.2f}%")

        message_lines.append("\n<b>Key Links</b>")
        message_lines.append(f"<a href='https://solscan.io/token/{safely_quote(token_address)}'>📄 Contract Address</a>")
        if coingeckoId:
            message_lines.append(f"<a href='https://www.coingecko.com/en/coins/{safely_quote(coingeckoId)}'>🦎 CoinGecko</a>")
        if tag:
            message_lines.append(f"<a href='https://solscan.io/account/{safely_quote(tag)}'>🔍 Tag</a>")
        if twitter:
            message_lines.append(f"<a href='https://twitter.com/{safely_quote(twitter)}'>🐦 Twitter</a>")
        if website:
            message_lines.append(f"<a href='{safely_quote(website)}'>🌐 Website</a>")
        message_lines.append(f"<a href='https://rugcheck.xyz/tokens/{safely_quote(token_address)}'>🥸 RugCheck</a>")
        message_lines.append(f"<a href='https://birdeye.so/token/{safely_quote(token_address)}?chain=solana'>🦅 BirdEye</a>")
        message_lines.append(f"<a href='https://dexscreener.com/solana/{safely_quote(token_address)}'>👀 DexScreener</a>")
    
    message_text = "\n".join(message_lines)
    logger.debug(f"Final Message: {message_text}")

    return message_text

async def send_token_info(update: Update, context: CallbackContext):
    args = context.args
    if not args:
        await update.message.reply_text('Please provide a token address.')
        return

    token_address = args[0]
    async with aiohttp.ClientSession() as session:
        message_text = await create_message(session, token_address)

    await update.message.reply_text(message_text, parse_mode='HTML', disable_web_page_preview=True, reply_markup=InlineKeyboardMarkup([[
        InlineKeyboardButton("Photon 💡", url="https://photon-sol.tinyastro.io/@rubberd"),
        InlineKeyboardButton("Pepeboost 🐸", url="https://t.me/pepeboost_sol07_bot?start=ref_01inkp")
    ]]))

application.add_handler(CommandHandler("search", send_token_info))

async def shutdown(application: Application):
    logger.info("Shutting down the bot...")
    await application.bot.session.close()

def signal_handler(sig, frame):
    logger.info(f"Received signal: {sig}, shutting down gracefully...")
    application.stop()

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

if __name__ == "__main__":
    logger.debug("Starting bot with long polling")
    application.run_polling()
