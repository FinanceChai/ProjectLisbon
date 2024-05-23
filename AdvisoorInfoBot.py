import os
import asyncio
import aiohttp
from dotenv import load_dotenv
from telegram import Bot, InlineKeyboardMarkup, InlineKeyboardButton
from urllib.parse import quote as safely_quote
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from telegram import Update
from datetime import datetime, timedelta, timezone

# Load environment variables from .env file
load_dotenv()

# Retrieve the environment variables
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')
SOLSCAN_API_KEY = os.getenv('SOLSCAN_API_KEY')

# Check if the TELEGRAM_TOKEN is set
if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN environment variable is not set")

EXCLUDED_SYMBOLS = {"ETH", "BTC", "BONK", "Bonk"}  # Add or modify as necessary

# Initialize the Telegram bot application
application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

async def fetch_token_metadata(session, token_address):
    now = datetime.now(timezone.utc)
    one_hour_ago = now - timedelta(hours=1)
    timestamp_now = int(now.timestamp())
    timestamp_one_hour_ago = int(one_hour_ago.timestamp())

    market_url = f"https://pro-api.solscan.io/v1.0/market/token/{safely_quote(token_address)}?limit=10&offset=0&startTime={timestamp_one_hour_ago}&endTime={timestamp_now}"
    meta_url = f"https://pro-api.solscan.io/v1.0/token/meta?tokenAddress={safely_quote(token_address)}"
    token_list_url = f"https://pro-api.solscan.io/v1.0/token/list?sortBy=market_cap&direction=desc&limit=10&offset=0"
    headers = {'accept': '*/*', 'token': SOLSCAN_API_KEY}
    
    async with session.get(market_url, headers=headers) as market_response, session.get(meta_url, headers=headers) as meta_response, session.get(token_list_url, headers=headers) as token_list_response:
        if market_response.status == 200 and meta_response.status == 200 and token_list_response.status == 200:
            market_data = await market_response.json()
            meta_data = await meta_response.json()
            token_list_data = await token_list_response.json()

            if 'markets' in market_data and market_data['markets']:
                market = market_data['markets'][0]  # Assuming you want the first market listed

                decimals = meta_data.get('decimals', 0)
                supply_data = meta_data.get('supply', '0')
                total_supply_raw = int(supply_data) if isinstance(supply_data, str) else int(supply_data.get('total', 0))
                total_supply = total_supply_raw / (10 ** decimals) if decimals else total_supply_raw

                num_holders = next((item['holder'] for item in token_list_data['data'] if item['mintAddress'] == token_address), 'N/A')

                result = {
                    'token_symbol': meta_data.get('symbol', 'Unknown'),
                    'token_name': meta_data.get('name', 'Unknown'),
                    'decimals': decimals,
                    'icon_url': meta_data.get('icon'),
                    'price_usdt': meta_data.get('price', 'N/A'),
                    'volume_usdt': sum(market.get('volume24h', 0) for market in market_data['markets'] if market.get('volume24h') is not None),  # Calculate the total volume over the last hour
                    'market_cap_fd': meta_data.get('marketCapFD', 0),
                    'total_liquidity': sum(market.get('liquidity', 0) for market in market_data['markets'] if market.get('liquidity') is not None),  # Calculate the total liquidity
                    'price_change_24h': market_data.get('priceChange24h'),
                    'total_supply': total_supply,
                    'num_holders': num_holders  # Get number of token holders
                }

                return result
            else:
                print(f"No market data available for token: {token_address}")
        else:
            print(f"Failed to fetch metadata, status code: {market_response.status}, {meta_response.status}, and {token_list_response.status}")
    return None

async def fetch_top_holders(session, token_address):
    url = f"https://pro-api.solscan.io/v1.0/token/holders?tokenAddress={safely_quote(token_address)}&limit=10&offset=0&fromAmount=0"
    headers = {'accept': '*/*', 'token': SOLSCAN_API_KEY}
    async with session.get(url, headers=headers) as response:
        if response.status == 200:
            data = await response.json()
            if 'data' in data:
                return data['data']
            else:
                print(f"No holder data available for token: {token_address}")
        else:
            print(f"Failed to fetch holders, status code: {response.status}")
    return []

async def create_message(session, token_address):
    message_lines = [""]
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
        volume_usdt = "${:,.0f}".format(token_metadata.get('volume_usdt', 0))
        market_cap_fd = "${:,.0f}".format(token_metadata.get('market_cap_fd', 0))
        total_liquidity = "${:,.0f}".format(token_metadata.get('total_liquidity', 0))
        total_supply = token_metadata.get('total_supply', 0)  # Retrieve total token supply
        num_holders = token_metadata.get('num_holders', 'N/A')  # Retrieve number of token holders

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
            f"<b><u>Token Overview</u></b>\n"
            f"🔣 Symbol: {token_symbol}\n"
            f"📈 Price: ${price_usdt}\n"
            f"🌛 Market Cap: {market_cap_fd}\n"
            f"🪙 Total Supply: {total_supply:,.0f}\n"
        )

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
            top_sums_str = f"Top 5: {top_5_sum:.2f}% | Top 10: {top_10_sum:.2f}%"

            message_lines.append(f"\n<b><u>Top 10 Holders Distribution</u></b>\n")
            message_lines.append(f"👥 Number of Holders: {num_holders}\n")
            message_lines.append(f"Top 10:\n{top_holder_percentages_str}")
            message_lines.append(f"\n{top_sums_str}\n")

        message_lines.append(
            f"\n<b><u>Liquidity</u></b>\n"
            f"💧 DEX Liquidity: {total_liquidity}\n"
            f"🔍 DEX Liquidity / Market Cap: {liquidity_market_cap_ratio_str}\n\n"
            f"<b><u>Market Activity</u></b>\n"
            f"💹 Price Change 24h: {price_change_24h_str}\n"
            f"📊 Volume / Market Cap: {volume_market_cap_ratio_str}\n"
            f"🔄 Volume (24h): {volume_usdt}\n\n"
            f"<a href='https://solscan.io/token/{safely_quote(token_address)}'>Contract Address</a>\n"
            f"--<a href='https://rugcheck.xyz/tokens/{safely_quote(token_address)}'>RugCheck</a>\n"
        )
    
    final_message = '\n'.join(message_lines)

    if len(message_lines) > 1:
        keyboard = [
            [InlineKeyboardButton("Photon 💡", url="https://photon-sol.tinyastro.io/@rubberd"),
            InlineKeyboardButton("Pepeboost 🐸", url="https://t.me/pepeboost_sol07_bot?start=ref_01inkp")]
        ]
        return final_message, InlineKeyboardMarkup(keyboard)
    else:
        return final_message, None

async def handle_token_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 1:
        await update.message.reply_text("Usage: /search [contract address]")
        return

    token_address = context.args[0]
    async with aiohttp.ClientSession() as session:
        message, reply_markup = await create_message(session, token_address)
        if message:
            await send_telegram_message(Bot(token=TELEGRAM_TOKEN), CHAT_ID, message, reply_markup)
        else:
            await update.message.reply_text("Failed to retrieve token information.")

async def send_telegram_message(bot, chat_id, text, reply_markup):
    await bot.send_message(chat_id, text=text, parse_mode='HTML', disable_web_page_preview=True, reply_markup=reply_markup)

def main():
    application.add_handler(CommandHandler("search", handle_token_info))
    application.run_polling()

if __name__ == "__main__":
    main()
