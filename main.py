import logging
import asyncio
import random
import string
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup
from aiogram.dispatcher import FSMContext
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import State, StatesGroup
from supabase import create_client, Client

# --- КОНФИГ ---
API_TOKEN = '8624542988:AAHDzBxDWDZdU6caOnofGqYHW4Ifk2LC5BY'
ADMIN_ID = 6332767725 
SUPABASE_URL = "https://yuksepnwkzffudhcrjnl.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inl1a3NlcG53a3pmZnVkaGNyam5sIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzUwNDM5OTksImV4cCI6MjA5MDYxOTk5OX0.6IvYWJiWqVeFVkQ-SK1NbG5_yEXVyHijFMGwvMbn1q4"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Состояния
class AdminGen(StatesGroup):
    count = State()
    days = State()
    limit = State()
    prefix = State()

class AdminEdit(StatesGroup):
    key_select = State()
    new_val = State()

class UserAct(StatesGroup):
    waiting_key = State()

# --- КЛАВИАТУРЫ ---
def get_main_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("👤 Профиль", "🛒 Товары", "🔑 Активировать")
    return markup

def get_cancel_kb():
    return ReplyKeyboardMarkup(resize_keyboard=True).add("❌ Отмена")

# --- АДМИН: ПОШАГОВАЯ ГЕНЕРАЦИЯ ---

@dp.message_handler(commands=['gen'], state='*')
async def admin_gen_start(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    await AdminGen.count.set()
    await message.answer("🔢 **Шаг 1:** Сколько ключей создать?", reply_markup=get_cancel_kb())

@dp.message_handler(state=AdminGen.count)
async def gen_step_1(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена": return await state.finish()
    if not message.text.isdigit(): return await message.answer("Введи число!")
    await state.update_data(c=int(message.text))
    await AdminGen.days.set()
    await message.answer("📅 **Шаг 2:** На сколько дней каждый ключ?")

@dp.message_handler(state=AdminGen.days)
async def gen_step_2(message: types.Message, state: FSMContext):
    if not message.text.isdigit(): return await message.answer("Введи число!")
    await state.update_data(d=int(message.text))
    await AdminGen.limit.set()
    await message.answer("👥 **Шаг 3:** Сколько человек могут активировать 1 ключ?")

@dp.message_handler(state=AdminGen.limit)
async def gen_step_3(message: types.Message, state: FSMContext):
    if not message.text.isdigit(): return await message.answer("Введи число!")
    await state.update_data(l=int(message.text))
    await AdminGen.prefix.set()
    await message.answer("🏷 **Шаг 4:** Введи префикс ключа (например, DX9):")

@dp.message_handler(state=AdminGen.prefix)
async def gen_step_4(message: types.Message, state: FSMContext):
    data = await state.get_data()
    pref = message.text.strip()
    keys_list = []
    
    for _ in range(data['c']):
        random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        full_key = f"{pref}-{random_str}"
        supabase.table("keys").insert({
            "key": full_key, "days": data['d'], "max_uses": data['l'], 
            "current_uses": 0, "is_active": True
        }).execute()
        keys_list.append(f"`{full_key}`")
    
    await message.answer(f"✅ Создано {data['c']} ключей!\n\n" + "\n".join(keys_list), 
                         parse_mode="Markdown", reply_markup=get_main_menu())
    await state.finish()

# --- АДМИН: РЕДАКТИРОВАНИЕ ---

@dp.message_handler(commands=['editkey'], state='*')
async def edit_key(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    key_to_edit = message.get_args().strip()
    if not key_to_edit: return await message.answer("Пиши: `/editkey КЛЮЧ`")
    
    res = supabase.table("keys").select("*").eq("key", key_to_edit).execute()
    if not res.data: return await message.answer("❌ Ключ не найден.")
    
    await state.update_data(editing=key_to_edit)
    await AdminEdit.key_select.set()
    
    kb = InlineKeyboardMarkup().add(
        InlineKeyboardButton("Изменить дни", callback_data="set_days"),
        InlineKeyboardButton("Изменить лимит", callback_data="set_limit")
    )
    await message.answer(f"🛠 Редактируем `{key_to_edit}`. Что меняем?", reply_markup=kb, parse_mode="Markdown")

@dp.callback_query_handler(state=AdminEdit.key_select)
async def edit_choice(call: types.CallbackQuery, state: FSMContext):
    await state.update_data(mode=call.data)
    await AdminEdit.new_val.set()
    await call.message.answer("Введи новое числовое значение:")

@dp.message_handler(state=AdminEdit.new_val)
async def edit_save(message: types.Message, state: FSMContext):
    if not message.text.isdigit(): return await message.answer("Введи число!")
    data = await state.get_data()
    col = "days" if data['mode'] == "set_days" else "max_uses"
    
    supabase.table("keys").update({col: int(message.text)}).eq("key", data['editing']).execute()
    await message.answer(f"✅ Обновлено! {col} теперь {message.text}", reply_markup=get_main_menu())
    await state.finish()

# --- ЮЗЕР: ПРОФИЛЬ И АКТИВАЦИЯ ---

@dp.message_handler(lambda m: m.text == "👤 Профиль", state='*')
async def user_profile(message: types.Message):
    res = supabase.table("users").select("*").eq("id", message.from_user.id).execute()
    if not res.data:
        supabase.table("users").upsert({"id": message.from_user.id, "username": message.from_user.username}).execute()
        return await message.answer("Профиль создан. Нажми еще раз.")
    
    u = res.data[0]
    status = "Активен ✅" if u.get('is_verified') else "Нет доступа ❌"
    await message.answer(f"👤 **Профиль**\nID: `{message.from_user.id}`\nСтатус лоадера: {status}\nИстекает: `{u.get('expiry_date', '—')}`", parse_mode="Markdown")

@dp.message_handler(lambda m: m.text == "🔑 Активировать", state='*')
async def act_start(message: types.Message):
    await UserAct.waiting_key.set()
    await message.answer("🔑 Введи свой ключ:", reply_markup=get_cancel_kb())

@dp.message_handler(state=UserAct.waiting_key)
async def act_process(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена": 
        await state.finish()
        return await message.answer("Отменено.", reply_markup=get_main_menu())
        
    key_text = message.text.strip()
    res = supabase.table("keys").select("*").eq("key", key_text).eq("is_active", True).execute()
    
    if res.data:
        k = res.data[0]
        if k['current_uses'] < k['max_uses']:
            new_uses = k['current_uses'] + 1
            exp = (datetime.now() + timedelta(days=k['days'])).strftime("%Y-%m-%d")
            
            # Обновляем ключ и юзера
            supabase.table("keys").update({"current_uses": new_uses, "used_by": message.from_user.id}).eq("key", key_text).execute()
            supabase.table("users").update({"is_verified": True, "expiry_date": exp}).eq("id", message.from_user.id).execute()
            
            await message.answer(f"✅ Успех! Доступ в лоадер до {exp}", reply_markup=get_main_menu())
        else:
            await message.answer("❌ Лимит активаций ключа исчерпан.")
    else:
        await message.answer("❌ Неверный или замороженный ключ.")
    await state.finish()

# --- СЛУЖЕБНОЕ ---

@dp.message_handler(commands=['cmd'])
async def cmd_list(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    text = (
        "📜 **Команды админа:**\n"
        "🔹 `/gen` — Пошаговая генерация\n"
        "🔹 `/editkey [ключ]` — Настройка ключа\n"
        "🔹 `/akey` — Все ключи\n"
        "🔹 `/freeze [ключ]` — Заморозка\n"
        "🔹 `/delkey [ключ]` — Удалить\n"
        "🔹 `/aprofile [ID]` — Профиль юзера"
    )
    await message.answer(text, parse_mode="Markdown")

@dp.message_handler(commands=['start'], state='*')
async def start(message: types.Message, state: FSMContext):
    await state.finish()
    supabase.table("users").upsert({"id": message.from_user.id, "username": message.from_user.username}).execute()
    kb = get_main_menu()
    gift_kb = InlineKeyboardMarkup().add(InlineKeyboardButton("🎁 Бесплатно", url="https://t.me/c/3771853425/2"))
    await message.answer("👋 DX9WARE запущен!", reply_markup=kb)
    await message.answer("Получить доступ бесплатно:", reply_markup=gift_kb)

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
    
