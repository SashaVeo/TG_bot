import logging
import os
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
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
    raise EnvironmentError("Не установлены TELEGRAM_BOT_TOKEN или OPENAI_API_KEY")

openai.api_key = OPENAI_API_KEY

# === Логгирование ===
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# === Истории чатов ===
chat_histories = {
    "default": {},
    "psychologist": {},
    "astrologer": {}
}
MAX_HISTORY_PAIRS = 10

def get_chat_history(chat_id, mode):
    history_store = chat_histories.get(mode, {})
    return history_store.setdefault(chat_id, [])

def trim_chat_history(history):
    return history[-(MAX_HISTORY_PAIRS * 2):] if len(history) > MAX_HISTORY_PAIRS * 2 else history

def build_keyboard():
    keyboard = [
        [KeyboardButton("🌍 Изображение")],
        [KeyboardButton("💬 Психолог")],
        [KeyboardButton("🔮 Астролог")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def build_back_keyboard():
    return ReplyKeyboardMarkup([[KeyboardButton("⬅️ Назад")]], resize_keyboard=True)

# === Команды ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "😊 Привет! Я бот с GPT-4o. Выбери действие:",
        reply_markup=build_keyboard()
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Выбери действие из меню.", reply_markup=build_keyboard())

# === Обработчик сообщений ===
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    text = update.message.text.strip()

    # Отклонение голосовых сообщений
    if update.message.voice:
        await update.message.reply_text("🔇 Голосовые сообщения не поддерживаются. Пожалуйста, используйте текст.")
        return

    # Назад
    if text == "⬅️ Назад":
        context.user_data["mode"] = "default"
        await update.message.reply_text("🔙 Возвращаемся в главное меню.", reply_markup=build_keyboard())
        return

    # Обработка выбора режима
    if text == "🌍 Изображение":
        context.user_data["mode"] = "image"
        await update.message.reply_text("🖋 Напиши описание изображения, которое хочешь создать:", reply_markup=build_back_keyboard())
        return

    if text == "💬 Психолог":
        context.user_data["mode"] = "psychologist"
        await update.message.reply_text("🧠 Психолог слушает тебя. Расскажи, что тревожит.", reply_markup=build_back_keyboard())
        return

    if text == "🔮 Астролог":
        context.user_data["mode"] = "astrologer"
        await update.message.reply_text("🔮 Я астролог. Введи дату рождения, время и город.", reply_markup=build_back_keyboard())
        return

    mode = context.user_data.get("mode", "default")

    if mode == "image":
        context.user_data["mode"] = "default"
        await update.message.reply_text("🎨 Генерирую изображение...")
        try:
            image_response = openai.images.generate(
                prompt=text,
                model="dall-e-3",
                n=1,
                size="1024x1024"
            )
            image_url = image_response.data[0].url
            await update.message.reply_photo(photo=image_url, reply_markup=build_keyboard())
        except OpenAIError as e:
            logging.error(f"Ошибка OpenAI при генерации изображения: {e}")
            await update.message.reply_text("Ошибка при генерации изображения.", reply_markup=build_keyboard())
        return

    # Обработка текстового сообщения для других режимов
    history = get_chat_history(chat_id, mode)
    history.append({"role": "user", "content": text})
    history = trim_chat_history(history)

    system_prompt = {
        "default": "Ты умный помощник. Отвечай подробно и понятно.",
        "psychologist": "Ты профессиональный психолог. Говори мягко, поддерживающе.",
        "astrologer": "Ты экспертный астролог. Используй астрологические знания, советы и термины."
    }.get(mode, "Ты умный помощник.")

    messages = [{"role": "system", "content": system_prompt}] + history

    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            temperature=0.8,
            max_tokens=1000
        )
        bot_reply = response.choices[0].message.content
        history.append({"role": "assistant", "content": bot_reply})
        chat_histories[mode][chat_id] = trim_chat_history(history)

        await update.message.reply_text(bot_reply, reply_markup=build_back_keyboard() if mode != "default" else build_keyboard())
    except OpenAIError as e:
        logging.error(f"OpenAI ошибка: {e}")
        await update.message.reply_text("Ошибка при получении ответа от GPT.", reply_markup=build_keyboard())

# === Запуск ===
if __name__ == "__main__":
    print("🤖 Бот запускается...")
    defaults = Defaults(parse_mode=None)
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).defaults(defaults).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.VOICE, handle_message))

    logging.info("Бот запущен и слушает события.")
    app.run_polling()
