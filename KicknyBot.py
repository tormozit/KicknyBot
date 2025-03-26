# Телеграм бот на языке python для голосования за бан пользователя с возможность отменить голосование и вариантами "Читатель 24ч", "Бан навегда", "Простить".
# Голосование начинается путем ответа на сообщение пользователя с указанием @<ИмяБота>. Если принятое решение не "Простить", то сообщение, ответом на которое начато голосование, удаляется.
# В сообщении о результате голосования должны быть перечислены через запятую все проголосовавшие за принятое решение участники и их количество.
# Каждое упоминание пользователя должно быть обозначено гиперссылкой с текстом его полного имени, обрезанным до 15 символов, и ссылкой на его профиль. Если в тексте гиперссылки есть картинки, то их надо удалить и сократить его до 5 символов.
# Отменить голосование может только инициатор. Пользователю запрещено голосовать в отношении себя.
# Должен иметь команду администратора "VotesLimit" для установки числа голосов для принятия решения. 
# Должен иметь команду администратора "VotesMonoLimit" для установки числа голосов для принятия решения единогласно.
# Должен иметь команду администратора "TimeLimit" для установки максимальной длительности в минутах сбора голосов.
# Должен иметь команду "Help" для вывода справки по командам.
# Получение ключа API сделай из отдельного файла APIKey, чтобы не загружать его на github.
# При нажатии кнопки голосования вставь в начало ее текста символ "+", а у других кнопок удали его.
# Число голосов по каждому варианту отображалось в формате: если нет голосов за другие варианты, то "<Голосов>/<Необходимо голосов единогласно>", иначе "<Голосов>/<Необходимо голосов>".

# https://github.com/tormozit/KicknyBot

from APIKey1 import API_KEY # Example of file content: API_KEY = "722222222:AAE3-2222222222222222222222222222222"
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
    Этот бот позволяет наказывать пользователя временным запретом писать или баном навсегда через голосование с возможностью отмены. Тех. поддержка https://github.com/tormozit/KicknyBot
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
    if initiator_id == target_user.id:
        await update.message.reply_text("Нельзя голосовать против себя.")
        return    
    if await is_admin(chat_id, target_user.id, context):
        await update.message.reply_text("Нельзя голосовать против администратора")
        return
    
    votes_limit = get_votes_limit(chat_id)
    votes_mono_limit = get_votes_mono_limit(chat_id)
    time_limit = get_time_limit(chat_id)
    
    keyboard = [
        [
            InlineKeyboardButton("Читатель 24ч", callback_data=f"vote:day:{target_user.id}"),
            InlineKeyboardButton("Бан навсегда", callback_data=f"vote:forever:{target_user.id}"),
            InlineKeyboardButton("Простить", callback_data=f"vote:forgive:{target_user.id}"),
        ],
        [InlineKeyboardButton("Отменить голосование", callback_data=f"vote:cancel:{target_user.id}")],
    ]
    message = await update.message.reply_text(
        titleText(
            userId=target_user.id,
            fullUserName=target_user.full_name,
            nickname=target_user.username,
            votes_mono_limit=votes_mono_limit,
            votes_limit=votes_limit
        ),
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )
    
    vote_id = (chat_id, message.message_id)
    active_votes[vote_id] = {
        "initiator_id": initiator_id,
        "target_user_id": target_user.id,
        "target_username": target_user.name,
        "target_full_name": target_user.full_name,
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
    
    # context.job_queue.run_once(
    #     end_vote, time_limit, data=vote_id, name=str(vote_id)
    # )
    context.application.job_queue.run_once(  # Используем application.job_queue
        end_vote, time_limit, data=vote_id, name=str(vote_id)
    )
def titleText(userId: int, fullUserName: str, nickname: str, votes_mono_limit: int, votes_limit: int) -> str:
    user_link = create_user_link(
        user_id=userId,
        fullUserName=fullUserName,
        nickname=nickname
    )
    return f"🔨 Голосуем за наказание пользователя {user_link} с лимитом {votes_limit} или единогласно {votes_mono_limit}.\n"

def get_votes_limit(chat_id):
    return chat_settings.get(chat_id, {}).get("votes_limit", 10)

def get_votes_mono_limit(chat_id):
    return chat_settings.get(chat_id, {}).get("votes_mono_limit", 6)

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
        await query.edit_message_text("Голосование остановлено по технической причине.")
        return
    
    user_id = query.from_user.id
    if user_id == target_user_id:
        await query.answer("Нельзя голосовать против себя.")
        return   
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
    
    # Обновляем текст всех кнопок
    keyboard = query.message.reply_markup.inline_keyboard
    new_keyboard = []
    for row in keyboard:
        new_row = []
        for button in row:
            # Убираем "+" из всех кнопок
            button_text = button.text.replace("+ ", "")
            if button.callback_data == query.data:
                # Добавляем "+" к выбранной кнопке
                button_text = f"+ {button_text}"
            new_button = InlineKeyboardButton(button_text, callback_data=button.callback_data)
            new_row.append(new_button)
        new_keyboard.append(new_row)
    
    await query.edit_message_text(
        FullStatus(vote_data, remaining), 
        reply_markup=InlineKeyboardMarkup(new_keyboard), 
        parse_mode="HTML"
    )
    
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
    def format_votes(current, mono_limit, limit, other1, other2):
        if other1 == 0 and other2 == 0:
            return f"{current}/{mono_limit}"
        return f"{current}/{limit}"

    day_text = format_votes(
        vote_data['votes_day'],
        vote_data['votes_mono_limit'],
        vote_data['votes_limit'],
        vote_data['votes_forever'],
        vote_data['votes_forgive']
    )

    forever_text = format_votes(
        vote_data['votes_forever'],
        vote_data['votes_mono_limit'],
        vote_data['votes_limit'],
        vote_data['votes_day'],
        vote_data['votes_forgive']
    )

    forgive_text = format_votes(
        vote_data['votes_forgive'],
        vote_data['votes_mono_limit'],
        vote_data['votes_limit'],
        vote_data['votes_day'],
        vote_data['votes_forever']
    )

    text = (
        titleText(vote_data['target_user_id'], vote_data['target_full_name'], vote_data['target_username'], vote_data['votes_mono_limit'], vote_data['votes_limit']) +
        f"{day_text} за читателя (запрет писать) 24ч\n"
        f"{forever_text} за бан (лишить доступа) навсегда\n"
        f"{forgive_text} за прощение\n"
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
        result_message = "забанен (лишен доступа) навсегда. Восстановить его может администратор в настройках группы"
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
                voters.append(create_user_link(
                    user_id=user_id,
                    fullUserName=user.user.full_name,
                    nickname=user.user.username
                ))
            except Exception as e:
                logger.error(f"Ошибка получения пользователя {user_id}: {e}")
                voters.append(create_user_link(
                    user_id=user_id,
                    fullUserName=f"id{user_id} (не в чате)",
                    nickname=None
                ))

    voters_text = ", ".join(voters)
    userLink = create_user_link(vote_data['target_user_id'], vote_data['target_full_name'], vote_data['target_username'])
    await context.bot.edit_message_text(
        text=(
            f"Пользователь {userLink} {result_message}.\n"
            f"За это голосовали ({len(voters)}): {voters_text}"
        ),
        chat_id=chat_id,
        message_id=message_id,
        parse_mode="HTML"
    )

def create_user_link(user_id: int, fullUserName: str, nickname: str) -> str:
    """Создает HTML-ссылку с адаптивным сокращением имени"""
    # Набор разрешенных символов
    ALLOWED_CHARS = set("_- .")  # Символы, которые не являются буквами/цифрами
    is_valid = lambda c: c.isalnum() or c in ALLOWED_CHARS
    
    # Проверка на наличие спецсимволов/эмодзи
    has_special = any(not is_valid(c) for c in fullUserName)
    
    # Очистка имени с использованием единого условия
    clean_name = "".join([c if is_valid(c) else "" for c in fullUserName]).strip()
    
    # Определение лимита и форматирование имени
    max_len = 5 if has_special else 15
    short_name = f"{clean_name[:max_len]}…" if len(clean_name) > max_len else clean_name
    
    return f'<a href="tg://user?id={user_id}">{short_name or f"id{user_id}"}</a>'

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