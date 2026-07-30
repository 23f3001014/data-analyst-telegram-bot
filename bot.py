import os
import json
import datetime
import pandas as pd
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# 1. Load Environment Variables
load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Your public GitHub raw URL for run.jsonl logging
RAW_LOG_URL = "https://raw.githubusercontent.com/23f3001014/data-analyst-telegram-bot/main/run.jsonl"

# Helper function to append logs to local run.jsonl (using modern timezone-aware UTC)
def log_interaction(query: str, response_data: dict):
    log_entry = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "query": query,
        "response": response_data
    }
    with open("run.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry) + "\n")

# Command: /start
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome = "Data Analyst Bot Active (Local Engine). Send a dataset (.csv) or ask a question."
    await update.message.reply_text(welcome)

# Handler: File Uploads (.csv / .xlsx)
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    document = update.message.document
    file_name = document.file_name

    if not (file_name.endswith(".csv") or file_name.endswith(".xlsx")):
        err_reply = {"error": "Invalid file. Please upload .csv or .xlsx"}
        await update.message.reply_text(json.dumps(err_reply))
        return

    file = await context.bot.get_file(document.file_id)
    download_path = f"temp_{file_name}"
    await file.download_to_drive(download_path)

    try:
        df = pd.read_csv(download_path) if file_name.endswith(".csv") else pd.read_excel(download_path)
        context.user_data["df"] = df
        context.user_data["dataset_name"] = file_name

        reply = {
            "answer": {
                "file_name": file_name,
                "total_rows": int(df.shape[0]),
                "total_columns": int(df.shape[1]),
                "status": "Dataset successfully loaded into memory."
            },
            "log_url": RAW_LOG_URL
        }
        log_interaction(f"Uploaded file: {file_name}", reply)
        await update.message.reply_text(json.dumps(reply, indent=2))

    except Exception as e:
        err_reply = {"error": str(e), "log_url": RAW_LOG_URL}
        await update.message.reply_text(json.dumps(err_reply))
    finally:
        if os.path.exists(download_path):
            os.remove(download_path)

# Handler: Direct Text Questions using Pandas logic
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_query = update.message.text.strip()

    if "df" not in context.user_data:
        err_reply = {
            "answer": {"error": "Please upload a CSV dataset file first before asking questions."},
            "log_url": RAW_LOG_URL
        }
        await update.message.reply_text(json.dumps(err_reply, indent=2))
        return

    df = context.user_data["df"]
    query_lower = user_query.lower()
    answer_data = {}

    try:
        if "highest" in query_lower and ("party" in query_lower or "candidate" in query_lower):
            party_col = next((col for col in df.columns if 'party' in col.lower() or 'candidate' in col.lower()), df.columns[0])
            vote_col = next((col for col in df.columns if 'vote' in col.lower() or 'total' in col.lower()), None)
            
            if vote_col:
                top_row = df.loc[df[vote_col].idxmax()]
                answer_data = {
                    "party_or_candidate": str(top_row[party_col]),
                    "votes": int(top_row[vote_col])
                }
            else:
                answer_data = {"result": str(df[party_col].value_counts().idxmax())}
        
        elif "total rows" in query_lower or "how many rows" in query_lower:
            answer_data = {"total_rows": int(df.shape[0])}
        
        else:
            answer_data = {
                "query_received": user_query,
                "columns_available": list(df.columns)[:5],
                "row_count": int(df.shape[0])
            }

        response_obj = {
            "answer": answer_data,
            "log_url": RAW_LOG_URL
        }
        
        log_interaction(user_query, response_obj)
        await update.message.reply_text(json.dumps(response_obj, indent=2))

    except Exception as e:
        fallback = {
            "answer": {"error": f"Processing error: {str(e)}"},
            "log_url": RAW_LOG_URL
        }
        log_interaction(user_query, fallback)
        await update.message.reply_text(json.dumps(fallback, indent=2))

# Main Entry Point
if __name__ == "__main__":
    print("Starting Local Data Analyst Bot...")
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot running...")
    app.run_polling()