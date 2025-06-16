import logging
import os
from typing import Union
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    CallbackQueryHandler,
    filters,
)
import openai
import base64

# === КЛЮЧИ ===
TELEGRAM_BOT_TOKEN = "TELEGRAM_BOT_TOKEN"
openai.api_key = "OPENAI_API_KEY"

# === ЛОГИ ===
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

# === ХРАНЕНИЕ ИСТОРИИ ===
chat_histories = {}

def get_chat_history(chat_id: Union[int, str]):
    return chat_histories.setdefault(chat_id, [])

# === GPT-4o ТЕКСТОВЫЙ ОТВЕТ ===
def handle_response(chat_id: Union[int, str], text: str) -> str:
    chat_history = get_chat_history(chat_id)
    chat_history.append({"role": "user", "content": text})

    messages = [
        {"role": "system", "content": "Ты мощный ассистент, отвечающий очень подробно и по существу на русском языке. Всегда вежлив, структурируешь ответы, даешь примеры, когда возможно."},
        *chat_history
    ]

    response = openai.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        temperature=0.7,
        max_tokens=1000
    )

    bot_reply = response.choices[0].message.content
    chat_history.append({"role": "assistant", "content": bot_reply})
    return bot_reply

# === START ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🎨 Сделать изображение по описанию", callback_data="make_image")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Привет! Я бот на базе GPT-4o. Задай вопрос или выбери действие:", reply_markup=reply_markup)

# === HELP ===
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Напиши вопрос или нажми кнопку — я помогу! 🧠")

# === СООБЩЕНИЕ ===
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_input = update.message.text
    bot_reply = handle_response(chat_id, user_input)
    await update.message.reply_text(bot_reply)

# === КНОПКИ ===
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "make_image":
        await query.edit_message_text("Опиши, что ты хочешь увидеть на изображении — и я создам его! 🖼️")
        context.user_data["awaiting_image_prompt"] = True

# === ПОЛУЧЕНИЕ ТЕКСТА ДЛЯ ИЗОБРАЖЕНИЯ ===
async def handle_image_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("awaiting_image_prompt"):
        prompt = update.message.text
        context.user_data["awaiting_image_prompt"] = False

        response = openai.images.generate(
            model="dall-e-3",
            prompt=prompt,
            n=1,
            size="1024x1024"
        )
        image_url = response.data[0].url
        await update.message.reply_photo(photo=image_url, caption=f"Вот изображение по описанию: \"{prompt}\" 🎨")
    else:
        await handle_message(update, context)

# === MAIN ===
if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_image_prompt))

    print("🤖 Бот запущен и готов к работе!")
    app.run_polling()
