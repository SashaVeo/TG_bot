import logging
import openai
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (ApplicationBuilder, CommandHandler,
                          ContextTypes, MessageHandler,
                          CallbackQueryHandler, filters)

# === КЛЮЧИ ===
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
openai.api_key = os.getenv("OPENAI_API_KEY")

# История чатов
chat_histories = {}

# Логгирование
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

def get_chat_history(chat_id):
    return chat_histories.setdefault(chat_id, [])

def handle_response(chat_id, text):
    chat_history = get_chat_history(chat_id)
    user_message = {"role": "user", "content": text}
    chat_history.append(user_message)

    messages = [
        {
            "role": "system",
            "content": "Ты — профессиональный ассистент, отвечающий подробно, последовательно и понятно. Не сокращай ответы."
        }
    ] + chat_history

    response = openai.ChatCompletion.create(
        model="gpt-4o",
        messages=messages,
        temperature=0.7,
        max_tokens=1000
    )

    bot_reply = response["choices"][0]["message"]["content"]
    chat_history.append({"role": "assistant", "content": bot_reply})
    return bot_reply

# Стартовая команда с кнопкой
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("🖼 Сделать изображение", callback_data="generate_image")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Привет! Я бот на GPT-4o. Напиши сообщение или выбери опцию 👇",
        reply_markup=reply_markup
    )

# Команда помощи
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Напиши любой вопрос или описание — я помогу! Чтобы создать изображение, нажми кнопку.")

# Обработка нажатия на кнопку
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "generate_image":
        await query.message.reply_text("Опиши, что ты хочешь увидеть. Я создам изображение по твоему описанию ✨")

# Обработка сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_input = update.message.text

    if any(word in user_input.lower() for word in ["нарисуй", "сделай", "создай", "изображение"]):
        try:
            response = openai.Image.create(
                prompt=user_input,
                n=1,
                size="512x512"
            )
            image_url = response["data"][0]["url"]
            await update.message.reply_photo(photo=image_url)
        except Exception as e:
            await update.message.reply_text("Ошибка при создании изображения: " + str(e))
    else:
        reply = handle_response(chat_id, user_input)
        await update.message.reply_text(reply)

# Запуск бота
if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🤖 Бот запущен...")
    app.run_polling()
