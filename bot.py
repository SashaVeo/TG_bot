import logging
import os
import asyncio
import aiohttp
import subprocess
import tarfile # Библиотека для работы с .tar.gz архивами

from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from telegram.constants import ChatAction
import openai

# === Переменные окружения ===
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not TELEGRAM_BOT_TOKEN or not OPENAI_API_KEY:
    raise EnvironmentError("Не установлены переменные окружения TELEGRAM_BOT_TOKEN или OPENAI_API_KEY")

# === Инициализация клиента OpenAI ===
client = openai.OpenAI(api_key=OPENAI_API_KEY)

# === Пути и URL для FFMPEG ===
# URL для статической сборки ffmpeg под Linux x86-64 (стандарт для серверов)
FFMPEG_STATIC_URL = "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz"
BIN_DIR = "./bin"
FFMPEG_PATH = os.path.join(BIN_DIR, "ffmpeg")


# === Логгирование ===
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


async def ensure_ffmpeg():
    """
    Проверяет наличие ffmpeg. Если его нет, скачивает статический билд,
    распаковывает и делает исполняемым.
    """
    if os.path.isfile(FFMPEG_PATH):
        logger.info(f"✅ FFMPEG уже на месте: {FFMPEG_PATH}")
        os.chmod(FFMPEG_PATH, 0o755)
        return

    logger.info("⬇️ FFMPEG не найден. Скачиваю статический билд...")
    os.makedirs(BIN_DIR, exist_ok=True)
    archive_path = os.path.join(BIN_DIR, "ffmpeg.tar.xz")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(FFMPEG_STATIC_URL) as resp:
                if resp.status != 200:
                    logger.error(f"Не удалось скачать FFMPEG. Статус код: {resp.status}")
                    raise RuntimeError("Download of ffmpeg failed")
                with open(archive_path, "wb") as f:
                    f.write(await resp.read())
        logger.info("📦 Архив FFMPEG успешно скачан.")

        logger.info("Распаковываю архив FFMPEG...")
        with tarfile.open(archive_path, "r:xz") as tar:
            for member in tar.getmembers():
                if member.name.endswith('/ffmpeg'):
                    member.name = os.path.basename(member.name)
                    tar.extract(member, path=BIN_DIR)
                    logger.info(f"Распакован {member.name} в {BIN_DIR}")
                    break
        
        if not os.path.isfile(FFMPEG_PATH):
            raise RuntimeError("ffmpeg не найден в распакованном архиве")

        os.chmod(FFMPEG_PATH, 0o755)
        logger.info(f"✅ FFMPEG готов к использованию: {FFMPEG_PATH}")

    except Exception as e:
        logger.error(f"Произошла ошибка при установке FFMPEG: {e}")
        raise
    finally:
        if os.path.exists(archive_path):
            os.remove(archive_path)

# === Остальная часть кода (без изменений) ===
# ... (вставьте сюда остальную часть кода из предыдущих сообщений, она не менялась)
# === Истории чатов и клавиатура ===
chat_histories = { "default": {}, "psychologist": {}, "astrologer": {} }
MAX_HISTORY_PAIRS = 10

def get_chat_history(chat_id, mode):
    return chat_histories.get(mode, {}).setdefault(chat_id, [])

def trim_chat_history(history):
    if len(history) > MAX_HISTORY_PAIRS * 2:
        return history[-(MAX_HISTORY_PAIRS * 2):]
    return history

def build_keyboard():
    keyboard = [
        [KeyboardButton("🌍 Изображение")],
        [KeyboardButton("💬 Психолог"), KeyboardButton("🔮 Астролог")],
        [KeyboardButton("🔙 Назад в главное меню")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# === Обработчики команд и сообщений ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "😊 Привет! Я многофункциональный бот с GPT-4o.\n\n"
        "Выберите один из режимов в меню ниже.",
        reply_markup=build_keyboard()
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Я могу работать в нескольких режимах:\n\n"
        "🌍 **Изображение** - создам картинку по вашему текстовому описанию.\n"
        "💬 **Психолог** - выслушаю и поддержу.\n"
        "🔮 **Астролог** - дам совет.\n\n"
        "Я также умею расшифровывать голосовые сообщения!",
        reply_markup=build_keyboard()
    )

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ogg_path = None
    mp3_path = None
    try:
        file_id = update.message.voice.file_id
        voice_file = await context.bot.get_file(file_id)
        
        ogg_path = f"voice_{file_id}.ogg"
        mp3_path = f"voice_{file_id}.mp3"

        await voice_file.download_to_drive(ogg_path)
        await update.message.chat.send_action(action=ChatAction.TYPING)

        process = await asyncio.create_subprocess_exec(
            FFMPEG_PATH, "-i", ogg_path, "-y", mp3_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            logger.error(f"Ошибка конвертации ffmpeg: {stderr.decode()}")
            await update.message.reply_text("❌ Не удалось обработать ваше голосовое сообщение.")
            return

        with open(mp3_path, "rb") as audio_file:
            transcript = client.audio.transcriptions.create(model="whisper-1", file=audio_file)
        
        update.message.text = transcript.text
        await handle_message(update, context)

    except Exception as e:
        logger.error(f"Ошибка в handle_voice: {e}")
        await update.message.reply_text("❌ Произошла ошибка при обработке аудио.")
        
    finally:
        if ogg_path and os.path.exists(ogg_path): os.remove(ogg_path)
        if mp3_path and os.path.exists(mp3_path): os.remove(mp3_path)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text = update.message.text.strip()
    mode = context.user_data.get("mode", "default")
    if text == "🔙 Назад в главное меню":
        context.user_data["mode"] = "default"
        await update.message.reply_text("Вы вернулись в главное меню.", reply_markup=build_keyboard())
        return
    if text == "🌍 Изображение":
        context.user_data["mode"] = "image"
        await update.message.reply_text("🖋 Напишите описание изображения.")
        return
    if text == "💬 Психолог":
        context.user_data["mode"] = "psychologist"
        await update.message.reply_text("🧠 Я вас слушаю...")
        return
    if text == "🔮 Астролог":
        context.user_data["mode"] = "astrologer"
        await update.message.reply_text("✨ Задайте свой вопрос.")
        return
    if mode == "image":
        context.user_data["mode"] = "default"
        await update.message.reply_text("🎨 Создаю изображение...", reply_markup=build_keyboard())
        await update.message.chat.send_action(action=ChatAction.UPLOAD_PHOTO)
        try:
            response = client.images.generate(model="dall-e-3", prompt=text, n=1, size="1024x1024", quality="standard")
            image_url = response.data[0].url
            await update.message.reply_photo(photo=image_url, caption="Ваше изображение готово!")
        except Exception as e:
            logger.error(f"Ошибка генерации изображения: {e}")
            await update.message.reply_text("Не удалось создать изображение.")
        return
    history = get_chat_history(chat_id, mode)
    history.append({"role": "user", "content": text})
    system_prompts = {
        "default": "Ты — дружелюбный и полезный ассистент.",
        "psychologist": "Ты — эмпатичный и профессиональный психолог.",
        "astrologer": "Ты — опытный астролог."
    }
    system_prompt = system_prompts.get(mode, system_prompts["default"])
    messages = [{"role": "system", "content": system_prompt}] + trim_chat_history(history)
    try:
        await update.message.chat.send_action(action=ChatAction.TYPING)
        response = client.chat.completions.create(model="gpt-4o", messages=messages, temperature=0.7, max_tokens=1500)
        bot_reply = response.choices[0].message.content
        history.append({"role": "assistant", "content": bot_reply})
        await update.message.reply_text(bot_reply, reply_markup=build_keyboard())
    except Exception as e:
        logger.error(f"Ошибка ответа OpenAI: {e}")
        await update.message.reply_text("Произошла ошибка.")

# === Запуск бота ===
async def main() -> None:
    # При запуске сначала убедимся, что ffmpeg на месте
    await ensure_ffmpeg()

    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.VOICE, handle_voice))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    try:
        logger.info("Бот запускается...")
        print("🤖 Бот запускается...")
        await application.initialize()
        await application.start()
        await application.updater.start_polling()
        logger.info("Бот успешно запущен и готов к работе.")
        print("✅ Бот успешно запущен и готов к работе.")
        while True:
            await asyncio.sleep(3600)
    finally:
        if application.updater and application.updater.running:
            await application.updater.stop()
        await application.stop()
        await application.shutdown()
        logger.info("Бот успешно остановлен.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Программа прервана пользователем.")
