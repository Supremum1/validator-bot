import os
import logging
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder,
    ChatJoinRequestHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
MAIN_GROUP_ID = os.getenv("MAIN_GROUP_ID")
MOD_GROUP_ID = os.getenv("MOD_GROUP_ID")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is missing. Add it to environment variables.")

if not MAIN_GROUP_ID:
    raise RuntimeError("MAIN_GROUP_ID is missing. Add it to environment variables.")

if not MOD_GROUP_ID:
    raise RuntimeError("MOD_GROUP_ID is missing. Add it to environment variables.")

MAIN_GROUP_ID = int(MAIN_GROUP_ID)
MOD_GROUP_ID = int(MOD_GROUP_ID)


async def on_join_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    req = update.chat_join_request
    user = req.from_user

    context.user_data["pending"] = req

    await user.send_message(
        "Здравствуйте, {0.first_name}!\n"
        "Пожалуйста, отправьте мне фото вашего студенческого билета."
        .format(user)
    )


async def on_private_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        return

    req = context.user_data.get("pending")
    if not req:
        return

    user = req.from_user
    chat = req.chat

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

    await context.bot.send_photo(
        chat_id=MOD_GROUP_ID,
        photo=file_id,
        caption=caption,
        reply_markup=kb
    )

    await update.message.reply_text("Фото отправлено на проверку модераторам.")
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

    try:
        await context.bot.send_message(chat_id=user_id, text=text)
    except Exception:
        logger.warning("Не удалось написать пользователю %s", user_id)

    await update.callback_query.edit_message_caption(
        update.callback_query.message.caption + f"\n\n{text}"
    )


def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(ChatJoinRequestHandler(on_join_request, chat_id=MAIN_GROUP_ID))
    app.add_handler(MessageHandler(filters.PHOTO & filters.ChatType.PRIVATE, on_private_photo))
    app.add_handler(CallbackQueryHandler(on_moder_click, pattern=r"^(ok|no)\|"))

    logger.info("Стартуем валидатор-бота…")
    app.run_polling()


if __name__ == "__main__":
    main()