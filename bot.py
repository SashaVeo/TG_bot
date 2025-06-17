import os
import logging
import urllib.request
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters, Defaults
)
import openai
from openai import OpenAIError

# === Настройки окружения ===
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

# === Настройки загрузки бинарников ===
BIN_DIR = "./bin"
FFMPEG_PATH = os.path.join(BIN_DIR, "ffmpeg")
FFPROBE_PATH = os.path.join(BIN_DIR, "ffprobe")
FFMPEG_URL = "https://github.com/SashaVeo/TG_bot/releases/download/v1.0/ffmpeg"
FFPROBE_URL = "https://github.com/SashaVeo/TG_bot/releases/download/v1.0/ffprobe"

def download_binary(url, path):
    if not os.path.exists(path):
        print(f"⬇️ Скачиваем {path}...")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        urllib.request.urlretrieve(url, path)
        os.chmod(path, 0o755)
        print(f"✅ {path} скачан и готов к использованию.")
    else:
        print(f"⚙️ {path} уже существует.")

download_binary(FFMPEG_URL, FFMPEG_PATH)
download_binary(FFPROBE_URL, FFPROBE_PATH)
os.environ["PATH"] = f"{os.path.abspath(BIN_DIR)}:" + os.environ["PATH"]

# === Логгирование ===
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# === Хранилище истории ===
chat_histories = {
    "default": {},
    "psychologist": {},
    "astrologer": {}
}
MAX_HISTORY_PAIRS = 10

def get_chat_history(chat_id, mode):
    return chat_histories.get(mode, {}).setdefault(chat_id, [])

def trim_chat_history(history):
    return history[-(MAX_HISTORY_PAIRS * 2):] if len(history) > MAX_HISTORY_PAIRS * 2 else history

def build_keyboard():
    keyboard = [
        [KeyboardButton("🌍 Изображение")],
        [KeyboardButton("💬 Психолог")],
        [KeyboardButton("🔮 Астролог")],
        [KeyboardButton("⬅️ Назад")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# === Обработчики команд ===
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
    mode = context.user_data.get("mode", "default")

    if text == "⬅️ Назад":
        context.user_data["mode"] = "default"
        await update.message.reply_text("🔙 Возврат в главное меню.", reply_markup=build_keyboard())
        return

    if text == "🌍 Изображение":
        context.user_data["mode"] = "image"
        await update.message.reply_text("🖋 Напиши описание изображения, которое хочешь создать:")
        return

    if text == "💬 Психолог":
        context.user_data["mode"] = "psychologist"
        await update.message.reply_text("🧠 Психолог слушает тебя. Расскажи, что тревожит.")
        return

    if text == "🔮 Астролог":
        context.user_data["mode"] = "astrologer"
        await update.message.reply_text("🔮 Введи дату рождения, время и город. Я дам тебе астрологический прогноз.")
        return

    if context.user_data.get("mode") == "image":
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
            await update.message.reply_photo(photo=image_url)
        except OpenAIError as e:
            logging.error(f"Ошибка генерации изображения: {e}")
            await update.message.reply_text("Ошибка при генерации изображения.")
        return

    history = get_chat_history(chat_id, mode)
    history.append({"role": "user", "content": text})
    history = trim_chat_history(history)

    system_prompt = {
        "default": "Ты умный помощник. Отвечай подробно и понятно.",
        "psychologist": "Ты профессиональный психолог. Говори мягко, поддерживающе.",
        "astrologer": "Ты экспертный астролог. Используй знания и термины астрологии."
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
        await update.message.reply_text(bot_reply, reply_markup=build_keyboard())
    except OpenAIError as e:
        logging.error(f"OpenAI ошибка: {e}")
        await update.message.reply_text("Ошибка при получении ответа от GPT.")

# === Запуск бота ===
if __name__ == "__main__":
    print("🤖 Бот запускается...")
    defaults = Defaults(parse_mode=None)
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).defaults(defaults).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logging.info("Бот запущен и слушает события.")
    app.run_polling()
