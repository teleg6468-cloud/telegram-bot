import asyncio
import sqlite3
import time
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart

# ========= НАСТРОЙКИ =========
TOKEN = "8634256633:AAFWLXHYLTR3uXbrBLXYf6ikSJVWyiJaFTE"
ADMIN_ID = 7740472875

bot = Bot(TOKEN)
dp = Dispatcher()

# ========= БАЗА =========
conn = sqlite3.connect("database.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS blacklist (
    user_id INTEGER PRIMARY KEY
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS access (
    user_id INTEGER PRIMARY KEY,
    end_time INTEGER,
    message_id INTEGER
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS stages (
    user_id INTEGER PRIMARY KEY,
    stage TEXT
)
""")

conn.commit()

# ========= СТАТУС =========
async def set_stage(user_id, stage_name):
    cursor.execute(
        "INSERT OR REPLACE INTO stages VALUES (?,?)",
        (user_id, stage_name)
    )
    conn.commit()

    await bot.send_message(
        ADMIN_ID,
        f"👤 Клиент: {user_id}\n📌 Этап: {stage_name}"
    )

# ========= START =========
@dp.message(CommandStart())
async def start(message: types.Message):

    user_id = message.from_user.id

    # Проверка блока
    cursor.execute("SELECT 1 FROM blacklist WHERE user_id=?", (user_id,))
    if cursor.fetchone():
        await message.answer("🚫 Вам ограничили доступ.")
        return

    cursor.execute("INSERT OR IGNORE INTO users VALUES (?)", (user_id,))
    conn.commit()

    await set_stage(user_id, "START")

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➡ Далее", callback_data="next")]
    ])

    await message.answer(
        "👋 Привет!\n\nНажмите «Далее», чтобы продолжить.",
        reply_markup=kb
    )

# ========= CALLBACK =========
@dp.callback_query()
async def callbacks(callback: types.CallbackQuery):

    user_id = callback.from_user.id

    if callback.data == "next":

        await set_stage(user_id, "НАЖАЛ ДАЛЕЕ")

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔑 Получить доступ", callback_data="access")]
        ])

        await callback.message.edit_text(
            "📱 Подготовка завершена.\n\nНажмите кнопку ниже.",
            reply_markup=kb
        )

    elif callback.data == "access":

        await set_stage(user_id, "ЗАПРОСИЛ ДОСТУП")

        await give_access(user_id, 600)

    elif callback.data == "revoke":

        cursor.execute("DELETE FROM access WHERE user_id=?", (user_id,))
        conn.commit()

        await set_stage(user_id, "ДОСТУП ОТОЗВАН")

        await callback.message.edit_text("❌ Доступ отозван")

    elif callback.data == "timer":

        cursor.execute("SELECT end_time FROM access WHERE user_id=?", (user_id,))
        data = cursor.fetchone()

        if data:
            remaining = data[0] - int(time.time())
            m = remaining // 60
            s = remaining % 60
            await callback.answer(f"{m:02}:{s:02}", show_alert=True)

# ========= ТАЙМЕР =========
async def give_access(user_id, seconds):

    end_time = int(time.time()) + seconds

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="❌ Отозвать", callback_data="revoke"),
            InlineKeyboardButton(text="⏰ Таймер", callback_data="timer")
        ]
    ])

    msg = await bot.send_message(
        user_id,
        "🔑 Доступ активирован\n⏳ Осталось: --:--",
        reply_markup=kb
    )

    cursor.execute(
        "INSERT OR REPLACE INTO access VALUES (?,?,?)",
        (user_id, end_time, msg.message_id)
    )
    conn.commit()

    await set_stage(user_id, "ДОСТУП АКТИВЕН")

    asyncio.create_task(update_timer(user_id))

async def update_timer(user_id):

    while True:
        await asyncio.sleep(1)

        cursor.execute("SELECT end_time, message_id FROM access WHERE user_id=?", (user_id,))
        data = cursor.fetchone()

        if not data:
            return

        end_time, message_id = data
        remaining = end_time - int(time.time())

        if remaining <= 0:

            await bot.edit_message_text(
                "❌ Время истекло\nСтатус: Неактивен",
                user_id,
                message_id
            )

            cursor.execute("DELETE FROM access WHERE user_id=?", (user_id,))
            conn.commit()

            await set_stage(user_id, "ВРЕМЯ ИСТЕКЛО")
            return

        m = remaining // 60
        s = remaining % 60

        try:
            await bot.edit_message_text(
                f"🔑 Доступ активен\n⏳ Осталось: {m:02}:{s:02}",
                user_id,
                message_id,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(text="❌ Отозвать", callback_data="revoke"),
                        InlineKeyboardButton(text="⏰ Таймер", callback_data="timer")
                    ]
                ])
            )
        except:
            pass

# ========= АДМИН =========
@dp.message(commands=["admin"])
async def admin_panel(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return

    await message.answer(
        "⚙ Админ панель\n\n"
        "/users\n"
        "/status ID\n"
        "/ban ID\n"
        "/unban ID"
    )

@dp.message(commands=["users"])
async def users_count(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return

    cursor.execute("SELECT COUNT(*) FROM users")
    count = cursor.fetchone()[0]

    await message.answer(f"👤 Пользователей: {count}")

@dp.message(commands=["status"])
async def check_status(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return

    try:
        user_id = int(message.text.split()[1])
        cursor.execute("SELECT stage FROM stages WHERE user_id=?", (user_id,))
        data = cursor.fetchone()

        if data:
            await message.answer(f"📌 Этап пользователя {user_id}:\n{data[0]}")
        else:
            await message.answer("Нет данных.")
    except:
        await message.answer("Используй: /status 123456")

@dp.message(commands=["ban"])
async def ban_user(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return

    try:
        user_id = int(message.text.split()[1])
        cursor.execute("INSERT OR IGNORE INTO blacklist VALUES (?)", (user_id,))
        conn.commit()
        await message.answer("🚫 Пользователь заблокирован")
    except:
        await message.answer("Используй: /ban 123456")

@dp.message(commands=["unban"])
async def unban_user(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return

    try:
        user_id = int(message.text.split()[1])
        cursor.execute("DELETE FROM blacklist WHERE user_id=?", (user_id,))
        conn.commit()
        await message.answer("✅ Пользователь разблокирован")
    except:
        await message.answer("Используй: /unban 123456")

# ========= ЗАПУСК =========
async def main():
    print("Bot started...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())