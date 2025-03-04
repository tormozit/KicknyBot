# Телеграм бот на языке python для голосования за бан пользователя с возможность отменить голосование и вариантами "Читатель на 24ч", "Бан навегда", "Простить".
# Голосование начинается путем ответа на сообщение пользователя с указанием @<ИмяБота>. Если принятое решение не "Простить", то сообщение, ответом на которое начато голосование, удаляется.
# В сообщении о результате голосования должны быть перечислены все проголосовавшие за принятое решение и их количество.
# Отменить голосование может только инициатор. Пользователю запрещено голосовать в отношении себя.
# Должен иметь команду администратора "VotesLimit" для установки числа голосов для принятия решения. 
# Должен иметь команду администратора "VotesMonoLimit" для установки числа голосов для принятия решения единогласно.
# Должен иметь команду администратора "TimeLimit" для установки максимальной длительности в минутах сбора голосов.
# Должен иметь команду "Help" для вывода справки по командам.
# Получение ключа API сделай из отдельного файла APIKey, чтобы не загружать его на github.

from APIKey1 import API_KEY
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatPermissions
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    CallbackContext,
    JobQueue,
    filters,
    MessageHandler,
)
from datetime import datetime, timedelta
import logging

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Хранение данных
active_votes = {}
chat_settings = {}

async def is_admin(chat_id: int, user_id: int, context: CallbackContext) -> bool:
    try:
        admins = await context.bot.get_chat_administrators(chat_id)
        return any(admin.user.id == user_id for admin in admins)
    except Exception as e:
        logger.error(f"Ошибка проверки администратора: {e}")
        return False

async def help_command(update: Update, context: CallbackContext) -> None:
    help_text = f"""
    Этот бот позволяет наказывать пользователя временным запретом писать или баном навсегда через голосование с возможностью отмены.
    Список команд:
    Ответьте на сообщение пользователя строкой @{context.bot.username} для начала голосования за его наказание
    /VotesLimit [количество] - Установить необходимое число голосов (только админы) = {get_votes_limit(update.effective_chat.id)}
    /VotesMonoLimit [количество] - Установить необходимое число голосов единогласно, т.е. при отсутствии голосов за другие варианты (только админы) = {get_votes_mono_limit(update.effective_chat.id)}
    /TimeLimit [минуты] - Установить время голосования (только админы) = {get_time_limit(update.effective_chat.id)/60}
    /help - Показать эту справку
    """
    await update.message.reply_text(help_text)

async def set_votes_limit(update: Update, context: CallbackContext) -> None:
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    if not await is_admin(chat_id, user_id, context):
        await update.message.reply_text("❌ Команда доступна только администраторам")
        return
    
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("⚠ Использование: /VotesLimit [число]")
        return
    
    votes_limit = int(context.args[0])
    chat_settings.setdefault(chat_id, {})["votes_limit"] = votes_limit
    await update.message.reply_text(f"✅ Лимит голосов установлен: {votes_limit}")

async def set_votes_mono_limit(update: Update, context: CallbackContext) -> None:
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    if not await is_admin(chat_id, user_id, context):
        await update.message.reply_text("❌ Команда доступна только администраторам")
        return
    
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("⚠ Использование: /VotesMonoLimit [число]")
        return
    
    votes_mono_limit = int(context.args[0])
    chat_settings.setdefault(chat_id, {})["votes_mono_limit"] = votes_mono_limit
    await update.message.reply_text(f"✅ Лимит единогласно голосов установлен: {votes_mono_limit}")

async def set_time_limit(update: Update, context: CallbackContext) -> None:
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    if not await is_admin(chat_id, user_id, context):
        await update.message.reply_text("❌ Команда доступна только администраторам")
        return
    
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("⚠ Использование: /TimeLimit [минуты]")
        return
    
    minutes = int(context.args[0])
    time_limit = minutes * 60
    chat_settings.setdefault(chat_id, {})["time_limit"] = time_limit
    await update.message.reply_text(f"✅ Время голосования установлено: {minutes} мин")

async def start_vote(update: Update, context: CallbackContext) -> None:
    if not update.message.reply_to_message:
        return       
    bot_username = context.bot.username.lower()
    mentioned = any(
        entity.type == "mention" 
        and update.message.text[entity.offset:entity.offset+entity.length].lower() == f"@{bot_username}"
        for entity in update.message.entities or []
    )
    if not mentioned:
        return
    target_user = update.message.reply_to_message.from_user
    chat_id = update.effective_chat.id
    initiator_id = update.effective_user.id
    
    if await is_admin(chat_id, target_user.id, context):
        await update.message.reply_text("Нельзя голосовать против администратора")
        return
    
    votes_limit = get_votes_limit(chat_id)
    votes_mono_limit = get_votes_mono_limit(chat_id)
    time_limit = get_time_limit(chat_id)
    
    keyboard = [
        [
            InlineKeyboardButton("⏳ Читатель 24ч", callback_data=f"vote:day:{target_user.id}"),
            InlineKeyboardButton("♾️ Бан навсегда", callback_data=f"vote:forever:{target_user.id}"),
            InlineKeyboardButton("Простить", callback_data=f"vote:forgive:{target_user.id}"),
        ],
        [InlineKeyboardButton("Отменить", callback_data=f"vote:cancel:{target_user.id}")],
    ]
    message = await update.message.reply_text(
        f"🔨 Начато голосование за наказание пользователя {target_user.name}\n"
        f"Необходимо голосов: {votes_limit} или единогласно {votes_mono_limit}\n",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    
    vote_id = (chat_id, message.message_id)
    active_votes[vote_id] = {
        "initiator_id": initiator_id,
        "target_user_id": target_user.id,
        "target_username": target_user.name,
        "votes_day": 0,
        "votes_forever": 0,
        "votes_forgive": 0,
        "voters": {},
        "start_time": datetime.now(),
        "votes_limit": votes_limit,
        "votes_mono_limit": votes_mono_limit,
        "time_limit": time_limit,
        "original_message_id": update.message.reply_to_message.message_id,  # Сохраняем ID исходного сообщения
    }
    
    context.job_queue.run_once(
        end_vote, time_limit, data=vote_id, name=str(vote_id)
    )

def get_votes_limit(chat_id):
    return chat_settings.get(chat_id, {}).get("votes_limit", 15)

def get_votes_mono_limit(chat_id):
    return chat_settings.get(chat_id, {}).get("votes_mono_limit", 10)

def get_time_limit(chat_id):
    return chat_settings.get(chat_id, {}).get("time_limit", 3600)

async def handle_vote(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()
    
    data = query.data.split(":")
    if len(data) != 3 or data[0] != "vote":
        return
    
    action, target_user_id = data[1], int(data[2])
    vote_id = (query.message.chat_id, query.message.message_id)
    vote_data = active_votes.get(vote_id)
    
    if not vote_data or vote_data["target_user_id"] != target_user_id:
        await query.edit_message_text("Голосование завершено")
        return
    
    user_id = query.from_user.id
    
    if action == "cancel":
        if user_id != vote_data["initiator_id"]:
            await query.answer("Только инициатор может отменить")
            return
        
        for job in context.job_queue.get_jobs_by_name(str(vote_id)):
            job.schedule_removal()
        del active_votes[vote_id]
        await query.edit_message_text(f"Голосование отменено")
        return
    
    current_vote = vote_data["voters"].get(user_id)
    if current_vote == action:
        await query.answer("Вы уже проголосовали")
        return
    
    if current_vote:
        vote_data[f"votes_{current_vote}"] -= 1
    
    vote_data["voters"][user_id] = action
    vote_data[f"votes_{action}"] += 1
    
    remaining = (vote_data["time_limit"] - (datetime.now() - vote_data["start_time"]).total_seconds()) // 60
    
    text = FullStatus(vote_data, remaining)
    await query.edit_message_text(text, reply_markup=query.message.reply_markup)
    if (False
        or vote_data["votes_day"] == vote_data["votes_limit"] 
        or vote_data["votes_day"] == vote_data["votes_mono_limit"] and vote_data["votes_forever"] == 0 and vote_data["votes_forgive"] == 0):
        result = "day"
    elif (False
        or vote_data["votes_forever"] == vote_data["votes_limit"] 
        or vote_data["votes_forever"] == vote_data["votes_mono_limit"] and vote_data["votes_day"] == 0 and vote_data["votes_forgive"] == 0):
        result = "forever"
    elif (False
        or vote_data["votes_forgive"] == vote_data["votes_limit"] 
        or vote_data["votes_forgive"] == vote_data["votes_mono_limit"] and vote_data["votes_day"] == 0 and vote_data["votes_forever"] == 0):
        result = 'forgive'
    else:
        result = None
    if result:
        vote_data["result"] = result
        for job in context.job_queue.get_jobs_by_name(str(vote_id)):
            job.schedule_removal()
        await end_vote(context, vote_id)

def FullStatus(vote_data, remaining):
    text = (
        f"🔨 Голосование за наказание {vote_data['target_username']}\n"
        f"{vote_data['votes_day']} за читателя (запрет писать) 24ч\n"
        f"{vote_data['votes_forever']} за бан (лишить доступа) навсегда\n"
        f"{vote_data['votes_forgive']} за прощение\n"
        f"Необходимо голосов: {vote_data['votes_limit']} или единогласно {vote_data['votes_mono_limit']}\n"
        f"Осталось: {int(remaining)} мин"
    )
    return text

async def end_vote(context: CallbackContext, vote_id: tuple) -> None:
    vote_data = active_votes.pop(vote_id, None)
    if not vote_data:
        return
    chat_id, message_id = vote_id
    result = vote_data["result"]
    result_message = ""
    if result == 'forgive':
        result_message = "прощен"
    elif result == 'forever':
        await context.bot.ban_chat_member(chat_id, vote_data["target_user_id"])
        result_message = "забанен (лишен доступа) навсегда"
        try:
            await context.bot.delete_message(chat_id, vote_data["original_message_id"])
        except Exception as e:
            logger.error(f"Ошибка удаления сообщения: {e}")
    else:
        until = datetime.now() + timedelta(days=1)
        result_message = "теперь читатель (запрещено писать) на 24ч"
        await context.bot.restrict_chat_member(
            chat_id=chat_id,
            user_id=vote_data["target_user_id"],
            permissions=ChatPermissions(
                can_send_messages=False,  # Запрет на отправку сообщений
            ),
            until_date=until
        )
        try:
            await context.bot.delete_message(chat_id, vote_data["original_message_id"])
        except Exception as e:
            logger.error(f"Ошибка удаления сообщения: {e}")

    voters = []
    for user_id, vote_type in vote_data["voters"].items():
        if vote_type == result:
            try:
                user = await context.bot.get_chat_member(chat_id, user_id)
                voters.append("@"+user.user.username)
            except Exception as e:
                logger.error(f"Ошибка получения пользователя {user_id}: {e}")
                voters.append(f"id{user_id}")
    voters_text = f"Проголосовали({len(voters)}): " + ", ".join(voters)
    await context.bot.edit_message_text(
        f"Пользователь {vote_data['target_username']} {result_message}. " + voters_text,
        chat_id=chat_id,
        message_id=message_id,
    )

def main() -> None:
    application = ApplicationBuilder().token(API_KEY).build()
    
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("VotesLimit", set_votes_limit))
    application.add_handler(CommandHandler("VotesMonoLimit", set_votes_mono_limit))
    application.add_handler(CommandHandler("TimeLimit", set_time_limit))
    application.add_handler(
        MessageHandler(
            filters.ChatType.GROUPS 
            & filters.REPLY 
            & filters.Entity("mention"),
            start_vote
            )
    )
    application.add_handler(CallbackQueryHandler(handle_vote))
    application.run_polling()

if __name__ == "__main__":
    main()