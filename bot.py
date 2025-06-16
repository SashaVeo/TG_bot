import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)
from openai import OpenAI

# Ключи из переменных среды
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)

# Логгирование
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

# Истории чатов
chat_histories = {}
image_request_flags = {}

def get_chat_history(chat_id):
    return chat_histories.setdefault(chat_id, [])

def build_keyboard():
    keyboard = [[InlineKeyboardButton("🌍 Сделать изображение", callback_data="make_image")]]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "😊 Привет! Я бот с GPT-4o. Напиши что-то или выбери кнопку.",
        reply_markup=build_keyboard()
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Напиши вопрос или нажми кнопку")

async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "make_image":
        await query.message.reply_text("🖋️ Напиши описание изображения")
        image_request_flags[query.message.chat.id] = True

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text = update.message.text
    history = get_chat_history(chat_id)

    # Если ждем описание для изображения
    if image_request_flags.get(chat_id):
        image_request_flags[chat_id] = False
        await update.message.reply_text("🎨 Создаю изображение...")
        image_response = client.images.generate(
            model="dall-e-3",
            prompt=text,
            n=1,
            size="1024x1024"
        )
        image_url = image_response.data[0].url
        await update.message.reply_photo(photo=image_url)
        return

    # Обычный текст
    history.append({"role": "user", "content": text})
    messages = [{
        "role": "system",
        "content": "Ты полноценный GPT-4o. Отвечаешь подробно, ссылаешься на контекст."
    }] + history

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        temperature=0.8,
        max_tokens=1000
    )
    bot_reply = response.choices[0].message.content
    history.append({"role": "assistant", "content": bot_reply})
    await update.message.reply_text(bot_reply, reply_markup=build_keyboard())

# === Запуск ===
if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(handle_button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("🤖 Бот запущен...")
    app.run_polling()
