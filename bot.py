import logging
import os
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters, Defaults
)
import openai
from openai import OpenAIError

# === Ключи API ===
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

# === Логгирование ===
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# === Истории ===
chat_histories = {
    "default": {},
    "psychologist": {},
    "astrologer": {}
}
MAX_HISTORY_PAIRS = 10

def get_chat_history(chat_id, mode):
    return chat_histories.setdefault(mode, {}).setdefault(chat_id, [])

def trim_chat_history(history):
    return history[-(MAX_HISTORY_PAIRS * 2):]

def build_keyboard(mode="default"):
    if mode == "default":
        return ReplyKeyboardMarkup([
            [KeyboardButton("🌍 Изображение")],
            [KeyboardButton("💬 Психолог")],
            [KeyboardButton("🔮 Астролог")]
        ], resize_keyboard=True)
    else:
        return ReplyKeyboardMarkup([[KeyboardButton("⬅️ Назад")]], resize_keyboard=True)

# === Команды ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["mode"] = "default"
    await update.message.reply_text(
        "😊 Привет! Я бот с GPT-4o. Выбери действие:",
        reply_markup=build_keyboard()
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Напиши вопрос или выбери действие из меню.", reply_markup=build_keyboard())

# === Основной обработчик ===
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text = update.message.text.strip()
    mode = context.user_data.get("mode", "default")

    # Кнопки переключения
    if text == "🌍 Изображение":
        context.user_data["mode"] = "image"
        await update.message.reply_text("🖋 Напиши описание изображения, которое хочешь создать:", reply_markup=build_keyboard("image"))
        return
    if text == "💬 Психолог":
        context.user_data["mode"] = "psychologist"
        await update.message.reply_text("🧠 Я слушаю. Расскажи, что тревожит.", reply_markup=build_keyboard("psychologist"))
        return
    if text == "🔮 Астролог":
        context.user_data["mode"] = "astrologer"
        await update.message.reply_text("🔮 Введи дату рождения, время и город. Я рассчитаю рекомендации.", reply_markup=build_keyboard("astrologer"))
        return
    if text == "⬅️ Назад":
        context.user_data["mode"] = "default"
        await update.message.reply_text("Выбери действие:", reply_markup=build_keyboard("default"))
        return

    # === Генерация изображения ===
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
            await update.message.reply_photo(photo=image_url, reply_markup=build_keyboard())
        except OpenAIError as e:
            logging.error(f"DALL·E Error: {e}")
            await update.message.reply_text("Ошибка генерации изображения.", reply_markup=build_keyboard())
        return

    # === GPT ответ ===
    history = get_chat_history(chat_id, mode)
    history.append({"role": "user", "content": text})
    history = trim_chat_history(history)

    system_prompts = {
        "default": "Ты умный помощник. Отвечай подробно и понятно.",
        "psychologist": "Ты профессиональный психолог. Говори мягко, поддерживающе, как лучший психотерапевт.",
        "astrologer": "Ты экспертный астролог. Отвечай, как астролог-консультант. Применяй астрологические знания."
    }

    messages = [{"role": "system", "content": system_prompts[mode]}] + history

    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            temperature=0.7,
            max_tokens=1000
        )
        reply = response.choices[0].message.content
        history.append({"role": "assistant", "content": reply})
        chat_histories[mode][chat_id] = trim_chat_history(history)
        await update.message.reply_text(reply, reply_markup=build_keyboard(mode="default" if mode == "image" else mode))
    except OpenAIError as e:
        logging.error(f"GPT Error: {e}")
        await update.message.reply_text("Ошибка при обращении к GPT. Попробуй позже.", reply_markup=build_keyboard(mode))

# === Запуск ===
if __name__ == "__main__":
    print("🤖 Бот запускается...")
    defaults = Defaults(parse_mode=None)

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).defaults(defaults).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logging.info("Бот запущен.")
    app.run_polling()
