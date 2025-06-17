import logging
import os
import asyncio
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
import aiohttp # aiohttp оставим, он может пригодиться для других целей
import subprocess

# === Переменные окружения ===
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not TELEGRAM_BOT_TOKEN or not OPENAI_API_KEY:
    raise EnvironmentError("Не установлены переменные окружения TELEGRAM_BOT_TOKEN или OPENAI_API_KEY")

# === Инициализация клиента OpenAI ===
client = openai.OpenAI(api_key=OPENAI_API_KEY)

# === Путь к FFMPEG ===
# Теперь ffmpeg будет установлен системно, поэтому достаточно просто его имени
FFMPEG_PATH = "ffmpeg"

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

# === Команды ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "😊 Привет! Я многофункциональный бот с GPT-4o.\n\n"
        "Выберите один из режимов в меню ниже. Вы можете отправлять мне текстовые и голосовые сообщения.",
        reply_markup=build_keyboard()
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Я могу работать в нескольких режимах:\n\n"
        "🌍 **Изображение** - создам картинку по вашему текстовому описанию.\n"
        "💬 **Психолог** - выслушаю и поддержу вас в трудную минуту.\n"
        "🔮 **Астролог** - дам совет, основываясь на звездах.\n\n"
        "Просто выберите режим из меню. Также я умею расшифровывать голосовые сообщения!",
        reply_markup=build_keyboard()
    )

# === Обработчик аудио ===
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
            transcript = client.audio.transcriptions.create(
              model="whisper-1",
              file=audio_file
            )
        
        recognized_text = transcript.text
        logger.info(f"Распознанный текст: '{recognized_text}'")
        
        update.message.text = recognized_text
        await handle_message(update, context)

    except Exception as e:
        await update.message.reply_text("❌ Произошла ошибка при обработке аудио.")
        logger.error(f"Ошибка в handle_voice: {e}")
    finally:
        if ogg_path and os.path.exists(ogg_path):
            os.remove(ogg_path)
        if mp3_path and os.path.exists(mp3_path):
            os.remove(mp3_path)

# === Обработчик текстовых сообщений ===
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text = update.message.text.strip()

    mode = context.user_data.get("mode", "default")

    if text == "🔙 Назад в главное меню":
        context.user_data["mode"] = "default"
        await update.message.reply_text("Вы вернулись в главное меню. Чем могу помочь?", reply_markup=build_keyboard())
        return

    if text == "🌍 Изображение":
        context.user_data["mode"] = "image"
        await update.message.reply_text("🖋 Отправьте мне текстовое описание, и я создам изображение.")
        return

    if text == "💬 Психолог":
        context.user_data["mode"] = "psychologist"
        await update.message.reply_text("🧠 Я вас слушаю. Расскажите, что вас беспокоит. Можете отправить текстовое или голосовое сообщение.")
        return

    if text == "🔮 Астролог":
        context.user_data["mode"] = "astrologer"
        await update.message.reply_text("✨ Я ваш личный астролог. Задайте свой вопрос или опишите ситуацию.")
        return

    if mode == "image":
        context.user_data["mode"] = "default"
        await update.message.reply_text("🎨 Создаю изображение... Это может занять до минуты.", reply_markup=build_keyboard())
        await update.message.chat.send_action(action=ChatAction.UPLOAD_PHOTO)
        try:
            response = client.images.generate(
                model="dall-e-3",
                prompt=text,
                n=1,
                size="1024x1024",
                quality="standard"
            )
            image_url = response.data[0].url
            await update.message.reply_photo(photo=image_url, caption="Ваше изображение готово!")
        except openai.BadRequestError as e:
            logger.error(f"Ошибка генерации изображения (BadRequestError): {e}")
            await update.message.reply_text("К сожалению, я не могу создать изображение по этому запросу. Возможно, он нарушает политику безопасности. Попробуйте переформулировать.")
        except Exception as e:
            logger.error(f"Неизвестная ошибка при генерации изображения: {e}")
            await update.message.reply_text("Произошла непредвиденная ошибка при создании изображения. Пожалуйста, попробуйте позже.")
        return

    history = get_chat_history(chat_id, mode)
    history.append({"role": "user", "content": text})
    
    system_prompts = {
        "default": "Ты — дружелюбный и полезный ассистент GPT-4o. Твои ответы должны быть четкими, структурированными и полезными.",
        "psychologist": "Ты — эмпатичный и профессиональный психолог. Твоя задача — мягко и поддерживающе общаться с пользователем. Не давай прямых советов, а помогай человеку самому найти ответы. Используй открытые вопросы. Проявляй сочувствие и понимание.",
        "astrologer": "Ты — опытный астролог с современным подходом. Используй астрологическую терминологию, но объясняй ее простым языком. Твои прогнозы должны быть позитивными и вдохновляющими, а не фаталистичными."
    }
    system_prompt = system_prompts.get(mode, system_prompts["default"])

    messages = [{"role": "system", "content": system_prompt}] + trim_chat_history(history)

    try:
        await update.message.chat.send_action(action=ChatAction.TYPING)
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            temperature=0.7,
            max_tokens=1500
        )
        bot_reply = response.choices[0].message.content
        
        history.append({"role": "assistant", "content": bot_reply})
        chat_histories[mode][chat_id] = history

        await update.message.reply_text(bot_reply, reply_markup=build_keyboard())

    except Exception as e:
        logger.error(f"Ошибка ответа OpenAI: {e}")
        await update.message.reply_text("К сожалению, произошла ошибка. Пожалуйста, попробуйте еще раз позже.")

# === Инициализация и запуск бота ===
async def main() -> None:
    """Основная асинхронная функция для настройки и запуска бота."""
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
            
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот останавливается...")
        print("\n shutting down bot...")
    finally:
        if application.updater and application.updater.running:
            await application.updater.stop()
        if application.running:
            await application.stop()
        await application.shutdown()
        logger.info("Бот успешно остановлен.")
        print("🔌 Бот успешно остановлен.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Программа прервана пользователем.")
