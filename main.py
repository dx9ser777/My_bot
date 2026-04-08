import logging
import random
import string
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.dispatcher import FSMContext
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import State, StatesGroup
from supabase import create_client

# --- КОНФИГ ---
API_TOKEN = "8624542988:AAHDzBxDWDZdU6caOnofGqYHW4Ifk2LC5BY"
CHANNEL_ID = "@Luci4DX9"
ADMIN_ID = 6332767725

# ... (инициализация бота и Supabase как в твоем коде)

class Form(StatesGroup):
    input_key = State()

# --- ПРОВЕРКА ПОДПИСКИ ---
async def check_sub(user_id):
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in ['member', 'creator', 'administrator']
    except:
        return False

# --- ХЕНДЛЕРЫ ---

@dp.message_handler(commands=["start"])
async def cmd_start(message: types.Message):
    # Проверка подписки
    if not await check_sub(message.from_user.id):
        markup = InlineKeyboardMarkup().add(InlineKeyboardButton("✅ Проверить подписку", callback_data="check_sub"))
        return await message.answer(f"❌ Чтобы пользоваться ботом, подпишись на канал: {CHANNEL_ID}", reply_markup=markup)

    # Регистрация юзера
    supabase.table("users").upsert({"id": message.from_user.id, "username": message.from_user.username}).execute()
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True).add("🛒 Купить подписку", "🔑 Активировать ключ", "👤 Мой профиль", "🆘 Поддержка")
    await message.answer("💜 Добро пожаловать в DX9 WARE!\nВыберите действие:", reply_markup=markup)

@dp.callback_query_handler(text="check_sub")
async def check_sub_cb(call: types.CallbackQuery):
    if await check_sub(call.from_user.id):
        await cmd_start(call.message)
    else:
        await call.answer("Вы еще не подписались!", show_alert=True)

@dp.message_handler(text="🛒 Купить подписку")
async def shop(message: types.Message):
    text = """☄️ Flux External 0.38.0
Ознакомиться с функционалом: https://t.me/Luci4DX9

👑 Поддержка: Android (Root/NoRoot), BlueStacks 5/MSI.

💵 Выберите тариф:
• 7 дней - 4$ / 350🌟
• 30 дней - 8$ / 700🌟
• Навсегда - 30$ / 2500🌟

Оплата звёздами: @ware4"""
    markup = InlineKeyboardMarkup(row_width=1).add(
        InlineKeyboardButton("7 дней (4$)", callback_data="buy_7"),
        InlineKeyboardButton("30 дней (8$)", callback_data="buy_30"),
        InlineKeyboardButton("Навсегда (30$)", callback_data="buy_life")
    )
    await message.answer(text, reply_markup=markup)

@dp.message_handler(text="👤 Мой профиль")
async def profile(message: types.Message):
    data = supabase.table("users").select("*").eq("id", message.from_user.id).execute().data[0]
    sub = data.get("active_until", "Нет")
    bal = data.get("balance", 0)
    text = f"👤 ID: `{message.from_user.id}`\n📅 Подписка до: `{sub}`\n💰 Реф. баланс: {bal} руб."
    
    markup = InlineKeyboardMarkup()
    if data.get("active_until"):
        markup.add(InlineKeyboardButton("📥 Скачать cheat_file.zip", callback_data="download"))
    
    await message.answer(text, reply_markup=markup, parse_mode="Markdown")

@dp.message_handler(text="🔑 Активировать ключ")
async def activate_key(message: types.Message):
    await Form.input_key.set()
    await message.answer("Введите ключ:")

@dp.message_handler(state=Form.input_key)
async def process_key(message: types.Message, state: FSMContext):
    key_data = supabase.table("keys").select("*").eq("key", message.text).eq("is_used", False).execute().data
    if key_data:
        # Активация
        days = key_data[0]['days']
        # Логика расчета даты... (добавление к текущей дате)
        supabase.table("users").update({"active_until": "активен"}).eq("id", message.from_user.id).execute()
        supabase.table("keys").update({"is_used": True}).eq("key", message.text).execute()
        await message.answer("✅ Ключ успешно активирован!")
    else:
        await message.answer("❌ Неверный или использованный ключ.")
    await state.finish()

@dp.message_handler(text="🆘 Поддержка")
async def support(message: types.Message):
    await message.answer("Наш канал: https://t.me/Luci4DX9\nПоддержка: @ware4")

# --- АДМИНКА ---
@dp.message_handler(commands=["admin"])
async def admin_panel(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    markup = InlineKeyboardMarkup().add(
        InlineKeyboardButton("🔑 Список ключей", callback_data="adm_keys"),
        InlineKeyboardButton("📊 Статистика", callback_data="adm_stats")
    )
    await message.answer("Админ-панель DX9 WARE", reply_markup=markup)

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
