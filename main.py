import asyncio
from datetime import datetime, timedelta
import logging
import os
import re
import time
from better_profanity import profanity
from telegram import ChatPermissions, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatType
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from telegram.request import HTTPXRequest

# Безопасное получение токена из переменной окружения
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

profanity.load_censor_words()

# Спам-триггеры для чатов вакансий и найма
EXTRA_FORBIDDEN_WORDS = [
    "заработок", "заработать", "онлайн-доход", "быстрый доход",
    "биткоин", "эфириум", "usdt", "крипта", "сигналы",
    "казино", "онлайн-подработка", "ставки", "легкие деньги",
    "удаленная работа без опыта", "пассивный доход", "раскрутка счета",
]

COOLDOWN = 10
last_message_time = {}

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# ---------- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ----------
def parse_time(time_str: str) -> int:
    """Преобразует '5m', '1h', '1d' в секунды."""
    time_str = time_str.lower().strip()
    if time_str.endswith('s'):
        return int(time_str[:-1])
    elif time_str.endswith('m'):
        return int(time_str[:-1]) * 60
    elif time_str.endswith('h'):
        return int(time_str[:-1]) * 3600
    elif time_str.endswith('d'):
        return int(time_str[:-1]) * 86400
    return int(time_str)

async def is_admin(bot, chat_id: int, user_id: int) -> bool:
    """Проверяет права администратора."""
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status in ('administrator', 'creator')
    except Exception:
        return False

async def get_target_from_reply(update: Update):
    """Извлекает пользователя из ответа."""
    if update.message and update.message.reply_to_message:
        return update.message.reply_to_message.from_user
    return None

async def delete_after_delay(message, delay: int = 5):
    """Фоновое удаление сообщения через N секунд."""
    await asyncio.sleep(delay)
    try:
        await message.delete()
    except Exception:
        pass

# ---------- ОБРАБОТЧИКИ КОМАНД ----------
async def kick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    admin_id = update.effective_user.id

    try:
        await update.message.delete()
    except Exception:
        pass

    if not await is_admin(context.bot, chat_id, admin_id):
        return

    target = await get_target_from_reply(update)
    if not target:
        return

    try:
        await context.bot.ban_chat_member(chat_id, target.id)
        await context.bot.unban_chat_member(chat_id, target.id)
        await context.bot.send_message(
            chat_id=admin_id,
            text=f"✅ Пользователь {target.full_name} успешно кикнут из чата."
        )
    except Exception as e:
        await context.bot.send_message(chat_id=admin_id, text=f"❌ Ошибка кика: {e}")

async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    admin_id = update.effective_user.id

    try:
        await update.message.delete()
    except Exception:
        pass

    if not await is_admin(context.bot, chat_id, admin_id):
        return

    target = await get_target_from_reply(update)
    if not target:
        return

    try:
        await context.bot.ban_chat_member(chat_id, target.id)
        await context.bot.send_message(
            chat_id=admin_id,
            text=f"🚫 Пользователь {target.full_name} забанен навсегда."
        )
    except Exception as e:
        await context.bot.send_message(chat_id=admin_id, text=f"❌ Ошибка бана: {e}")

async def mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    admin_id = update.effective_user.id

    try:
        await update.message.delete()
    except Exception:
        pass

    if not await is_admin(context.bot, chat_id, admin_id):
        return

    if update.effective_chat.type != ChatType.SUPERGROUP:
        return

    target = await get_target_from_reply(update)
    if not target:
        return

    time_arg = ' '.join(context.args) if context.args else '5m'
    try:
        seconds = parse_time(time_arg)
        until_date = datetime.now() + timedelta(seconds=seconds)
    except Exception:
        return

    try:
        await context.bot.restrict_chat_member(
            chat_id=chat_id,
            user_id=target.id,
            permissions=ChatPermissions(can_send_messages=False),
            until_date=until_date,
            use_independent_chat_permissions=True
        )
        await context.bot.send_message(
            chat_id=admin_id,
            text=f"🔇 Пользователь {target.full_name} замучен на {time_arg}."
        )
    except Exception as e:
        await context.bot.send_message(chat_id=admin_id, text=f"❌ Ошибка мута: {e}")

async def unmute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    admin_id = update.effective_user.id

    try:
        await update.message.delete()
    except Exception:
        pass

    if not await is_admin(context.bot, chat_id, admin_id):
        return

    if update.effective_chat.type != ChatType.SUPERGROUP:
        return

    target = await get_target_from_reply(update)
    if not target:
        return

    try:
        await context.bot.restrict_chat_member(
            chat_id=chat_id,
            user_id=target.id,
            permissions=ChatPermissions(
                can_send_messages=True,
                can_send_audios=True,
                can_send_documents=True,
                can_send_photos=True,
                can_send_videos=True,
                can_send_video_notes=True,
                can_send_voice_notes=True,
                can_send_polls=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True
            ),
            use_independent_chat_permissions=True
        )
        await context.bot.send_message(
            chat_id=admin_id,
            text=f"✅ Пользователь {target.full_name} размучен."
        )
    except Exception as e:
        await context.bot.send_message(chat_id=admin_id, text=f"❌ Ошибка размута: {e}")

# ---------- ПАНЕЛЬ МОДЕРАЦИИ В ЛС АДМИНУ ----------
async def mod_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    admin_id = update.effective_user.id

    try:
        await update.message.delete()
    except Exception:
        pass

    if not await is_admin(context.bot, chat_id, admin_id):
        return

    target = await get_target_from_reply(update)
    if not target:
        return

    keyboard = [
        [
            InlineKeyboardButton("🚫 Кикнуть", callback_data=f"kick_{chat_id}_{target.id}"),
            InlineKeyboardButton("⛔ Забанить", callback_data=f"ban_{chat_id}_{target.id}"),
        ],
        [
            InlineKeyboardButton("🔇 Мут 5м", callback_data=f"mute_5m_{chat_id}_{target.id}"),
            InlineKeyboardButton("🔇 Мут 1ч", callback_data=f"mute_1h_{chat_id}_{target.id}"),
            InlineKeyboardButton("🔇 Мут 1д", callback_data=f"mute_1d_{chat_id}_{target.id}"),
        ],
        [
            InlineKeyboardButton("🔊 Размутить", callback_data=f"unmute_{chat_id}_{target.id}"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await context.bot.send_message(
            chat_id=admin_id,
            text=f"👤 Управление пользователем {target.full_name} (ID: {target.id}):",
            reply_markup=reply_markup
        )
    except Exception:
        msg = await update.effective_chat.send_message(
            f"⚠️ <a href='tg://user?id={admin_id}'>Администратор</a>, напишите боту в личные сообщения /start, чтобы получать панель скрытно.",
            parse_mode="HTML"
        )
        asyncio.create_task(delete_after_delay(msg, 7))

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data.split('_')
    action = data[0]

    if action == 'mute':
        time_str = data[1]
        chat_id = int(data[2])
        user_id = int(data[3])
        seconds = parse_time(time_str)
        until_date = datetime.now() + timedelta(seconds=seconds)
    else:
        chat_id = int(data[1])
        user_id = int(data[2])
        time_str, seconds, until_date = None, None, None

    if not await is_admin(context.bot, chat_id, query.from_user.id):
        await query.edit_message_text("❌ У вас нет прав администратора в этой группе.")
        return

    try:
        if action == 'mute':
            await context.bot.restrict_chat_member(
                chat_id=chat_id,
                user_id=user_id,
                permissions=ChatPermissions(can_send_messages=False),
                until_date=until_date,
                use_independent_chat_permissions=True
            )
            await query.edit_message_text(f"🔇 Пользователь замучен на {time_str}.")

        elif action == 'unmute':
            await context.bot.restrict_chat_member(
                chat_id=chat_id,
                user_id=user_id,
                permissions=ChatPermissions(
                    can_send_messages=True,
                    can_send_audios=True,
                    can_send_documents=True,
                    can_send_photos=True,
                    can_send_videos=True,
                    can_send_video_notes=True,
                    can_send_voice_notes=True,
                    can_send_polls=True,
                    can_send_other_messages=True,
                    can_add_web_page_previews=True
                ),
                use_independent_chat_permissions=True
            )
            await query.edit_message_text("✅ Пользователь размучен.")

        elif action == 'kick':
            await context.bot.ban_chat_member(chat_id, user_id)
            await context.bot.unban_chat_member(chat_id, user_id)
            await query.edit_message_text("✅ Пользователь кикнут.")

        elif action == 'ban':
            await context.bot.ban_chat_member(chat_id, user_id)
            await query.edit_message_text("🚫 Пользователь забанен.")
    except Exception as e:
        await query.edit_message_text(f"❌ Ошибка: {e}")

# ---------- ФИЛЬТРАЦИЯ СООБЩЕНИЙ ----------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    user = update.effective_user

    if not message or not user or user.is_bot:
        return

    user_id = user.id
    text = message.text or message.caption or ""

    if await is_admin(context.bot, message.chat_id, user_id):
        return

    # 1. Цензурирование мата через словарь better_profanity
    if text and profanity.contains_profanity(text):
        await message.delete()
        return

    # 2. Фильтрация спам-слов с проверкой границ слов
    if text:
        lower_text = text.lower()
        for word in EXTRA_FORBIDDEN_WORDS:
            if re.search(r'\b' + re.escape(word) + r'\b', lower_text):
                await message.delete()
                return

    # 3. Фильтрация внешних ссылок
    if text:
        url_pattern = re.compile(r"https?://\S+|www\.\S+")
        if url_pattern.search(text):
            await message.delete()
            return

    # 4. Антифлуд (ограничение частоты сообщений)
    current_time = time.time()
    if user_id in last_message_time:
        elapsed = current_time - last_message_time[user_id]
        if elapsed < COOLDOWN:
            await message.delete()
            return

    last_message_time[user_id] = current_time

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        f"Здравствуйте, {user.full_name}!\n"
        f"Бот готов к скрытой модерации. Все команды и панели будут отправляться вам сюда."
    )

def main():
    request = HTTPXRequest(
        connection_pool_size=8,
        connect_timeout=20.0,
        read_timeout=20.0,
        write_timeout=20.0,
        pool_timeout=5.0
    )

    application = Application.builder().token(TOKEN).request(request).build()

    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))
    application.add_handler(CommandHandler("kick", kick))
    application.add_handler(CommandHandler("ban", ban))
    application.add_handler(CommandHandler("mute", mute))
    application.add_handler(CommandHandler("unmute", unmute))
    application.add_handler(CommandHandler("mod", mod_panel))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(CommandHandler("start", start))

    print("Бот запущен...")
    application.run_polling()

if __name__ == "__main__":
    main()
