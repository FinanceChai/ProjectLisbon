import os
import aiohttp
import logging
from dotenv import load_dotenv
from telegram import Bot, InlineKeyboardMarkup, InlineKeyboardButton, Update
from urllib.parse import quote as safely_quote
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackContext, MessageHandler, filters
from datetime import datetime, timedelta, timezone

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

# Retrieve the environment variables
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
SOLSCAN_API_KEY = os.getenv('SOLSCAN_API_KEY')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')  # The URL where Telegram will send updates
PORT = 443  # Use port 443 for HTTPS

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
                    'market_cap_fd': market_data.get('marketCapFD'),
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
        price_usdt = token_metadata.get('price_usdt', 'N/A')
        volume_usdt = "${:,.0f}".format(token_metadata.get('volume_usdt', 0))
        market_cap_fd = "${:,.0f}".format(token_metadata.get('market_cap_fd', 0) or 0)
        total_liquidity = "${:,.0f}".format(token_metadata.get('total_liquidity', 0))
        total_supply = token_metadata.get('total_supply', 0)  # Retrieve total token supply
        num_holders = token_metadata.get('holders', 'N/A')  # Retrieve number of token holders
        token_authority = token_metadata.get('token_authority')
        token_authority_str = "🟢" if token_authority is None else "🔴"
        website = token_metadata.get('website')
        twitter = token_metadata.get('twitter')
        tag = token_metadata.get('tag')
        coingeckoId = token_metadata.get('coingeckoId')
        holder = token_metadata.get('holder')

        logger.debug("Token Metadata for message creation: %s", {
            'token_symbol': token_symbol,
            'token_name': token_name,
            'price_usdt': price_usdt,
            'volume_usdt': volume_usdt,
            'market_cap_fd': market_cap_fd,
            'total_liquidity': total_liquidity,
            'total_supply': total_supply,
            'num_holders': num_holders,
            'token_authority': token_authority_str,
            'website': website,
            'twitter': twitter,
            'tag': tag,
            'coingeckoId': coingeckoId,
            'holder': holder
        })

        if price_usdt != 'N/A' and token_metadata.get('price_change_24h') is not None:
            price_usdt = float(price_usdt)
            price_change_24h = token_metadata.get('price_change_24h')
            price_change_ratio = price_change_24h / (price_usdt - price_change_24h)
            price_change_24h_str = "{:.2f}%".format(price_change_ratio * 100)
        else:
            price_change_24h_str = "N/A"

        total_volume = token_metadata.get('volume_usdt', 0)
        market_cap = token_metadata.get('market_cap_fd', 1) or 1
        volume_market_cap_ratio = total_volume / market_cap
        volume_market_cap_ratio_str = "{:.2f}x".format(volume_market_cap_ratio)

        liquidity_market_cap_ratio = (token_metadata.get('total_liquidity', 0) / market_cap) * 100
        liquidity_market_cap_ratio_str = "{:.2f}%".format(liquidity_market_cap_ratio)

        message_lines.append(
            f"Token Name: {token_name}\n\n"
            f"<b>Token Overview</b>\n"
            f"🔣 Symbol: {token_symbol}\n"
            f"📈 Price: ${price_usdt}\n"
            f"🌛 Market Cap: {market_cap_fd}\n"
            f"🪙 Total Supply: {total_supply:,.0f}\n"
            f"📍 Token Authority: {token_authority_str}"
        )

        if website:
            message_lines.append(f"🌐 Website: <a href='{website}'>{website}</a>")
        if twitter:
            message_lines.append(f"🐦 Twitter: <a href='https://twitter.com/{twitter}'>@{twitter}</a>")
        if tag:
            message_lines.append(f"🏷️ Tag: {tag}")
        if coingeckoId:
            message_lines.append(f"🦎 CoinGecko ID: {coingeckoId}")
        if holder:
            message_lines.append(f"👤 Holder: {holder}")

        # Fetch and calculate top holders' percentage ownership
        top_holders = await fetch_top_holders(session, token_address)
        if top_holders:
            top_holder_percentages = []
            top_5_sum = 0
            top_10_sum = 0

            for i, holder in enumerate(top_holders):
                amount = holder.get('amount') / (10 ** token_metadata.get('decimals', 0))
                percentage = (amount / total_supply) * 100
                top_holder_percentages.append(f"{percentage:.2f}%")
                if i < 5:
                    top_5_sum += percentage
                top_10_sum += percentage

            top_holder_percentages_str = " | ".join(top_holder_percentages)
            top_sums_str = f"Σ Top 5: {top_5_sum:.2f}% | Σ Top 10: {top_10_sum:.2f}%"

            message_lines.append(f"\n<b>Holder Distribution</b>")
            message_lines.append(f"Top10 Distro: {top_holder_percentages_str}")
            message_lines.append(f"{top_sums_str}\n")

        message_lines.append(
            f"<b>Liquidity</b>\n"
            f"💧 DEX Liquidity: {total_liquidity}\n"
            f"🔍 DEX Liquidity / Market Cap: {liquidity_market_cap_ratio_str}\n\n"
            f"<b>Market Activity</b>\n"
            f"💹 Price Change (24h): {price_change_24h_str}\n"
            f"📊 Total Volume (24h): ${total_volume:,.0f}\n"
            f"🔍 Volume / Market Cap: {volume_market_cap_ratio_str}\n\n"
            f"<b>Key Links</b>\n"
            f"<a href='https://solscan.io/token/{safely_quote(token_address)}'>📄 Contract Address</a>\n"
            f"<a href='https://rugcheck.xyz/tokens/{safely_quote(token_address)}'>🥸 RugCheck</a>\n"
            f"<a href='https://birdeye.so/token/{safely_quote(token_address)}?chain=solana'>🦅 BirdEye</a> | "
            f"<a href='https://dexscreener.com/solana/{safely_quote(token_address)}'>🧭 DexScreener</a>"
        )
    
    final_message = '\n'.join(message_lines)

    logger.debug(f"Final Message: {final_message}")

    if len(message_lines) > 1:
        keyboard = [
            [InlineKeyboardButton("Photon 💡", url="https://photon-sol.tinyastro.io/@rubberd"),
            InlineKeyboardButton("Pepeboost 🐸", url="https://t.me/pepeboost_sol07_bot?start=ref_01inkp")]
        ]
        return final_message, InlineKeyboardMarkup(keyboard)
    else:
        return final_message, None

async def handle_token_info(update: Update, context: CallbackContext):
    logger.debug(f"Handling /search command with args: {context.args}")
    if len(context.args) != 1:
        await update.message.reply_text("Usage: /search [contract address]")
        return

    token_address = context.args[0]
    logger.debug(f"Token address received: {token_address}")
    async with aiohttp.ClientSession() as session:
        message, reply_markup = await create_message(session, token_address)
        if message:
            logger.debug(f"Sending message: {message}")
            await update.message.reply_text(text=message, parse_mode='HTML', disable_web_page_preview=True, reply_markup=reply_markup)
        else:
            logger.debug("Failed to retrieve token information.")
            await update.message.reply_text("Failed to retrieve token information.")

def main():
    logger.debug("Starting bot with webhook")

    # Add a handler to log all incoming updates (for debugging purposes)
    async def log_update(update: Update, context: CallbackContext):
        logger.debug(f"Received update: {update}")

    application.add_handler(MessageHandler(filters.ALL, log_update))
    application.add_handler(CommandHandler("search", handle_token_info))

    application.run_webhook(listen="0.0.0.0",
                            port=PORT,  # Using PORT 443
                            url_path=TELEGRAM_TOKEN,
                            webhook_url=f"{WEBHOOK_URL}/{TELEGRAM_TOKEN}")
    logger.debug(f"Webhook URL: {WEBHOOK_URL}/{TELEGRAM_TOKEN}")

if __name__ == "__main__":
    main()
