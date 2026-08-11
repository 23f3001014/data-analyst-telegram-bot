import os
import json
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
        "Send me a CSV or Excel file with a caption (like 'higest vote share') to analyze it!"
    )

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming document files and process data based on the caption."""
    document = update.message.document
    file_name = document.file_name.lower()
    
    # Grab the user's question from the caption
    caption = update.message.caption.lower() if update.message.caption else ""
    
    if not (file_name.endswith('.csv') or file_name.endswith('.xlsx') or file_name.endswith('.xls')):
        await update.message.reply_text("Please upload a valid CSV or Excel file.")
        return

    await update.message.reply_text("Downloading and analyzing your file...")
    
    file = await context.bot.get_file(document.file_id)
    file_path = f"temp_{document.file_name}"
    await file.download_to_drive(file_path)

    try:
        # Load the data
        if file_name.endswith('.csv'):
            df = pd.read_csv(file_path)
        else:
            df = pd.read_excel(file_path)
            
        # --- Assignment Logic for JSON Output ---
        if "higest vote share" in caption or "highest" in caption:
            # Find the row with the maximum number of votes
            max_idx = df['Votes'].idxmax()
            candidate_name = str(df.loc[max_idx, 'Candidate'])
            highest_votes = int(df.loc[max_idx, 'Votes'])
            
            # Construct the required JSON dictionary
            response_data = {
                "answer": {
                    "party_or_candidate": candidate_name,
                    "votes": highest_votes
                },
                "log_url": "https://raw.githubusercontent.com/23f3001014/data-analyst-telegram-bot/main/run.jsonl"
            }
            
            # Format nicely as a JSON string
            final_output = json.dumps(response_data, indent=2)
            
            # Send the JSON back to the user inside a code block
            await update.message.reply_text(f"```json\n{final_output}\n```", parse_mode="Markdown")
            
        else:
            # Fallback if they do not provide a recognized caption
            await update.message.reply_text(
                "Please provide a specific query in the file caption (e.g., 'higest vote share')."
            )
            
    except Exception as e:
        await update.message.reply_text(f"Error processing file: {str(e)}")
    finally:
        # Clean up the downloaded file so Render doesn't run out of storage
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