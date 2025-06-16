import logging
import os
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters, Defaults
)
import openai
from openai import OpenAIError

# === Переменные окружения ===
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not TELEGRAM_BOT_TOKEN or not OPENAI_API_KEY:
    raise EnvironmentError("❌ Не установлены TELEGRAM_BOT_TOKEN или OPENAI_API_KEY")

openai.api_key = OPENAI_API_KEY

# === Логгирование ===
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# === Настройки истории ===
chat_histories = {}
MAX_HISTORY_PAIRS = 10

def get_chat_history(chat_id):
    return chat_histories.setdefault(chat_id, [])

def trim_chat_history(history):
    return history[-(MAX_HISTORY_PAIRS * 2):] if len(history) > MAX_HISTORY_PAIRS * 2 else history

# === Меню ===
def build_text_menu():
    return ReplyKeyboardMarkup(
        [["Сделать изображение"]],
        resize_keyboard=True,
        one_time_keyboard=False
    )

# === Команды ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logging.info(f"/start от {update.effective_user.id}")
    await update.message.reply_text(
        "😊 Привет! Я бот с GPT-4o. Напиши что-нибудь или нажми кнопку ниже 👇",
        reply_markup=build_text_menu()
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Напиши вопрос или нажми кнопку.", reply_markup=build_text_menu())

# === Сообщения ===
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    text = update.message.text
    logging.info(f"Сообщение от {user_id}: {text}")

    # === Обработка генерации изображения ===
    if context.user_data.get("awaiting_image"):
        context.user_data["awaiting_image"] = False
        await update.message.reply_text("🎨 Генерирую изображение...")

        try:
            image_response = openai.images.generate(
                prompt=text,
                model="dall-e-3",
                n=1,
                size="1024x1024"
            )
            image_url = image_response.data[0].url
            await update.message.reply_photo(photo=image_url)
            logging.info(f"Изображение отправлено пользователю {user_id}.")
        except OpenAIError as e:
            logging.error(f"OpenAI ошибка: {e}")
            await update.message.reply_text("❌ Ошибка генерации изображения.")
        return

    # === Обработка кнопки ===
    if text.lower().strip() == "сделать изображение":
        context.user_data["awaiting_image"] = True
        await update.message.reply_text("🖋 Напиши описание изображения, которое хочешь создать:")
        return

    # === GPT-чат ===
    history = get_chat_history(chat_id)
    history.append({"role": "user", "content": text})
    history = trim_chat_history(history)
    chat_histories[chat_id] = history

    messages = [{"role": "system", "content": "Ты умный помощник. Отвечай подробно и точно."}] + history

    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            temperature=0.8,
            max_tokens=1000
        )
        bot_reply = response.choices[0].message.content
        history.append({"role": "assistant", "content": bot_reply})
        chat_histories[chat_id] = trim_chat_history(history)
        await update.message.reply_text(bot_reply, reply_markup=build_text_menu())
    except OpenAIError as e:
        logging.error(f"OpenAI ошибка: {e}")
        await update.message.reply_text("❌ Ошибка ответа от GPT.", reply_markup=build_text_menu())

# === Запуск ===
if __name__ == "__main__":
    print("🤖 Бот запускается...")
    defaults = Defaults(parse_mode=None)
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).defaults(defaults).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logging.info("✅ Бот запущен и работает.")
    app.run_polling()
