import logging
import random
import string
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, executor, types
from aiogram.dispatcher import FSMContext
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import State, StatesGroup
from supabase import create_client, Client

# --- КОНФИГ ---
API_TOKEN = '8607818846:AAEjGMfOMw8JmUsXu8Zj5mUdzfP1RylLVjU'
ADMIN_ID = 6332767725 

SUPABASE_URL = "https://yuksepnwkzffudhcrjnl.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inl1a3NlcG53a3pmZnVkaGNyam5sIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzUwNDM5OTksImV4cCI6MjA5MDYxOTk5OX0.6IvYWJiWqVeFVkQ-SK1NbG5_yEXVyHijFMGwvMbn1q4"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

class Form(StatesGroup):
    waiting_days = State()
    waiting_activation = State()

def get_main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("👤 Профиль", "🛒 Товары", "🔑 Активировать", "🎁 Промо")
    return markup

def gen_str(prefix="DX9-", length=10):
    return prefix + ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

# --- ТОВАРЫ (ОБНОВЛЕННЫЙ ПРАЙС) ---
@dp.message_handler(lambda m: m.text == "🛒 Товары", state='*')
async def shop_view(message: types.Message, state: FSMContext):
    await state.finish()
    text = (
        "**Apk DX9WARE 😀**\n"
        "**Stars:**\n"
        "7 days — 350⭐️\n"
        "Month — 700⭐️\n"
        "*Комиссия на вас*\n\n"
        "**IOS😔**\n"
        "7 days — 400⭐️\n"
        "Month — 800⭐️\n\n"
        "**Price on Crypto [APK]**\n"
        "7 days — 4 USDT ☺️\n"
        "Month — 8 USDT ☺️\n\n"
        "**[IOS]⭐️**\n"
        "7 days — 6 USDT ☺️\n"
        "Month — 12 USDT ☺️\n\n"
        "**Lifetime (Навсегда):**\n"
        "APK — 25 USDT / 2500⭐️\n"
        "IOS — 35 USDT / 3500⭐️\n\n"
        "📩 Send Crypto or Stars here: @ware4"
    )
    await message.answer(text, parse_mode="Markdown", reply_markup=get_main_menu())

# --- АДМИН-ПАНЕЛЬ ---
@dp.message_handler(commands=['admin'], state='*')
async def admin_cmd(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    await state.finish()
    await Form.waiting_days.set()
    await message.answer(
        "На сколько дней создать ключ?\n\n"
        "Число — дни (напр. 30)\n"
        "0 — Навсегда (Lifetime)", 
        reply_markup=types.ReplyKeyboardRemove()
    )

@dp.message_handler(state=Form.waiting_days)
async def process_days(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("⚠️ Введите только число!")
    
    input_days = int(message.text)
    # Логика вечного ключа: если 0, ставим 99999 дней
    is_lifetime = input_days == 0
    days = 99999 if is_lifetime else input_days
    
    new_key = gen_str()
    
    try:
        supabase.table("keys").insert({"key": new_key, "days": days}).execute()
        try:
            supabase.table("username").insert({"password": new_key}).execute()
        except: pass 
        
        type_text = "FOREVER (Lifetime)" if is_lifetime else f"{days} дней"
        await message.answer(f"✅ Ключ создан: `{new_key}`\nТип: {type_text}", parse_mode="Markdown", reply_markup=get_main_menu())
    except Exception as e:
        await message.answer(f"❌ Ошибка базы: {e}", reply_markup=get_main_menu())
    await state.finish()

# --- АКТИВАЦИЯ (ТВОЙ ТЕКСТ) ---
@dp.message_handler(lambda m: m.text == "🔑 Активировать", state='*')
async def act_btn(message: types.Message, state: FSMContext):
    await state.finish()
    await Form.waiting_activation.set()
    await message.answer("Введите ваш ключ:", reply_markup=types.ReplyKeyboardRemove())

@dp.message_handler(state=Form.waiting_activation)
async def act_process(message: types.Message, state: FSMContext):
    key = message.text.strip()
    try:
        res = supabase.table("keys").select("*").eq("key", key).execute()
        if res.data:
            k = res.data[0]
            days_to_add = k['days']
            
            # Если ключ вечный (99999), пишем "Lifetime", иначе считаем дату
            if days_to_add >= 90000:
                exp = "Lifetime (Навсегда)"
            else:
                exp = (datetime.now() + timedelta(days=days_to_add)).strftime("%Y-%m-%d")
            
            supabase.table("users").update({"active_until": exp}).eq("id", message.from_user.id).execute()
            supabase.table("keys").delete().eq("key", key).execute()
            
            await message.answer(
                f"Ваш ключ \n`{key}`\nАктивирован!\nВаш айди: `{message.from_user.id}`", 
                parse_mode="Markdown", reply_markup=get_main_menu()
            )
        else:
            await message.answer("❌ Ключ не найден.", reply_markup=get_main_menu())
    except Exception as e:
        await message.answer(f"❌ Ошибка активации: {e}", reply_markup=get_main_menu())
    await state.finish()

# --- ПРОФИЛЬ ---
@dp.message_handler(lambda m: m.text == "👤 Профиль", state='*')
async def profile_view(message: types.Message, state: FSMContext):
    await state.finish()
    try:
        r = supabase.table("users").select("*").eq("id", message.from_user.id).execute()
        sub = r.data[0].get('active_until', 'Нет') if r.data else "Нет"
        await message.answer(f"🆔 Ваш ID: `{message.from_user.id}`\n📅 Подписка: `{sub}`", parse_mode="Markdown")
    except:
        await message.answer(f"🆔 Ваш ID: `{message.from_user.id}`\n📅 Подписка: Ошибка данных")

# --- СТАРТ ---
@dp.message_handler(commands=['start', 'akey', 'delkey'], state='*')
async def start_cmds(message: types.Message, state: FSMContext):
    await state.finish()
    cmd = message.get_command()
    
    if cmd == '/start':
        try: supabase.table("users").upsert({"id": message.from_user.id}).execute()
        except: pass
        await message.answer("👋 Добро пожаловать в DX9WARE!", reply_markup=get_main_menu())
    
    elif cmd == '/akey':
        if message.from_user.id != ADMIN_ID: return
        res = supabase.table("keys").select("*").execute()
        text = "🔑 **КЛЮЧИ:**\n\n" + "\n".join([f"`{k['key']}` ({'Lifetime' if k['days'] >= 90000 else str(k['days'])+'д'})" for k in res.data])
        await message.answer(text if res.data else "Ключей нет.", parse_mode="Markdown")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
                       
