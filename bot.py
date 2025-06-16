import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, CallbackQueryHandler, filters
)
import openai

# Ключи из переменных среды
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

# Логирование
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# Истории чатов
chat_histories = {}

def get_chat_history(chat_id):
    return chat_histories.setdefault(chat_id, [])

def build_keyboard():
    keyboard = [[InlineKeyboardButton("🌍 Сделать изображение", callback_data="make_image")]]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "😊 Привет! Я бот с GPT-4o. Напиши что-нибудь или нажми кнопку 👇",
        reply_markup=build_keyboard()
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Напиши вопрос или нажми кнопку ниже.")

async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "make_image":
        context.user_data["awaiting_image"] = True
        await query.message.reply_text("🖋 Напиши описание, и я сгенерирую картинку!")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text = update.message.text

    if context.user_data.get("awaiting_image"):
        context.user_data["awaiting_image"] = False
        await update.message.reply_text("🎨 Генерирую изображение...")

        image_response = openai.images.generate(
            prompt=text,
            model="dall-e-3",
            n=1,
            size="1024x1024"
        )
        image_url = image_response.data[0].url
        await update.message.reply_photo(photo=image_url)
        return

    history = get_chat_history(chat_id)
    history.append({"role": "user", "content": text})

    messages = [{"role": "system", "content": "Ты умный помощник. Отвечай подробно и точно."}] + history

    response = openai.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        temperature=0.8,
        max_tokens=1000
    )

    bot_reply = response.choices[0].message.content
    history.append({"role": "assistant", "content": bot_reply})
    await update.message.reply_text(bot_reply, reply_markup=build_keyboard())

# Запуск бота
if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(handle_button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("🤖 Бот запущен...")
    app.run_polling()
