import logging
import requests
import io
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup
from aiogram.dispatcher import FSMContext
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import State, StatesGroup
from supabase import create_client

# --- КОНФИГ ---
API_TOKEN = "8624542988:AAHDzBxDWDZdU6caOnofGqYHW4Ifk2LC5BY"
ADMIN_ID = 6332767725
CHANNEL_ID = "@Luci4DX9"
FILE_URL = "https://github.com/dx9ser777/My_bot/raw/refs/heads/main/cheat_file.zip"

SUPABASE_URL = "https://yuksepnwkzffudhcrjnl.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inl1a3NlcG53a3pmZnVkaGNyam5sIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzUwNDM5OTksImV4cCI6MjA5MDYxOTk5OX0.6IvYWJiWqVeFVkQ-SK1NbG5_yEXVyHijFMGwvMbn1q4"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

class Form(StatesGroup):
    waiting_key = State()

def get_main_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add("🛒 Купить подписку", "🔑 Активировать ключ", "👤 Мой профиль", "🆘 Поддержка")
    return kb

async def is_subscribed(user_id):
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in ['member', 'creator', 'administrator']
    except: return False

@dp.message_handler(commands=["start"])
async def start(message: types.Message):
    if not await is_subscribed(message.from_user.id):
        kb = InlineKeyboardMarkup().add(InlineKeyboardButton("✅ Проверить подписку", callback_data="check_sub"))
        return await message.answer(f"⚠️ Для доступа к DX9 WARE подпишись на канал: {CHANNEL_ID}", reply_markup=kb)
    
    supabase.table("users").upsert({"id": message.from_user.id, "username": message.from_user.username}).execute()
    await message.answer("💜 Добро пожаловать в DX9 WARE!", reply_markup=get_main_kb())

@dp.callback_query_handler(text="check_sub")
async def check_sub_cb(call: types.CallbackQuery):
    if await is_subscribed(call.from_user.id):
        await start(call.message)
    else:
        await call.answer("❌ Вы не подписаны на канал!", show_alert=True)

@dp.message_handler(text="🛒 Купить подписку")
async def shop(message: types.Message):
    text = ("☄️ Flux External 0.38.0\n\n"
            "👑 Dx9 ware поддерживается на Android (Root/NoRoot) и эмуляторах BlueStacks 5 / MSI.\n"
            "💵 Тарифы:\n"
            "7 дней — 4$ / 350🌟\n"
            "30 дней — 8$ / 700🌟\n"
            "Навсегда — 30$ / 2500🌟\n\n"
            "Оплата звёздами: @ware4")
    await message.answer(text)

@dp.message_handler(text="🔑 Активировать ключ")
async def ask_key(message: types.Message):
    await Form.waiting_key.set()
    await message.answer("Введите ваш ключ активации:")

@dp.message_handler(state=Form.waiting_key)
async def process_key(message: types.Message, state: FSMContext):
    key = message.text
    k_data = supabase.table("keys").select("*").eq("key", key).eq("is_used", False).execute().data
    if k_data:
        supabase.table("users").update({"active_until": "Активен", "current_key": key}).eq("id", message.from_user.id).execute()
        supabase.table("keys").update({"is_used": True, "owner_id": message.from_user.id}).eq("key", key).execute()
        await message.answer("✅ Ключ успешно активирован! Теперь вы можете получить файл в профиле.")
    else:
        await message.answer("❌ Неверный или уже использованный ключ.")
    await state.finish()

@dp.message_handler(text="👤 Мой профиль")
async def profile(message: types.Message):
    u = supabase.table("users").select("*").eq("id", message.from_user.id).execute().data
    if not u: return await message.answer("Ошибка: вы не зарегистрированы. Напишите /start")
    user = u[0]
    text = f"👤 ID: `{message.from_user.id}`\n📅 Статус: {user.get('active_until')}\n💰 Баланс: {user.get('balance')} руб."
    kb = InlineKeyboardMarkup().add(InlineKeyboardButton("📥 Получить cheat_file.zip", callback_data="download"))
    await message.answer(text, reply_markup=kb, parse_mode="Markdown")

@dp.callback_query_handler(text="download")
async def download_file(call: types.CallbackQuery):
    user = supabase.table("users").select("active_until").eq("id", call.from_user.id).execute().data[0]
    if user.get("active_until") == "Нет":
        return await call.answer("❌ У вас нет активной подписки!", show_alert=True)
    
    await call.message.answer("⏳ Скачиваю файл...")
    try:
        response = requests.get(FILE_URL)
        if response.status_code == 200:
            file_data = io.BytesIO(response.content)
            file_data.name = 'cheat_file.zip'
            await bot.send_document(call.from_user.id, file_data, caption="✅ Ваш файл DX9 WARE")
        else:
            await call.message.answer("❌ Ошибка соединения с GitHub.")
    except Exception as e:
        await call.message.answer(f"❌ Ошибка: {str(e)}")

@dp.message_handler(text="🆘 Поддержка")
async def support(message: types.Message):
    await message.answer("💬 Поддержка: @ware4\n📣 Наш канал: https://t.me/Luci4DX9")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
