import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, CallbackQueryHandler, filters
)
import openai
from openai import OpenAIError # Импортируем базовый класс ошибок OpenAI

# Ключи из переменных среды
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Проверяем, что ключи API загружены
if not TELEGRAM_BOT_TOKEN:
    logging.error("TELEGRAM_BOT_TOKEN не установлен в переменных среды.")
    exit(1)
if not OPENAI_API_KEY:
    logging.error("OPENAI_API_KEY не установлен в переменных среды.")
    exit(1)

openai.api_key = OPENAI_API_KEY

# Логирование
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# Истории чатов (в памяти, сбросится при перезапуске бота)
chat_histories = {}

# Максимальное количество пар сообщений (пользователь-бот) для хранения в истории
MAX_HISTORY_PAIRS = 10 

def get_chat_history(chat_id):
    """Получает историю чата для данного chat_id, инициализируя её при необходимости."""
    return chat_histories.setdefault(chat_id, [])

def trim_chat_history(history):
    """Обрезает историю чата, оставляя только последние MAX_HISTORY_PAIRS сообщений."""
    # Учитываем, что каждое взаимодействие - это два сообщения (пользователь + бот)
    if len(history) > MAX_HISTORY_PAIRS * 2:
        return history[-(MAX_HISTORY_PAIRS * 2):]
    return history

def build_keyboard():
    """Строит инлайн-клавиатуру для бота."""
    keyboard = [[InlineKeyboardButton("🌍 Сделать изображение", callback_data="make_image")]]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start."""
    logging.info(f"Получена команда /start от пользователя {update.effective_user.id}")
    await update.message.reply_text(
        "😊 Привет! Я бот с GPT-4o. Напиши что-нибудь или нажми кнопку 👇",
        reply_markup=build_keyboard()
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help."""
    logging.info(f"Получена команда /help от пользователя {update.effective_user.id}")
    await update.message.reply_text("Напиши вопрос или нажми кнопку ниже.", reply_markup=build_keyboard())

async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий на инлайн-кнопки."""
    query = update.callback_query
    logging.info(f"Получено нажатие кнопки '{query.data}' от пользователя {query.from_user.id}")
    await query.answer() # Обязательно ответьте на CallbackQuery

    if query.data == "make_image":
        context.user_data["awaiting_image"] = True # Устанавливаем флаг ожидания описания для картинки
        await query.message.reply_text("🖋 Напиши описание, и я сгенерирую картинку!")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений."""
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    text = update.message.text
    logging.info(f"Получено сообщение от пользователя {user_id} в чате {chat_id}: '{text[:50]}...'")

    # Если бот ожидает описание для генерации изображения
    if context.user_data.get("awaiting_image"):
        context.user_data["awaiting_image"] = False # Сбрасываем флаг
        await update.message.reply_text("🎨 Генерирую изображение...")
        logging.info(f"Пользователь {user_id} запросил генерацию изображения: '{text[:50]}'")

        try:
            image_response = openai.images.generate(
                prompt=text,
                model="dall-e-3",
                n=1,
                size="1024x1024"
            )
            image_url = image_response.data[0].url
            await update.message.reply_photo(photo=image_url)
            logging.info(f"Изображение для пользователя {user_id} сгенерировано и отправлено.")
        except OpenAIError as e:
            logging.error(f"Ошибка OpenAI при генерации изображения для пользователя {user_id}: {e}", exc_info=True)
            await update.message.reply_text("Произошла ошибка при генерации изображения. Пожалуйста, попробуйте еще раз позже.", reply_markup=build_keyboard())
        except Exception as e:
            logging.error(f"Неизвестная ошибка при генерации изображения для пользователя {user_id}: {e}", exc_info=True)
            await update.message.reply_text("Произошла непредвиденная ошибка. Пожалуйста, попробуйте еще раз.", reply_markup=build_keyboard())
        return

    # Если это обычное текстовое сообщение для GPT
    history = get_chat_history(chat_id)
    history.append({"role": "user", "content": text})
    
    # Обрезаем историю перед отправкой в OpenAI
    history = trim_chat_history(history)
    chat_histories[chat_id] = history # Обновляем историю в глобальном словаре

    # Формируем сообщения для OpenAI, добавляя системную роль
    messages = [{"role": "system", "content": "Ты умный помощник. Отвечай подробно и точно."}] + history
    logging.info(f"Отправка запроса GPT-4o для пользователя {user_id}. Длина истории: {len(history)} сообщений.")

    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            temperature=0.8,
            max_tokens=1000
        )

        bot_reply = response.choices[0].message.content
        logging.info(f"Получен ответ от GPT-4o для пользователя {user_id}: '{bot_reply[:50]}...'")
        
        history.append({"role": "assistant", "content": bot_reply})
        # Обрезаем историю после добавления ответа бота
        history = trim_chat_history(history)
        chat_histories[chat_id] = history # Обновляем историю в глобальном словаре

        await update.message.reply_text(bot_reply, reply_markup=build_keyboard())

    except OpenAIError as e:
        logging.error(f"Ошибка OpenAI при получении ответа GPT для пользователя {user_id}: {e}", exc_info=True)
        await update.message.reply_text("Произошла ошибка при обработке вашего запроса к GPT. Пожалуйста, попробуйте еще раз позже.", reply_markup=build_keyboard())
    except Exception as e:
        logging.error(f"Неизвестная ошибка при обработке сообщения для пользователя {user_id}: {e}", exc_info=True)
        await update.message.reply_text("Произошла непредвиденная ошибка. Пожалуйста, попробуйте еще раз.", reply_markup=build_keyboard())


# Запуск бота
if __name__ == "__main__":
    # Инициализация ApplicationBuilder с токеном
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # Добавление обработчиков
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(handle_button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🤖 Бот запущен... Ожидание сообщений.")
    logging.info("🤖 Бот запущен... Включен polling.")
    # Запуск бота в режиме polling
    app.run_polling()
