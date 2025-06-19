import logging
import os
import asyncio
import aiohttp
import subprocess
import tarfile
import requests # <-- ДОБАВЛЕНО: для работы с API RunwayML

from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, InputFile
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
# --- ДОБАВЛЕНО: API ключ RunwayML ---
RUNWAYML_API_KEY = os.getenv("RUNWAYML_API_KEY") # Предполагаем, что ключ будет в переменной окружения

if not TELEGRAM_BOT_TOKEN or not OPENAI_API_KEY or not RUNWAYML_API_KEY: # <-- ИЗМЕНЕНО: добавлена проверка RUNWAYML_API_KEY
    raise EnvironmentError("Не установлены необходимые переменные окружения: TELEGRAM_BOT_TOKEN, OPENAI_API_KEY или RUNWAYML_API_KEY")

# === Инициализация клиента OpenAI ===
client = openai.OpenAI(api_key=OPENAI_API_KEY)

# === Пути и URL для FFMPEG ===
FFMPEG_STATIC_URL = "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz"
BIN_DIR = "./bin"
FFMPEG_PATH = os.path.join(BIN_DIR, "ffmpeg")

# --- ДОБАВЛЕНО: URL и настройки для RunwayML ---
# Важно: Сверься с официальной документацией RunwayML для Gen-4, чтобы убедиться в актуальности URL и структуры payload.
RUNWAYML_API_GENERATE_URL = "https://api.runwayml.com/v1/generate"
MAX_PROMPT_LENGTH_RUNWAY = 1300 # Максимальная длина промпта для RunwayML Gen-4

# === Логгирование ===
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def ensure_ffmpeg():
    # ... (код этой функции не менялся)
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
                    raise RuntimeError(f"Не удалось скачать FFMPEG. Статус код: {resp.status}")
                with open(archive_path, "wb") as f:
                    f.write(await resp.read())
        logger.info("📦 Архив FFMPEG успешно скачан.")
        logger.info("Распаковываю архив FFMPEG...")
        with tarfile.open(archive_path, "r:xz") as tar:
            for member in tar.getmembers():
                if member.name.endswith('/ffmpeg'):
                    member.name = os.path.basename(member.name)
                    tar.extract(member, path=BIN_DIR)
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

# === Истории чатов ===
chat_histories = { "default": {}, "psychologist": {}, "astrologer": {} } # <-- ИЗМЕНЕНО: "default" используется как база
MAX_HISTORY_PAIRS = 10

def get_chat_history(chat_id, mode):
    # Если режим не имеет своей собственной истории, используем default
    if mode not in chat_histories:
        return chat_histories["default"].setdefault(chat_id, [])
    return chat_histories.get(mode, {}).setdefault(chat_id, [])

def trim_chat_history(history):
    if len(history) > MAX_HISTORY_PAIRS * 2:
        return history[-(MAX_HISTORY_PAIRS * 2):]
    return history

def build_keyboard():
    # --- ИЗМЕНЕНИЕ: Добавлена кнопка "Видеообложка" ---
    keyboard = [
        [KeyboardButton("📈 SEO"), KeyboardButton("🌍 Изображение")],
        [KeyboardButton("💁‍♀️ Помощница"), KeyboardButton("💬 Психолог")],
        [KeyboardButton("🔮 Астролог"), KeyboardButton("🎬 Видеообложка")], # <-- ДОБАВЛЕНО
        [KeyboardButton("🔙 Назад в главное меню")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# === Обработчики команд ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "😊 Привет! Я ваш многофункциональный ассистент с GPT-4o.\n\n"
        "Выберите один из режимов в меню ниже.",
        reply_markup=build_keyboard()
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Я могу работать в нескольких режимах:\n\n"
        "📈 **SEO** - напишу текст для карточки товара по ключевым словам.\n"
        "💁‍♀️ **Помощница** - составлю вежливый ответ на отзыв клиента.\n"
        "🌍 **Изображение** - создам картинку по вашему текстовому описанию.\n"
        "🎬 **Видеообложка** - сгенерирую 5-секундный видеоролик по описанию.\n" # <-- ДОБАВЛЕНО
        "💬 **Психолог** - выслушаю и поддержу.\n"
        "🔮 **Астролог** - дам совет.\n\n"
        "Я также умею расшифровывать голосовые сообщения!",
        reply_markup=build_keyboard()
    )

# === Обработчики сообщений ===
async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ... (код этой функции не менялся)
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
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        await process.communicate()
        if process.returncode != 0:
            raise subprocess.CalledProcessError(process.returncode, cmd=FFMPEG_PATH)
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
    
    # === Навигация по меню ===
    if text == "🔙 Назад в главное меню":
        context.user_data["mode"] = "default"
        await update.message.reply_text("Вы вернулись в главное меню.", reply_markup=build_keyboard())
        return
    if text == "📈 SEO":
        context.user_data["mode"] = "seo"
        await update.message.reply_text(
            "Отправьте мне список ключевых слов (например, через запятую), и я создам SEO-оптимизированное описание для карточки товара на Wildberries (1500-2000 символов)."
        )
        return
    if text == "💁‍♀️ Помощница":
        context.user_data["mode"] = "assistant"
        await update.message.reply_text(
            "Пришлите мне отзыв или вопрос клиента. Я подготовлю вежливый и профессиональный ответ от имени Евгении Ланцовой из 'Немецкого дома'."
        )
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
    # --- ДОБАВЛЕНО: Обработчик для кнопки "Видеообложка" ---
    if text == "🎬 Видеообложка":
        context.user_data["mode"] = "video_cover"
        await update.message.reply_text(
            f"Отлично! Теперь пришлите мне текстовое описание для 5-секундной видеообложки (до {MAX_PROMPT_LENGTH_RUNWAY} символов).",
            reply_markup=build_keyboard() # Можно оставить клавиатуру, чтобы пользователь мог вернуться
        )
        return

    # === Логика для каждого режима ===
    if mode == "video_cover": # <-- ДОБАВЛЕНО: Логика для режима "Видеообложка"
        user_prompt = text
        context.user_data["mode"] = "default" # Возвращаем в дефолтный режим после получения промпта

        if not user_prompt:
            await update.message.reply_text("Пожалуйста, отправь мне текстовое описание для генерации видео.")
            return

        if len(user_prompt) > MAX_PROMPT_LENGTH_RUNWAY:
            await update.message.reply_text(
                f"Твой промпт слишком длинный. Максимальная длина - {MAX_PROMPT_LENGTH_RUNWAY} символов. "
                "Пожалуйста, сократи его.",
                reply_markup=build_keyboard()
            )
            return

        await update.message.reply_text("Отлично! Я начинаю генерировать видеообложку. Это может занять некоторое время, пожалуйста, подожди...", reply_markup=build_keyboard())
        await update.message.chat.send_action(action=ChatAction.UPLOAD_VIDEO) # Показываем, что бот загружает видео

        try:
            # Формируем данные для запроса к RunwayML API
            payload = {
                "prompt": user_prompt,
                "duration": 5, # 5 секунд
                "aspect_ratio": "3:4", # Соотношение сторон
                # Здесь могут быть другие параметры, специфичные для Gen-4.
                # Сверяйся с документацией RunwayML!
            }
            headers = {
                "Authorization": f"Bearer {RUNWAYML_API_KEY}",
                "Content-Type": "application/json"
            }

            logger.info(f"Отправка запроса в RunwayML с промптом: '{user_prompt}'")
            response = requests.post(RUNWAYML_API_GENERATE_URL, json=payload, headers=headers)
            response.raise_for_status()  # Выбросит исключение для ошибок HTTP (4xx или 5xx)

            runway_data = response.json()
            
            # Предполагаем, что URL видео находится в поле 'video_url'
            # Это может отличаться, проверь документацию RunwayML!
            video_url = runway_data.get("video_url") 
            
            if not video_url:
                logger.error(f"Не удалось получить URL видео из ответа RunwayML: {runway_data}")
                await update.message.reply_text(
                    "Произошла ошибка при генерации видеообложки. URL видео не найден в ответе.",
                    reply_markup=build_keyboard()
                )
                return

            logger.info(f"Видео сгенерировано. URL: {video_url}")

            # Скачивание видео
            video_response = requests.get(video_url, stream=True)
            video_response.raise_for_status()

            # Отправка видео пользователю
            await update.message.reply_video(
                video=InputFile(video_response.raw, filename="video_cover.mp4"),
                caption="Вот твоя 5-секундная видеообложка от RunwayML Gen-4!",
                reply_markup=build_keyboard()
            )

        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка запроса к RunwayML API: {e}")
            await update.message.reply_text(
                "Произошла ошибка при генерации видеообложки (проблема с соединением или API). Пожалуйста, попробуй еще раз позже.",
                reply_markup=build_keyboard()
            )
        except Exception as e:
            logger.error(f"Произошла непредвиденная ошибка при обработке видеообложки: {e}")
            await update.message.reply_text(
                "Произошла непредвиденная ошибка при генерации видеообложки. Пожалуйста, попробуй еще раз позже.",
                reply_markup=build_keyboard()
            )
        return # Важно завершить обработку сообщения здесь

    if mode == "assistant":
        # ... (код для assistant режима не менялся, но теперь помещен выше)
        context.user_data["mode"] = "default"
        customer_feedback = text
        await update.message.reply_text("✅ Готовлю ответ от имени менеджера...", reply_markup=build_keyboard())
        await update.message.chat.send_action(action=ChatAction.TYPING)
        try:
            assistant_system_prompt = (
                "Ты — Евгения Ланцова, менеджер по заботе о клиентах в компании 'Немецкий дом'. "
                "Твоя задача — отвечать на отзывы и вопросы клиентов максимально вежливо, профессионально и понятно. "
                "Твоя цель — решить проблему клиента, поблагодарить за отзыв и оставить положительное впечатление о компании. "
                "В конце КАЖДОГО ответа, без каких-либо исключений, ты ОБЯЗАНА добавить следующую подпись на трех отдельных строках:\n"
                "Ваш \"Немецкий дом\"\n"
                "Менеджер заботы о клиентах\n"
                "Евгения Ланцова"
            )
            messages = [
                {"role": "system", "content": assistant_system_prompt},
                {"role": "user", "content": f"Вот отзыв/вопрос клиента, на который нужно ответить:\n\n---\n\n{customer_feedback}"}
            ]
            response = client.chat.completions.create(
                model="gpt-4o", messages=messages, temperature=0.5, max_tokens=500
            )
            assistant_reply = response.choices[0].message.content.strip()
            final_response = (
                f"✅ *Ответ от Евгении Ланцовой готов:*\n\n"
                f"```\n{assistant_reply}\n```"
            )
            await update.message.reply_text(final_response, parse_mode='MarkdownV2')
        except Exception as e:
            logger.error(f"Ошибка при генерации ответа на отзыв: {e}")
            await update.message.reply_text("❌ Произошла ошибка при генерации ответа.")
        return

    if mode == "seo":
        # ... (код для SEO режима не менялся)
        context.user_data["mode"] = "default"
        keywords = text
        await update.message.reply_text("✅ Принял. Генерирую SEO-текст...", reply_markup=build_keyboard())
        await update.message.chat.send_action(action=ChatAction.TYPING)
        try:
            seo_system_prompt = (
                "Ты — опытный SEO-специалист и копирайтер для маркетплейсов. "
                "Твоя задача — сгенерировать продающий, хорошо структурированный и SEO-оптимизированный текст для карточки товара на Wildberries. "
                "Текст должен быть объемом строго от 1500 до 2000 символов. "
                "Обязательно используй предоставленные ключевые слова органично и естественно, распределяя их по всему тексту. "
                "Текст должен быть легко читаемым, разделенным на абзацы, и привлекательным для покупателя. "
                "Не используй Markdown или HTML теги в ответе, только обычный текст."
            )
            messages = [
                {"role": "system", "content": seo_system_prompt},
                {"role": "user", "content": f"Сгенерируй описание товара, используя следующие ключевые слова: {keywords}"}
            ]
            response = client.chat.completions.create(
                model="gpt-4o", messages=messages, temperature=0.7, max_tokens=800
            )
            seo_text = response.choices[0].message.content.strip()
            final_response = (
                f"✅ *Готово\\!* \n\n"
                f"Длина текста: {len(seo_text)} символов\\.\n\n"
                f"```\n{seo_text}\n```"
            )
            await update.message.reply_text(final_response, parse_mode='MarkdownV2')
        except Exception as e:
            logger.error(f"Ошибка при генерации SEO-текста: {e}")
            await update.message.reply_text("❌ Произошла ошибка при генерации SEO-текста.")
        return

    if mode == "image":
        # ... (код для генерации изображения не менялся)
        context.user_data["mode"] = "default"
        await update.message.reply_text("🎨 Создаю изображение...", reply_markup=build_keyboard())
        await update.message.chat.send_action(action=ChatAction.UPLOAD_PHOTO)
        try:
            response = client.images.generate(model="dall-e-3", prompt=text, n=1, size="1024x1024", quality="standard")
            await update.message.reply_photo(photo=response.data[0].url, caption="Ваше изображение готово!")
        except Exception as e:
            logger.error(f"Ошибка генерации изображения: {e}")
            await update.message.reply_text("Не удалось создать изображение.")
        return

    # === Логика для режимов чата (должна быть в конце) ===
    history = get_chat_history(chat_id, mode)
    history.append({"role": "user", "content": text})
    system_prompts = {
        "default": "Ты — дружелюбный и полезный ассистент. Используй HTML-теги для форматирования: <b> для жирного, <i> для курсива.",
        "psychologist": "Ты — эмпатичный психолог. Используй HTML-теги для форматирования: <b> для акцентов, <i> для мягких выделений.",
        "astrologer": "Ты — опытный астролог. Используй HTML-теги для форматирования: <b> для важных терминов, <i> для названий."
    }
    system_prompt = system_prompts.get(mode, system_prompts["default"])
    messages = [{"role": "system", "content": system_prompt}] + trim_chat_history(history)
    try:
        await update.message.chat.send_action(action=ChatAction.TYPING)
        response = client.chat.completions.create(model="gpt-4o", messages=messages, temperature=0.7, max_tokens=1500)
        bot_reply = response.choices[0].message.content
        history.append({"role": "assistant", "content": bot_reply})
        await update.message.reply_text(bot_reply, parse_mode='HTML', reply_markup=build_keyboard())
    except Exception as e:
        logger.error(f"Ошибка ответа OpenAI: {e}")
        await update.message.reply_text("Произошла ошибка.")

# === Запуск бота ===
async def main() -> None:
    await ensure_ffmpeg()
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.VOICE, handle_voice))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    try:
        logger.info("Бот запускается...")
        await application.initialize()
        await application.start()
        await application.updater.start_polling()
        logger.info("Бот успешно запущен и готов к работе.")
        while True:
            await asyncio.sleep(3600)
    finally:
        if application.updater and application.updater.running:
            await application.updater.stop()
        if application.running:
            await application.stop()
        await application.shutdown()
        logger.info("Бот успешно остановлен.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Программа прервана пользователем.")
