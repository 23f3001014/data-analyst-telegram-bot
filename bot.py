import os
import logging
from threading import Thread
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import pandas as pd

# --- Flask Keep-Alive Server for Render Free Tier ---
app = Flask('')

@app.route('/')
def home():
    return "Telegram Data Analyst Bot is live!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_web)
    t.start()

# --- Logging Setup ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Telegram Bot Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a welcome message when the command /start is issued."""
    user = update.effective_user
    await update.message.reply_html(
        f"Hello {user.mention_html()}! I am your Data Analyst Bot.\n\n"
        "Send me a CSV or Excel file, or ask me questions about your data!"
    )

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming document files (CSV/Excel) and provide basic analytics."""
    document = update.message.document
    file_name = document.file_name.lower()
    
    if not (file_name.endswith('.csv') or file_name.endswith('.xlsx') or file_name.endswith('.xls')):
        await update.message.reply_text("Please upload a valid CSV or Excel file.")
        return

    await update.message.reply_text("Downloading and analyzing your file...")
    
    file = await context.bot.get_file(document.file_id)
    file_path = f"temp_{document.file_name}"
    await file.download_to_drive(file_path)

    try:
        if file_name.endswith('.csv'):
            df = pd.read_csv(file_path)
        else:
            df = pd.read_excel(file_path)
            
        summary = f"📊 **Dataset Summary:**\n\n" \
                  f"• **Rows:** {df.shape[0]}\n" \
                  f"• **Columns:** {df.shape[1]}\n\n" \
                  f"• **Columns List:** {', '.join(df.columns.astype(str))}"
        
        await update.message.reply_text(summary, parse_mode="Markdown")
        
    except Exception as e:
        await update.message.reply_text(f"Error processing file: {str(e)}")
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

def main() -> None:
    """Start the bot."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("No TELEGRAM_BOT_TOKEN environment variable found!")

    # Start the keep-alive web server for Render port binding
    keep_alive()

    # Create the Application
    application = Application.builder().token(token).build()

    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))

    # Run the bot using polling
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()