import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, CallbackQueryHandler, filters
)
import openai

# === Проверка переменных среды ===
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not TELEGRAM_BOT_TOKEN or not OPENAI_API_KEY:
    raise ValueError("❌ Установи TELEGRAM_BOT_TOKEN и OPENAI_API_KEY как переменные окружения.")

# === Подключение к OpenAI ===
openai.api_key = OPENAI_API_KEY

# === Логирование ===
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# === История чатов ===
chat_histories = {}

def get_chat_history(chat_id):
    return chat_histories.setdefault(chat_id, [])

def build_keyboard():
    keyboard = [[InlineKeyboardButton("🌍 Сделать изображение", callback_data="make_image")]]
    return InlineKeyboardMarkup(keyboard)

# === Команда /start ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "😊 Привет! Я бот с GPT-4o. Напиши что-нибудь или нажми кнопку 👇",
        reply_markup=build_keyboard()
    )

# === Команда /help ===
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Напиши вопрос или нажми кнопку ниже.")

# === Обработка кнопки ===
async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "make_image":
        context.user_data["awaiting_image"] = True
        await query.message.reply_text("🖋 Напиши описание, и я сгенерирую картинку!")

# === Обработка сообщений ===
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text = update.message.text

    # Генерация изображения
    if context.user_data.get("awaiting_image", False):
        context.user_data["awaiting_image"] = False
        await update.message.reply_text("🎨 Генерирую изображение...")

        try:
            image_response = openai.Image.create(
                prompt=text,
                model="dall-e-3",
                n=1,
                size="1024x1024"
            )
            image_url = image_response['data'][0]['url']
            await update.message.reply_photo(photo=image_url)
        except Exception as e:
            logging.error(f"Ошибка генерации изображения: {e}")
            await update.message.reply_text("❌ Не удалось сгенерировать изображение.")
        return

    # Ответ от GPT-4o
    history = get_chat_history(chat_id)
    history.append({"role": "user", "content": text})
    history[:] = history[-10:]  # ограничиваем длину истории

    messages = [{"role": "system", "content": "Ты умный помощник. Отвечай подробно и точно."}] + history

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o",
            messages=messages,
            temperature=0.8,
            max_tokens=1000
        )
        bot_reply = response["choices"][0]["message"]["content"]
        history.append({"role": "assistant", "content": bot_reply})
        await update.message.reply_text(bot_reply, reply_markup=build_keyboard())
    except Exception as e:
        logging.error(f"Ошибка GPT: {e}")
        await update.message.reply_text("❌ Не удалось получить ответ от GPT.")

# === Запуск ===
if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(handle_button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("🤖 Бот запущен...")
    app.run_polling()
