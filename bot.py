import os
import pandas as pd
from flask import Flask, request
from dotenv import load_dotenv
from google import genai
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Load environment variables 
load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
PORT = int(os.environ.get("PORT", 8080))
WEBHOOK_URL = f"https://data-analyst-telegram-bot-fz91.onrender.com/{TOKEN}"

# Initialize Flask app and Telegram application globally
app = Flask(__name__)
telegram_app = Application.builder().token(TOKEN).build()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Send me a CSV or Excel file, and ask your question in the caption!")

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    document = update.message.document
    caption = update.message.caption

    if not caption:
        await update.message.reply_text("Please provide a specific query in the file caption (e.g., 'Who won the election?').")
        return

    await update.message.reply_text("Downloading and analyzing your file with Gemini...")

    try:
        # Download the file to local server storage
        file = await context.bot.get_file(document.file_id)
        file_path = f"{document.file_name}"
        await file.download_to_drive(file_path)

        # Read the dataset using Pandas
        if file_path.endswith('.csv'):
            df = pd.read_csv(file_path)
        elif file_path.endswith(('.xls', '.xlsx')):
            df = pd.read_excel(file_path)
        else:
            await update.message.reply_text("Unsupported file format. Please send a CSV or Excel file.")
            os.remove(file_path)
            return

        # Optimization: Keep only the first 500 rows to prevent token quota exhaustion
        if len(df) > 500:
            df = df.head(500)

        data_string = df.to_string() 
        
        # Build the prompt combining instructions, data, and the user's question
        prompt = f"""
        Here is a sample dataset (truncated to fit token limits):
        {data_string}
        
        Based on this dataset, answer the following query: "{caption}"
        
        Respond ONLY with raw JSON format containing the answer details. Do not use markdown block fences like ```json.
        """

        # Initialize the new Gemini client and query gemini-3.6-flash
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        response = client.models.generate_content(
            model="gemini-3.6-flash",
            contents=prompt,
        )
        
        # Clean the response text
        ai_output = response.text.strip()
        
        # Manually append the log_url wrapper to guarantee it's always included
        final_json = f"""{{
  "answer": {ai_output},
  "log_url": "[https://raw.githubusercontent.com/23f3001014/data-analyst-telegram-bot/main/run.jsonl](https://raw.githubusercontent.com/23f3001014/data-analyst-telegram-bot/main/run.jsonl)"
}}"""

        # Ensure final message doesn't exceed Telegram's 4000 character limit
        if len(final_json) > 4000:
            final_json = final_json[:3997] + "..."
            
        await update.message.reply_text(final_json)

        # Delete the file from the server to save space
        os.remove(file_path)

    except Exception as e:
        await update.message.reply_text(f"An error occurred: {str(e)}")

# Register handlers to the telegram application
telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(MessageHandler(filters.Document.ALL, handle_document))

@app.route('/')
def home():
    return "Bot is running via Webhooks!"

@app.route(f'/{TOKEN}', methods=['POST'])
def webhook():
    """Endpoint that receives updates from Telegram"""
    json_data = request.get_json(force=True)
    update = Update.de_json(json_data, telegram_app.bot)
    
    async def process():
        async with telegram_app:
            await telegram_app.process_update(update)
            
    import asyncio
    asyncio.run(process())
    return "OK", 200

async def setup_webhook():
    await telegram_app.bot.set_webhook(url=WEBHOOK_URL)

if __name__ == '__main__':
    # Automatically register the webhook URL with Telegram on startup
    import asyncio
    asyncio.run(setup_webhook())
    
    # Run Flask server to listen for incoming webhooks
    app.run(host="0.0.0.0", port=PORT)