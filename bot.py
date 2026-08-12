import os
import json
import pandas as pd
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure the Gemini API and Telegram Token
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file_id = update.message.document.file_id
    # Get the user's question from the caption
    caption = update.message.caption or "Analyze this data."
    
    await update.message.reply_text("Downloading and analyzing your file with Gemini...")
    
    new_file = await context.bot.get_file(file_id)
    file_path = f"downloads/{update.message.document.file_name}"
    os.makedirs("downloads", exist_ok=True)
    await new_file.download_to_drive(file_path)

    try:
        # Read the file into a string
        if file_path.endswith('.csv'):
            df = pd.read_csv(file_path)
        else:
            df = pd.read_excel(file_path)
            
        csv_data = df.to_csv(index=False)
        
        # Create the prompt with strict instructions for JSON output
        prompt = f"""
        You are a data analyst bot. Analyze the following CSV data:
        {csv_data}
        
        The user asked: "{caption}"
        
        Respond ONLY with a raw JSON object containing the answer. Use this exact structure:
        {{
            "answer": {{
                "party_or_candidate": "NAME",
                "votes": 12345
            }},
            "log_url": "https://raw.githubusercontent.com/23f3001014/data-analyst-telegram-bot/main/run.jsonl"
        }}
        """

        # Call Gemini and enforce JSON output format
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json"
            )
        )

        # Send the raw JSON text back to Telegram
        await update.message.reply_text(response.text)

    except Exception as e:
        await update.message.reply_text(f"An error occurred: {e}")

def main():
    # Initialize the Telegram bot application
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Listen for any document uploads
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    
    print("Bot is running and waiting for files...")
    app.run_polling()

if __name__ == "__main__":
    main()