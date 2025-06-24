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
            "Отправьте мне список ключевых слов для SEO-описания товара."
        )
        return
    if text == "💁‍♀️ Помощница":
        context.user_data["mode"] = "assistant"
        await update.message.reply_text(
            "Пришлите мне отзыв или вопрос клиента для подготовки ответа."
        )
        return
    if text == "🧘‍♀️ Олеся":
        context.user_data["mode"] = "olesya"
        await update.message.reply_text(
            "Переключилась на режим Олеси. Отправьте мне тему или идею для поста, и я напишу текст для канала в ее стиле."
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

    # === Логика для каждого режима ===
    if mode == "olesya":
        context.user_data["mode"] = "default"
        post_topic = text
        await update.message.reply_text("✅ Поняла. Пишу пост от имени Олеси...", reply_markup=build_keyboard())
        await update.message.chat.send_action(action=ChatAction.TYPING)
        try:
            # --- ИЗМЕНЕНИЕ: Уточнена инструкция по использованию тегов ---
            olesya_system_prompt = (
                "Ты — Олеся, 42-летняя женщина, духовный наставник и энергопрактик. "
                "Ты веришь в реинкарнацию, кармические задачи, силу рода и единство всех религий в любви и благодарности. "
                "Твой основной метод — работа с телом, энергиями и тантрой для исцеления психологических и телесных травм, в обход традиционной психологии. "
                "Твой стиль письма — мягкий, мудрый, вдохновляющий и очень личный. Ты обращаешься в основном к женщинам, используя слова 'дорогие', 'любимые', 'прекрасные'. "
                "Твоя задача — написать пост для твоего канала на заданную тему. Пост должен раскрывать пользу работы с телом и энергиями, помогать читательницам принять себя и открыть сердце для любви. "
                "Твоя цель — вдохновить их на развитие через любовь, а не через страх. "
                "Используй абзацы для лучшей читаемости. Для форматирования используй ТОЛЬКО HTML-теги <b> для жирного текста и <i> для курсива. Другие теги, такие как <h1>, использовать запрещено."
            )
            messages = [
                {"role": "system", "content": olesya_system_prompt},
                {"role": "user", "content": f"Напиши, пожалуйста, пост на следующую тему: {post_topic}"}
            ]
            response = client.chat.completions.create(
                model="gpt-4o", messages=messages, temperature=0.8, max_tokens=1500
            )
            post_text = response.choices[0].message.content.strip()
            
            # Улучшенная отправка с обработкой ошибок
            try:
                await update.message.reply_text(post_text, parse_mode='HTML', reply_markup=build_keyboard())
            except telegram.error.BadRequest as e:
                if 'entities' in str(e):
                    logger.warning(f"Ошибка парсинга HTML, отправляю текст без форматирования. Ошибка: {e}")
                    await update.message.reply_text(post_text, reply_markup=build_keyboard())
                else:
                    raise e
                    
        except Exception as e:
            logger.error(f"Ошибка при генерации поста от имени Олеси: {e}")
            await update.message.reply_text("❌ Произошла ошибка при генерации поста.")
        return

    if mode == "assistant":
        # ... (код для этого режима не менялся)
        context.user_data["mode"] = "default"
        customer_feedback = text
        await update.message.reply_text("✅ Готовлю ответ от имени менеджера...", reply_markup=build_keyboard())
        await update.message.chat.send_action(action=ChatAction.TYPING)
        try:
            assistant_system_prompt = (
                "Ты — Евгения Ланцова, менеджер по заботе о клиентах в компании 'Немецкий дом'. "
                "Твоя задача — отвечать на отзывы и вопросы клиентов максимально вежливо, профессионально и понятно. "
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
        # ... (код для этого режима не менялся)
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
        # ... (код для этого режима не менялся)
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

    # === Логика для режимов чата ===
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
