import logging
import os
import asyncio
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters, Defaults
)
import openai
import aiohttp
import subprocess

# === Переменные окружения ===
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not TELEGRAM_BOT_TOKEN or not OPENAI_API_KEY:
    raise EnvironmentError("Не установлены TELEGRAM_BOT_TOKEN или OPENAI_API_KEY")

openai.api_key = OPENAI_API_KEY

# === URL для загрузки бинарников ===
FFMPEG_URL = "https://github.com/SashaVeo/TG_bot/releases/download/v1.0/ffmpeg"
FFPROBE_URL = "https://github.com/SashaVeo/TG_bot/releases/download/v1.0/ffprobe"

# === Логгирование ===
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

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
        [KeyboardButton("🔮 Астролог")],
        [KeyboardButton("🔙 Назад")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# === Команды ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "😊 Привет! Я бот с GPT-4o. Выбери действие:",
        reply_markup=build_keyboard()
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Выбери действие из меню.", reply_markup=build_keyboard())

# === Обработчик аудио ===
async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file = await update.message.voice.get_file()
    ogg_path = f"voice_{update.message.message_id}.ogg"
    mp3_path = f"voice_{update.message.message_id}.mp3"

    await file.download_to_drive(ogg_path)
    try:
        subprocess.run(["./bin/ffmpeg", "-i", ogg_path, mp3_path], check=True)
        with open(mp3_path, "rb") as audio_file:
            transcript = openai.Audio.transcribe("whisper-1", audio_file)
            update.message.text = transcript["text"]
            await handle_message(update, context)
    except Exception as e:
        await update.message.reply_text("❌ Ошибка при обработке аудио")
        logger.error(f"Ошибка при конвертации: {e}")
    finally:
        if os.path.exists(ogg_path):
            os.remove(ogg_path)
        if os.path.exists(mp3_path):
            os.remove(mp3_path)

# === Обработчик текстовых сообщений ===
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    text = update.message.text.strip()

    mode = context.user_data.get("mode", "default")

    if text == "🔙 Назад":
        context.user_data["mode"] = "default"
        await update.message.reply_text("Главное меню:", reply_markup=build_keyboard())
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
        await update.message.reply_text("🔮 Я астролог. Введи дату рождения, время и город.")
        return

    if mode == "image":
        context.user_data["mode"] = "default"
        await update.message.reply_text("🎨 Генерирую изображение...")
        try:
            response = openai.images.generate(
                prompt=text,
                model="dall-e-3",
                n=1,
                size="1024x1024"
            )
            image_url = response.data[0].url
            await update.message.reply_photo(photo=image_url)
        except Exception as e:
            logger.error(f"Ошибка при генерации изображения: {e}")
            await update.message.reply_text("Ошибка при генерации изображения.")
        return

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

        await update.message.reply_text(bot_reply, reply_markup=build_keyboard())
    except Exception as e:
        logger.error(f"Ошибка OpenAI: {e}")
        await update.message.reply_text("Произошла ошибка. Попробуй ещё раз позже.")

# === Инициализация приложения ===
async def ensure_ffmpeg():
    os.makedirs("./bin", exist_ok=True)
    for name, url in {"ffmpeg": FFMPEG_URL, "ffprobe": FFPROBE_URL}.items():
        path = f"./bin/{name}"
        if not os.path.isfile(path):
            print(f"⬇️  Скачиваем {path}...")
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    with open(path, "wb") as f:
                        f.write(await resp.read())
        os.chmod(path, 0o755)
        print(f"✅ {path} готов к использованию")

if __name__ == "__main__":
    print("🤖 Бот запускается...")
    asyncio.run(ensure_ffmpeg())

    defaults = Defaults(parse_mode=None)
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).defaults(defaults).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logging.info("Бот запущен и слушает события.")
    app.run_polling()
