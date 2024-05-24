import os
import aiohttp
import logging
import signal
from dotenv import load_dotenv
from telegram import Bot, InlineKeyboardMarkup, InlineKeyboardButton, Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackContext, filters
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
WEBHOOK_URL = os.getenv('WEBHOOK_URL')  # The URL where Telegram will send updates
PORT = int(os.getenv('PORT', 8443))  # Use port 8443 for HTTPS by default

# Check if the TELEGRAM_TOKEN is set
if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN environment variable is not set")

EXCLUDED_SYMBOLS = {"ETH", "BTC", "BONK", "Bonk"}  # Add or modify as necessary

# Initialize the Telegram bot application
application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

async def fetch_token_metadata(session, token_address):
    # Your existing code for fetch_token_metadata
    pass

async def fetch_top_holders(session, token_address):
    # Your existing code for fetch_top_holders
    pass

async def create_message(session, token_address):
    # Your existing code for create_message
    pass

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

def shutdown(signum, frame):
    logger.debug("Shutting down...")
    application.stop()
    logger.debug("Bot stopped")

def main():
    logger.debug("Starting bot with webhook")

    # Add a handler to log all incoming updates (for debugging purposes)
    async def log_update(update: Update, context: CallbackContext):
        logger.debug(f"Received update: {update}")

    application.add_handler(MessageHandler(filters.ALL, log_update))
    application.add_handler(CommandHandler("search", handle_token_info))

    # Signal handling for graceful shutdown
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,  # Using updated PORT
        url_path=TELEGRAM_TOKEN,
        webhook_url=f"{WEBHOOK_URL}/{TELEGRAM_TOKEN}"
    )
    logger.debug(f"Webhook URL: {WEBHOOK_URL}/{TELEGRAM_TOKEN}")

if __name__ == "__main__":
    main()
