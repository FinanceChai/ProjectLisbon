import os
import asyncio
import aiohttp
from dotenv import load_dotenv
from telegram import Bot, InlineKeyboardMarkup, InlineKeyboardButton
from urllib.parse import quote as safely_quote
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from telegram import Update

load_dotenv()

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')
SOLSCAN_API_KEY = os.getenv('SOLSCAN_API_KEY')
EXCLUDED_SYMBOLS = {"ETH", "BTC", "BONK", "Bonk"}  # Add or modify as necessary

application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

async def fetch_token_metadata(session, token_address):
    url = f"https://pro-api.solscan.io/v1.0/market/token/{safely_quote(token_address)}"
    headers = {'accept': '*/*', 'token': SOLSCAN_API_KEY}
    async with session.get(url, headers=headers) as response:
        if response.status == 200:
            data = await response.json()
            if 'markets' in data and data['markets']:
                market = data['markets'][0]  # Assuming you want the first market listed

                result = {
                    'mint_address': market.get('base', {}).get('address'),
                    'token_symbol': market.get('base', {}).get('symbol'),
                    'token_name': market.get('base', {}).get('name'),
                    'decimals': market.get('base', {}).get('decimals'),
                    'icon_url': market.get('base', {}).get('icon'),
                    'website': market.get('base', {}).get('website', 'N/A'),
                    'twitter': market.get('base', {}).get('twitter', 'N/A'),
                    'market_cap_rank': market.get('market_cap_rank', 'N/A'),
                    'price_usdt': market.get('price', 'N/A'),
                    'market_cap_fd': market.get('market_cap_fd', 'N/A'),
                    'volume': market.get('volume24h', 'N/A'),
                    'tag': market.get('tag', 'N/A'),
                    'total_liquidity': market.get('liquidity', 'N/A'),
                    'initial_lp_size': market.get('initial_lp_size', 'N/A'),
                    'mint_disabled': market.get('mint', {}).get('freezeAuthority', 'N/A'),
                    'lp_burned': market.get('lp_burned', 'N/A')
                }

                return result
            else:
                print(f"No market data available for token: {token_address}")
        else:
            print(f"Failed to fetch metadata, status code: {response.status}")
    return None

async def fetch_top_holders(session, token_address):
    url = f"https://pro-api.solscan.io/v1.0/token/holders/{safely_quote(token_address)}?limit=10"
    headers = {'accept': '*/*', 'token': SOLSCAN_API_KEY}
    async with session.get(url, headers=headers) as response:
        if response.status == 200:
            data = await response.json()
            holders = data.get('data', [])
            top_holders = [{'address': holder['owner'], 'amount': holder['amount']} for holder in holders]
            return top_holders
        else:
            print(f"Failed to fetch top holders, status code: {response.status}")
    return []

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
        market_cap = token_metadata.get('market_cap_fd', 'N/A')
        total_liquidity = token_metadata.get('total_liquidity', 'N/A')
        initial_lp_size = token_metadata.get('initial_lp_size', 'N/A')
        mint_disabled = token_metadata.get('mint_disabled', 'N/A')
        lp_burned = token_metadata.get('lp_burned', 'N/A')
        website = token_metadata.get('website', 'N/A')
        twitter = token_metadata.get('twitter', 'N/A')
        
        top_holders = await fetch_top_holders(session, token_address)
        top_holders_list = ', '.join([holder['address'] for holder in top_holders])
        
        message_lines.append(
            f"Token Symbol: {token_symbol}\n"
            f"Token Name: {token_name}\n"
            f"Market Cap: {market_cap}\n"
            f"Total Liquidity: {total_liquidity}\n"
            f"Initial LP Size: {initial_lp_size}\n"
            f"Mint Disabled: {mint_disabled}\n"
            f"LP Burned: {lp_burned}\n"
            f"Top 10 Holders: {top_holders_list}\n"
            f"Website: {website}\n"
            f"Twitter: {twitter}\n"
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
