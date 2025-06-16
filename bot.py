import logging
import os
from typing import Union
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
import openai

# === Токены ===
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
openai.api_key = os.environ.get("OPENAI_API_KEY")

# Хранение истории
chat_histories = {}

# Логирование
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

def get_chat_history(chat_id: Union[int, str]):
    return chat_histories.setdefault(chat_id, [])

# Ответ от GPT-4o
def handle_response(chat_id: Union[int, str], text: str) -> str:
    history = get_chat_history(chat_id)
    history.append({"role": "user", "content": text})

    messages = [{"role": "system", "content": "Ты — гопник из 90-х, отвечаешь нагло и неохотно."}] + history

    response = openai.chat.completions.create(
        model="gpt-4o",
        messages=messages
    )

    bot_reply = response.choices[0].message.content
    history.append({"role": "assistant", "content": bot_reply})
    return bot_reply

# Команды
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Привет! Я бот на GPT-4o. Напиши что-нибудь, гавнюк.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Просто пиши — я отвечаю.")

# Обработка текста
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_input = update.message.text
    bot_reply = handle_response(chat_id, user_input)
    await update.message.reply_text(bot_reply)

# Запуск
if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🤖 Бот запущен...")
    app.run_polling()
