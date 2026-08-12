import os
import pandas as pd
from threading import Thread
from flask import Flask
from dotenv import load_dotenv
import google.generativeai as genai
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Load environment variables 
load_dotenv()

# Configure Gemini API
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# --- Dummy Web Server to keep Render happy ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running perfectly!"

def run_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
# ---------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Send me a CSV or Excel file, and ask your question in the caption!")

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    document = update.message.document
    caption = update.message.caption

    # Ensure a question is asked in the caption
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

        # Convert the dataframe to a string representation so Gemini can read it
        data_string = df.to_string() 

        # Call the updated Gemini AI model
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        # Build the prompt combining instructions, data, and the user's question
        prompt = f"""
        Here is a dataset:
        {data_string}
        
        Based on this dataset, answer the following query: "{caption}"
        
        Respond ONLY with raw JSON format. Do not use markdown formatting block fences like ```json.
        """
        
        # Get the answer from Gemini
        response = model.generate_content(prompt)
        
        # Send the raw JSON string back to Telegram
        await update.message.reply_text(response.text)

        # Delete the file from the server to save space
        os.remove(file_path)

    except Exception as e:
        await update.message.reply_text(f"An error occurred: {str(e)}")

def main():
    # Start the dummy web server in the background
    server_thread = Thread(target=run_server)
    server_thread.start()

    # Start the Telegram bot
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    application = Application.builder().token(bot_token).build()

    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))

    print("Bot is running and waiting for files...")
    
    # Run the bot until stopped
    application.run_polling()

if __name__ == '__main__':
    main()