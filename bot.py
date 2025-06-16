import logging
import os
from typing import Union
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
import openai

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

chat_histories = {}

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

def get_chat_history(chat_id: Union[int, str]):
    return chat_histories.setdefault(chat_id, [])

def handle_response(chat_id: Union[int, str], text: str) -> str:
    chat_history = get_chat_history(chat_id)
    user_message = {"role": "user", "content": text}
    chat_history.append(user_message)

    messages = [
        {
            "role": "system",
            "content": "Ты — гопник из 90-х, который жил в России в это время, отвечаешь нагло и неохотно.",
        }
    ] + chat_history

    response = openai.ChatCompletion.create(
        model="gpt-4o",
        messages=messages,
        temperature=0.8,
        max_tokens=300
    )

    bot_response = response["choices"][0]["message"]["content"]
    chat_history.append({"role": "assistant", "content": bot_response})
    return bot_response

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Привет! Я чертов бот на GPT-4oбля. Напиши мне что-нибудь и отвали!")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Напиши любой вопрос или сообщение — я постараюсь ответить 🤖")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_input = update.message.text
    bot_reply = handle_response(chat_id, user_input)
    await update.message.reply_text(bot_reply)

if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🤖 Бот запущен...")
    app.run_polling()
