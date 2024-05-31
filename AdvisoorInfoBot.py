import os
import aiohttp
import logging
import signal
from dotenv import load_dotenv
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackContext
from urllib.parse import quote as safely_quote

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Retrieve the environment variables
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')

# Check if the TELEGRAM_TOKEN is set
if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN environment variable is not set")

EXCLUDED_SYMBOLS = {"ETH", "BTC", "BONK", "Bonk"}  # Add or modify as necessary

# Initialize the Telegram bot application
application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

async def fetch_token_metadata(session, pair_address):
    chain_id = "solana"
    logger.debug(f"Fetching token metadata for: {pair_address} on chain: {chain_id}")
    url = f"https://api.dexscreener.com/latest/dex/pairs/{chain_id}/{safely_quote(pair_address)}"
    
    logger.debug(f"Dexscreener URL: {url}")

    async with session.get(url) as response:
        logger.debug(f"Response status: {response.status}")
        if response.status == 200:
            data = await response.json()
            logger.debug(f"Response data: {data}")
            pairs = data.get('pairs', [])
            if pairs:
                pair = pairs[0]  # Assuming you want the first pair listed

                base_token = pair.get('baseToken', {})
                volume = pair.get('volume', {})
                price_change = pair.get('priceChange', {})
                liquidity = pair.get('liquidity', {})

                result = {
                    'token_symbol': base_token.get('symbol', 'Unknown'),
                    'token_name': base_token.get('name', 'Unknown'),
                    'price_usdt': pair.get('priceUsd', 'N/A'),
                    'volume_usdt': volume.get('h24', 0),  # 24-hour volume
                    'total_liquidity': liquidity.get('usd', 0),  # Total liquidity in USD
                    'price_change_24h': price_change.get('h24', 0),
                    'total_supply': None,  # Placeholder, replace with actual source if available
                    'num_holders': None,  # Placeholder, replace with actual source if available
                    'token_authority': None,  # Placeholder, replace with actual source if available
                    'website': None,  # Placeholder, replace with actual source if available
                    'twitter': None,  # Placeholder, replace with actual source if available
                    'tag': None,  # Placeholder, replace with actual source if available
                    'coingeckoId': None,  # Placeholder, replace with actual source if available
                    'holder': None  # Placeholder, replace with actual source if available
                }

                logger.debug(f"Fetched token metadata: {result}")
                return result
            else:
                logger.info(f"No market data available for pair: {pair_address}")
        else:
            logger.error(f"Failed to fetch metadata, status code: {response.status}")
    return None

async def create_message(session, pair_address):
    chain_id = "solana"
    logger.debug(f"Creating message for pair: {pair_address} on chain: {chain_id}")
    message_lines = [""]
    token_metadata = await fetch_token_metadata(session, pair_address)
    
    if not token_metadata:
        logger.debug("No token metadata found.")
        message_lines.append(
            f"🔫 No data available for the provided pair address 🔫\n\n"
            f"<a href='https://dexscreener.com/{chain_id}/{safely_quote(pair_address)}'>Go to Pair Address</a>\n"
        )
    else:
        token_symbol = token_metadata.get('token_symbol', 'Unknown')
        token_name = token_metadata.get('token_name', 'Unknown')
        price_usdt = token_metadata.get('price_usdt', 'N/A')
        volume_usdt = "${:,.0f}".format(token_metadata.get('volume_usdt', 0))
        total_liquidity = "${:,.0f}".format(token_metadata.get('total_liquidity', 0))
        total_supply = token_metadata.get('total_supply', 0)  # Placeholder for total token supply
        num_holders = token_metadata.get('num_holders', 'N/A')  # Placeholder for number of token holders
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

        if price_usdt != 'N/A':
            price_usdt = float(price_usdt)
            price_change_24h = token_metadata.get('price_change_24h', 0)
            price_change_ratio = price_change_24h / (price_usdt - price_change_24h) if price_usdt - price_change_24h != 0 else 0
            price_change_24h_str = "{:.2f}%".format(price_change_ratio * 100)
        else:
            price_change_24h_str = "N/A"

        market_cap = total_supply * price_usdt if price_usdt != 'N/A' else 0
        market_cap_str = "${:,.0f}".format(market_cap)

        total_volume = token_metadata.get('volume_usdt', 0)
        volume_market_cap_ratio = total_volume / (market_cap or 1)
        volume_market_cap_ratio_str = "{:.2f}x".format(volume_market_cap_ratio)

        liquidity_market_cap_ratio = (token_metadata.get('total_liquidity', 0) / (market_cap or 1)) * 100
        liquidity_market_cap_ratio_str = "{:.0f}%".format(liquidity_market_cap_ratio)

        message_lines.append(
            f"🤵🏼 <b>Advisoor Token Info Bot</b> 🤵🏼\n\n"
            f"Token Name: {token_name}\n\n"
            f"<b>Token Overview</b>\n"
            f"🔣 Symbol: {token_symbol}\n"
            f"📈 Price: ${price_usdt}\n"
            f"🌛 Market Cap: {market_cap_str}\n"
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

        message_lines.append(
            f"<b>Liquidity</b>\n"
            f"💧 DEX Liquidity: {total_liquidity}\n"
            f"🔍 DEX Liquidity / Market Cap: {liquidity_market_cap_ratio_str}\n\n"
            f"<b>Market Activity</b>\n"
            f"💹 Price Change (24h): {price_change_24h_str}\n"
            f"📊 Total Volume (24h): ${total_volume:,.0f}\n"
            f"🔍 Volume / Market Cap: {volume_market_cap_ratio_str}\n\n"
            f"<b>Key Links</b>\n"
            f"<a href='https://dexscreener.com/{chain_id}/{safely_quote(pair_address)}'>📄 Pair Address</a>"
        )

    final_message = '\n'.join(message_lines)

    logger.debug(f"Final Message: {final_message}")

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Photon 💡", url="https://photon-sol.tinyastro.io/@rubberd"),
         InlineKeyboardButton("Pepeboost 🐸", url="https://t.me/pepeboost_sol07_bot?start=ref_01inkp")]
    ])

    return final_message, keyboard

async def handle_token_info(update: Update, context: CallbackContext):
    logger.debug(f"Handling /search command with args: {context.args}")
    if len(context.args) == 1:
        pair_address = context.args[0]
        async with aiohttp.ClientSession() as session:
            message, keyboard = await create_message(session, pair_address)
            logger.debug(f"Sending message: {message}")
            await context.bot.send_message(chat_id=update.effective_chat.id, text=message, parse_mode='HTML', disable_web_page_preview=True, reply_markup=keyboard)  # Disable web page preview
    else:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Usage: /search [pairAddress]", parse_mode='HTML', disable_web_page_preview=True)

# Register command handler
application.add_handler(CommandHandler("search", handle_token_info))

# Start the bot
if __name__ == '__main__':
    logger.debug("Starting bot with long polling")
    application.run_polling(stop_signals=[signal.SIGINT, signal.SIGTERM])
