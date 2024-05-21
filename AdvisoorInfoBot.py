import os
import asyncio
import aiohttp
from dotenv import load_dotenv
from telegram import Bot, InlineKeyboardMarkup, InlineKeyboardButton
from urllib.parse import quote as safely_quote
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from telegram import Update

# Load environment variables from .env file
load_dotenv()

# Retrieve the environment variables
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')
SOLSCAN_API_KEY = os.getenv('SOLSCAN_API_KEY')

# Debugging: Print environment variables to ensure they are loaded correctly
print(f"TELEGRAM_TOKEN: {TELEGRAM_TOKEN}")
print(f"CHAT_ID: {CHAT_ID}")
print(f"SOLSCAN_API_KEY: {SOLSCAN_API_KEY}")

# Check if the TELEGRAM_TOKEN is set
if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN environment variable is not set")

EXCLUDED_SYMBOLS = {"ETH", "BTC", "BONK", "Bonk"}  # Add or modify as necessary

# Initialize the Telegram bot application
application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

async def fetch_token_metadata(session, token_address):
    url = f"https://pro-api.solscan.io/v1.0/market/token/{safely_quote(token_address)}?limit=10&offset=0"
    headers = {'accept': '*/*', 'token': SOLSCAN_API_KEY}
    async with session.get(url, headers=headers) as response:
        if response.status == 200:
            data = await response.json()
            if 'markets' in data and data['markets']:
                market = data['markets'][0]  # Assuming you want the first market listed

                result = {
                    'token_symbol': market.get('base', {}).get('symbol'),
                    'token_name': market.get('base', {}).get('name'),
                    'decimals': market.get('base', {}).get('decimals'),
                    'icon_url': market.get('base', {}).get('icon'),
                    'price_usdt': data.get('priceUsdt'),
                    'volume_usdt': data.get('volumeUsdt'),
                    'market_cap_fd': data.get('marketCapFD'),
                    'market_cap_rank': data.get('marketCapRank'),
                    'price_change_24h': data.get('priceChange24h'),
                    'markets': [
                        {
                            'name': market.get('name'),
                            'price': market.get('price'),
                            'volume_24h': market.get('volume24h')
                        } for market in data['markets']
                    ]
                }

                return result
            else:
                print(f"No market data available for token: {token_address}")
        else:
            print(f"Failed to fetch metadata, status code: {response.status}")
    return None

async def create_message(session, token_address):
    message_lines = ["📝 Token Information 🔮\n"]
    token_metadata = await fetch_token_metadata(session, token_address)
    
    if not token_metadata:
        message_lines.append(
            f"🔫 No data available for the provided token address 🔫\n\n"
            f"<a href='https://solscan.io/token/{safely_quote(token_address)}'>Go to Contract Address</a>\n"
        )
    else:
        token_symbol = token_metadata.get('token_symbol', 'Unknown')
        token_name = token_metadata.get('token_name', 'Unknown')
        price_usdt = token_metadata.get('price_usdt', 'N/A')
        volume_usdt = token_metadata.get('volume_usdt', 'N/A')
        market_cap_fd = token_metadata.get('market_cap_fd', 'N/A')
        market_cap_rank = token_metadata.get('market_cap_rank', 'N/A')
        price_change_24h = token_metadata.get('price_change_24h', 'N/A')

        markets_info = "\n".join(
            [f"Market: {market['name']} - Price: {market['price']} - Volume 24h: {market['volume_24h']}"
             for market in token_metadata['markets']]
        )

        message_lines.append(
            f"Token Symbol: {token_symbol}\n"
            f"Token Name: {token_name}\n"
            f"Price (USDT): {price_usdt}\n"
            f"Volume (USDT): {volume_usdt}\n"
            f"Market Cap (FD): {market_cap_fd}\n"
            f"Market Cap Rank: {market_cap_rank}\n"
            f"Price Change (24h): {price_change_24h}\n"
            f"\nMarkets Information:\n{markets_info}\n"
            f"<a href='https://solscan.io/token/{safely_quote(token_address)}'>Contract Address</a>\n"
        )
    
    final_message = '\n'.join(message_lines)

    if len(message_lines) > 1:
        keyboard = [
            [InlineKeyboardButton("Trojan", url="https://t.me/solana_trojanbot?start=r-0xrubberd319503"),
             InlineKeyboardButton("Photon", url="https://photon-sol.tinyastro.io/@rubberd")],
            [InlineKeyboardButton("Bonkbot", url="https://t.me/bonkbot_bot?start=ref_al2no"),
             InlineKeyboardButton("BananaGun", url="https://t.me/BANANAGUNSNIPER_BOT?START=REF_RUBBERD")]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)
        return final_message, reply_markup
    else:
        return final_message, None

async def handle_token_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 1:
        await update.message.reply_text("Usage: /search [contract address]")
        return

    token_address = context.args[0]
    async with aiohttp.ClientSession() as session:
        message, reply_markup = await create_message(session, token_address)
        await send_telegram_message(Bot(token=TELEGRAM_TOKEN), CHAT_ID, message, reply_markup)

async def send_telegram_message(bot, chat_id, text, reply_markup):
    await bot.send_message(chat_id, text=text, parse_mode='HTML', disable_web_page_preview=True, reply_markup=reply_markup)

def main():
    application.add_handler(CommandHandler("search", handle_token_info))
    application.run_polling()

if __name__ == "__main__":
    main()
