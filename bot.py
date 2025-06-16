import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, CallbackQueryHandler, filters, Defaults, DictPersistence
)
import openai
from openai import OpenAIError

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

# === История чатов и режимы ===
chat_histories = {}
user_modes = {}  # Хранит режим пользователя: 'default', 'psychologist', 'astrologer'
MAX_HISTORY_PAIRS = 10

def get_chat_history(chat_id, mode):
    key = f"{chat_id}:{mode}"
    return chat_histories.setdefault(key, [])

def trim_chat_history(history):
    return history[-(MAX_HISTORY_PAIRS * 2):] if len(history) > MAX_HISTORY_PAIRS * 2 else history

def build_main_menu():
    keyboard = [
        [InlineKeyboardButton("💬 Психолог", callback_data="mode_psychologist")],
        [InlineKeyboardButton("🔮 Астролог", callback_data="mode_astrologer")],
        [InlineKeyboardButton("🌍 Изображение", callback_data="make_image")]
    ]
    return InlineKeyboardMarkup(keyboard)

def build_back_menu():
    keyboard = [[InlineKeyboardButton("⬅️ Назад в меню", callback_data="main_menu")]]
    return InlineKeyboardMarkup(keyboard)

# === Команды ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "😊 Привет! Я бот с GPT-4o. Выбери режим или напиши что-нибудь.",
        reply_markup=build_main_menu()
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Напиши вопрос или выбери режим.", reply_markup=build_main_menu())

# === Обработчик кнопок ===
async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id

    if query.data == "make_image":
        context.user_data["awaiting_image"] = True
        await query.message.reply_text("🖋 Напиши описание изображения, которое хочешь создать:")
        return

    if query.data == "main_menu":
        user_modes[chat_id] = "default"
        await query.message.reply_text("🔙 Вернулись в главное меню.", reply_markup=build_main_menu())
        return

    if query.data == "mode_psychologist":
        user_modes[chat_id] = "psychologist"
        await query.message.reply_text("🧠 Ты в режиме 'Лучший психолог'. Задай свой вопрос.", reply_markup=build_back_menu())
        return

    if query.data == "mode_astrologer":
        user_modes[chat_id] = "astrologer"
        await query.message.reply_text("🔮 Введи дату рождения в формате ДД.ММ.ГГГГ, я сделаю гороскоп.", reply_markup=build_back_menu())
        return

# === Обработчик сообщений ===
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    text = update.message.text
    mode = user_modes.get(chat_id, "default")

    if context.user_data.get("awaiting_image"):
        context.user_data["awaiting_image"] = False
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
        except Exception as e:
            logging.error(f"Ошибка генерации изображения: {e}")
            await update.message.reply_text("Ошибка генерации изображения.", reply_markup=build_main_menu())
        return

    history = get_chat_history(chat_id, mode)
    history.append({"role": "user", "content": text})
    history = trim_chat_history(history)
    chat_histories[f"{chat_id}:{mode}"] = history

    system_prompt = {
        "default": "Ты умный помощник. Отвечай подробно и точно.",
        "psychologist": "Ты — профессиональный психолог. Отвечай мягко, поддерживающе и глубоко. Помоги человеку разобраться в себе.",
        "astrologer": "Ты — профессиональный астролог с обширными знаниями. Используй астрологические термины, учитывай дату рождения, делай гороскоп и прогнозы."
    }

    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": system_prompt[mode]}] + history,
            temperature=0.7,
            max_tokens=1000
        )
        bot_reply = response.choices[0].message.content
        history.append({"role": "assistant", "content": bot_reply})
        chat_histories[f"{chat_id}:{mode}"] = trim_chat_history(history)

        await update.message.reply_text(bot_reply, reply_markup=build_back_menu() if mode in ["psychologist", "astrologer"] else build_main_menu())
    except Exception as e:
        logging.error(f"Ошибка OpenAI: {e}")
        await update.message.reply_text("Ошибка при обработке запроса.", reply_markup=build_main_menu())

# === Запуск ===
if __name__ == "__main__":
    print("🤖 Бот запускается...")

    defaults = Defaults(parse_mode=None)
    persistence = DictPersistence()

    app = ApplicationBuilder() \
        .token(TELEGRAM_BOT_TOKEN) \
        .defaults(defaults) \
        .persistence(persistence) \
        .build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(handle_button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logging.info("Бот запущен")
    app.run_polling()
