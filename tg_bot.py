import telebot
import json
import os
from telebot import types
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    raise RuntimeError("BOT_TOKEN не найден. Проверь файл .env")

bot = telebot.TeleBot(TOKEN)

FILE = "tasks.json"


# ---------- Работа с файлом ----------
def load_all():
    if not os.path.exists(FILE):
        return {}
    with open(FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_all(data):
    with open(FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_user_tasks(user_id):
    data = load_all()
    return data.get(str(user_id), [])


def save_user_tasks(user_id, tasks):
    data = load_all()
    data[str(user_id)] = tasks
    save_all(data)


# ---------- Клавиатуры ----------
def main_keyboard():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add(
        types.KeyboardButton("➕ Добавить задачу"),
        types.KeyboardButton("📋 Список"),
        types.KeyboardButton("🗑 Очистить всё"),
    )
    return kb


def cancel_keyboard():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(types.KeyboardButton("❌ Отмена"))
    return kb


def tasks_keyboard(tasks):
    kb = types.InlineKeyboardMarkup(row_width=2)
    buttons = []
    for i, task in enumerate(tasks, start=1):
        if not task["done"]:
            buttons.append(types.InlineKeyboardButton(
                text=f"✅ {i}",
                callback_data=f"done:{i}"
            ))
        buttons.append(types.InlineKeyboardButton(
            text=f"❌ {i}",
            callback_data=f"delete:{i}"
        ))
    kb.add(*buttons)
    return kb


# ---------- /start ----------
@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(
        message.chat.id,
        f"Привет, {message.from_user.first_name}! 👋\n\n"
        "Я бот-задачник. Твои задачи видишь только ты 😉\n\n"
        "Нажми «➕ Добавить задачу» — и я спрошу, что записать.\n"
        "Или используй команды:\n"
        "/add текст — добавить задачу\n"
        "/list — показать все задачи\n"
        "/clear — удалить все задачи",
        reply_markup=main_keyboard()
    )


@bot.message_handler(commands=['help'])
def help_command(message):
    start(message)


# ---------- /add (командой) ----------
@bot.message_handler(commands=['add'])
def add_task_cmd(message):
    text = message.text.replace("/add", "", 1).strip()

    if not text:
        # Если написал /add без текста — переходим в диалог
        ask_task_text(message)
        return

    tasks = get_user_tasks(message.from_user.id)
    tasks.append({"text": text, "done": False})
    save_user_tasks(message.from_user.id, tasks)

    bot.send_message(message.chat.id, f"✅ Добавлено: {text}")


# ---------- Диалог: спросить текст задачи ----------
def ask_task_text(message):
    msg = bot.send_message(
        message.chat.id,
        "✏️ Что добавить? Напиши текст задачи одним сообщением.\n"
        "Или нажми «❌ Отмена».",
        reply_markup=cancel_keyboard()
    )
    bot.register_next_step_handler(msg, save_new_task)


# ---------- Диалог: получить текст и сохранить ----------
def save_new_task(message):
    # Если пользователь отменил
    if message.text == "❌ Отмена":
        bot.send_message(
            message.chat.id,
            "Отменено 👌",
            reply_markup=main_keyboard()
        )
        return

    # Пустое сообщение — маловероятно, но проверим
    if not message.text or not message.text.strip():
        bot.send_message(message.chat.id, "⚠️ Пустая задача. Попробуй ещё раз.")
        ask_task_text(message)
        return

    text = message.text.strip()

    tasks = get_user_tasks(message.from_user.id)
    tasks.append({"text": text, "done": False})
    save_user_tasks(message.from_user.id, tasks)

    bot.send_message(
        message.chat.id,
        f"✅ Добавлено: {text}",
        reply_markup=main_keyboard()
    )


# ---------- /list ----------
@bot.message_handler(commands=['list'])
def list_tasks(message):
    tasks = get_user_tasks(message.from_user.id)

    if not tasks:
        bot.send_message(message.chat.id, "📭 Список пуст. Добавь задачу: /add ...")
        return

    lines = ["📋 Твои задачи:\n"]
    for i, task in enumerate(tasks, start=1):
        mark = "✅" if task["done"] else "⬜"
        lines.append(f"{i}. {mark} {task['text']}")

    bot.send_message(
        message.chat.id,
        "\n".join(lines),
        reply_markup=tasks_keyboard(tasks)
    )


# ---------- /clear ----------
@bot.message_handler(commands=['clear'])
def clear_tasks(message):
    save_user_tasks(message.from_user.id, [])
    bot.send_message(message.chat.id, "🗑 Все твои задачи удалены.")


# ---------- Inline-кнопки ----------
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    action, num_str = call.data.split(":")
    num = int(num_str)

    user_id = call.from_user.id
    tasks = get_user_tasks(user_id)

    if num < 1 or num > len(tasks):
        bot.answer_callback_query(call.id, "⚠️ Задача не найдена")
        return

    task = tasks[num - 1]

    if action == "done":
        if task["done"]:
            bot.answer_callback_query(call.id, "Уже выполнена ✅")
            return
        task["done"] = True
        save_user_tasks(user_id, tasks)
        bot.answer_callback_query(call.id, f"✅ {task['text']}")

    elif action == "delete":
        tasks.pop(num - 1)
        save_user_tasks(user_id, tasks)
        bot.answer_callback_query(call.id, f"❌ Удалено: {task['text']}")

    tasks = get_user_tasks(user_id)

    if not tasks:
        bot.edit_message_text(
            "📭 Список пуст. Добавь задачу: /add ...",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id
        )
        return

    lines = ["📋 Твои задачи:\n"]
    for i, t in enumerate(tasks, start=1):
        mark = "✅" if t["done"] else "⬜"
        lines.append(f"{i}. {mark} {t['text']}")

    bot.edit_message_text(
        "\n".join(lines),
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=tasks_keyboard(tasks)
    )


# ---------- Reply-кнопки и обычный текст ----------
@bot.message_handler(content_types=['text'])
def handle_text(message):
    text = message.text

    if text == "➕ Добавить задачу":
        ask_task_text(message)
    elif text == "📋 Список":
        list_tasks(message)
    elif text == "🗑 Очистить всё":
        clear_tasks(message)
    else:
        bot.send_message(
            message.chat.id,
            "Не понимаю 🤔 Нажми «➕ Добавить задачу» или используй /list",
            reply_markup=main_keyboard()
        )


print("Бот с диалоговым режимом запущен...")
bot.polling(none_stop=True)