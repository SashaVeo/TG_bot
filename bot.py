import logging
import os
import openai
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, CallbackQueryHandler, filters
)

# 🔐 Ключи
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

# 🔹 Логирование
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

# 🧠 Истории чатов
chat_histories = {}

# 🎛 Кнопки
def build_keyboard():
    keyboard = [[InlineKeyboardButton("🖼 Сделать изображение", callback_data="make_image")]]
    return InlineKeyboardMarkup(keyboard)

# 🚀 /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Привет! Я бот на GPT-4o. Напиши вопрос или нажми кнопку:",
        reply_markup=build_keyboard()
    )

# ℹ️ /help
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Просто напиши любой вопрос или нажми кнопку ниже:")

# 🔘 Обработка кнопки
async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "make_image":
        await query.message.reply_text("🖋 Напиши короткое описание — я создам изображение.")
        context.user_data["awaiting_image_description"] = True

# 💬 Обработка текста
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text = update.message.text

    # Режим генерации изображения
    if context.user_data.get("awaiting_image_description"):
        context.user_data["awaiting_image_description"] = False
        await update.message.reply_text("🎨 Генерирую изображение...")

        response = openai.Image.create(
            prompt=text,
            n=1,
            size="1024x1024"
        )
        image_url = response['data'][0]['url']
        await update.message.reply_photo(photo=image_url)
        return

    # Режим обычного чата
    history = chat_histories.setdefault(chat_id, [])
    history.append({"role": "user", "content": text})
    messages = [{"role": "system", "content": "Ты GPT-4o. Отвечай подробно и вежливо."}] + history

    completion = openai.ChatCompletion.create(
        model="gpt-4o",
        messages=messages,
        temperature=0.8,
        max_tokens=1000
    )
    reply = completion["choices"][0]["message"]["content"]
    history.append({"role": "assistant", "content": reply})
    await update.message.reply_text(reply, reply_markup=build_keyboard())

# ▶️ Запуск
if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(handle_button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("🤖 Бот запущен...")
    app.run_polling()
