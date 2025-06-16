import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, CallbackQueryHandler, filters
)
import openai
from telegram.ext import CallbackQueryHandler

app.add_handler(CallbackQueryHandler(handle_button_click))

# Ключи из переменных среды
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = openai.OpenAI(api_key=OPENAI_API_KEY)

# Логгирование
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# Истории чатов
chat_histories = {}

# === Функции ===
def get_chat_history(chat_id):
    return chat_histories.setdefault(chat_id, [])

def build_keyboard():
    keyboard = [[InlineKeyboardButton("🌍 Сделать изображение", callback_data="make_image")]]
    return InlineKeyboardMarkup(keyboard)
    

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "😊 Привет! Я бот с поддержкой GPT-4o. Напиши что-то или выбери кнопку",
        reply_markup=build_keyboard()
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Просто напиши вопрос или нажми на кнопку")

async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "make_image":
        await query.message.reply_text("🖋 Напиши короткое описание, и я сделаю картинку!")
        chat_histories[query.message.chat.id].append({"image_mode": True})

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text = update.message.text
    history = get_chat_history(chat_id)

    if history and isinstance(history[-1], dict) and history[-1].get("image_mode"):
        history.pop()
        image_response = client.images.generate(prompt=text, model="dall-e-3", n=1, size="1024x1024")
        image_url = image_response.data[0].url
        await update.message.reply_photo(photo=image_url)
        return

    # Собираем историю
    history.append({"role": "user", "content": text})
    messages = [{
        "role": "system",
        "content": "Ты полноценный интеллектуальный GPT-4o, даешь подробные ответы, ссылаешься на цепочку диалога."
    }] + history

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        temperature=0.8,
        max_tokens=1000
    )
    bot_reply = response.choices[0].message.content
    history.append({"role": "assistant", "content": bot_reply})
    await update.message.reply_text(bot_reply, reply_markup=build_keyboard())
    async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_input = update.message.text

    # если ждем описание — генерируем изображение
    if context.user_data.get("awaiting_image_description"):
        context.user_data["awaiting_image_description"] = False
        await update.message.reply_text("🎨 Создаю изображение, подожди...")
        
        # вызов DALL·E или image API
        response = openai.Image.create(
            prompt=user_input,
            n=1,
            size="512x512"
        )
        image_url = response['data'][0]['url']
        await update.message.reply_photo(image_url)
        return
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

keyboard = [
    [InlineKeyboardButton("🖼 Сделать изображение", callback_data="generate_image")]
]
reply_markup = InlineKeyboardMarkup(keyboard)

await update.message.reply_text("Выбери действие:", reply_markup=reply_markup)

# === Запуск ===
if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(handle_button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("🤖 Бот запущен...")
    app.run_polling()
