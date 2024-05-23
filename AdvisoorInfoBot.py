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

# Load environment variables
load_dotenv()

# Retrieve the environment variables
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
SOLSCAN_API_KEY = os.getenv('SOLSCAN_API_KEY')
WEBHOOK_URL = os.getenv('WEBHOOK_URL', 'https://167.99.43.125')  # The URL where Telegram will send updates
PORT = 443  # Use port 443 for HTTPS

# Check if the TELEGRAM_TOKEN is set
if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN environment variable is not set")

EXCLUDED_SYMBOLS = {"ETH", "BTC", "BONK", "Bonk"}  # Add or modify as necessary

# Initialize the Telegram bot application
application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

# Your fetch_token_metadata, fetch_top_holders, create_message, handle_token_info functions here...

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
