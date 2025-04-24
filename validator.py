
import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder,
    ChatJoinRequestHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# Логи
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = "7891548345:AAGe6bMpEpzZCul2P0OzGIKWfeQ-SvxGG4A"
# ID основной группы (приватной) — где заявки
MAIN_GROUP_ID = -1002190355376
# ID группы модераторов
MOD_GROUP_ID  = -1002551811200

async def on_join_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    req  = update.chat_join_request
    user = req.from_user

    # Сохраняем объект запроса в user_data
    context.user_data["pending"] = req

    # Пишем пользователю в личку
    await user.send_message(
        "Здравствуйте, {0.first_name}!\n"
        "Пожалуйста, отправьте мне фото вашего студенческого билета."
        .format(user)
    )

async def on_private_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Ловим фото только в личных чатах
    if update.effective_chat.type != "private":
        return

    req = context.user_data.get("pending")
    if not req:
        return  # не ждём от этого пользователя фото

    user = req.from_user
    chat = req.chat

    # Берём последнее фото
    file_id = update.message.photo[-1].file_id
    caption = (
        f"Новая заявка:\n"
        f"Пользователь: {user.full_name} (@{user.username or '—'})\n"
        f"ID: {user.id}\n"
        f"Группа: {chat.title}"
    )
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Принять", callback_data=f"ok|{chat.id}|{user.id}"),
        InlineKeyboardButton("❌ Отклонить", callback_data=f"no|{chat.id}|{user.id}")
    ]])

    # Пересылаем модераторам
    await context.bot.send_photo(
        chat_id=MOD_GROUP_ID,
        photo=file_id,
        caption=caption,
        reply_markup=kb
    )
    await update.message.reply_text("Фото отправлено на проверку модераторам.")
    # снимаем ожидание
    context.user_data.pop("pending", None)

async def on_moder_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    data = update.callback_query.data.split("|")
    action, chat_id, user_id = data[0], int(data[1]), int(data[2])

    if action == "ok":
        await context.bot.approve_chat_join_request(chat_id, user_id)
        text = "✅ Заявка одобрена — вы в группе!"
    else:
        await context.bot.decline_chat_join_request(chat_id, user_id)
        text = "❌ Валидация не удалась. Попробуйте ещё раз."

    # Уведомляем пользователя
    try:
        await context.bot.send_message(chat_id=user_id, text=text)
    except:
        logger.warning("Не удалось написать пользователю %s", user_id)

    # Обновляем сообщение у модераторов
    await update.callback_query.edit_message_caption(
        update.callback_query.message.caption + f"\n\n{text}"
    )

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Слушаем события заявок в основную группу
    app.add_handler(ChatJoinRequestHandler(on_join_request, chat_id=MAIN_GROUP_ID))
    # Ловим фото только в ЛС
    app.add_handler(MessageHandler(filters.PHOTO & filters.ChatType.PRIVATE, on_private_photo))
    # Кнопки модераторов
    app.add_handler(CallbackQueryHandler(on_moder_click, pattern="^(ok|no)\|"))

    logger.info("Стартуем валидатор‑бота…")
    app.run_polling()

if __name__ == "__main__":
    main()
