import logging
import os
import tempfile
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters, Defaults
)
import openai
from openai import OpenAIError
from pydub import AudioSegment

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
        [KeyboardButton("🌍 Изображение"), KeyboardButton("🔙 Назад")],
        [KeyboardButton("💬 Психолог"), KeyboardButton("🔮 Астролог")]
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

# === Обработчик голосовых сообщений ===
async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file = await update.message.voice.get_file()
    with tempfile.NamedTemporaryFile(delete=False, suffix=".ogg") as f:
        ogg_path = f.name
        await file.download_to_drive(ogg_path)

    mp3_path = ogg_path.replace(".ogg", ".mp3")
    audio = AudioSegment.from_file(ogg_path)
    audio.export(mp3_path, format="mp3")

    try:
        with open(mp3_path, "rb") as audio_file:
            transcript = openai.Audio.transcribe("whisper-1", audio_file)
            text = transcript["text"]
            await update.message.reply_text(f"🔊 Распознано:\n{text}")
            update.message.text = text
            await handle_message(update, context)
    except Exception as e:
        logging.error(f"Ошибка при распознавании аудио: {e}")
        await update.message.reply_text("❌ Не удалось распознать голосовое сообщение.")

# === Обработчик сообщений ===
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    text = update.message.text.strip()

    mode = context.user_data.get("mode", "default")

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

    if text == "🔙 Назад":
        context.user_data["mode"] = "default"
        await update.message.reply_text("🔁 Возврат в главное меню.", reply_markup=build_keyboard())
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
            logging.error(f"Ошибка OpenAI при генерации изображения: {e}")
            await update.message.reply_text("Ошибка при генерации изображения.")
        return

    history_mode = context.user_data.get("mode", "default")
    history = get_chat_history(chat_id, history_mode)
    history.append({"role": "user", "content": text})
    history = trim_chat_history(history)

    system_prompt = {
        "default": "Ты умный помощник. Отвечай подробно и понятно.",
        "psychologist": "Ты профессиональный психолог. Говори мягко, поддерживающе.",
        "astrologer": "Ты экспертный астролог. Используй астрологические знания, советы и термины."
    }.get(history_mode, "Ты умный помощник.")

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
        chat_histories[history_mode][chat_id] = trim_chat_history(history)

        await update.message.reply_text(bot_reply, reply_markup=build_keyboard())
    except OpenAIError as e:
        logging.error(f"OpenAI ошибка: {e}")
        await update.message.reply_text("Ошибка при получении ответа от GPT.")

# === Запуск ===
if __name__ == "__main__":
    print("🤖 Бот запускается...")
    defaults = Defaults(parse_mode=None)
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).defaults(defaults).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logging.info("Бот запущен и слушает события.")
    app.run_polling()
