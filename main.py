import logging
import random
import string
import asyncio
import aiohttp
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, executor, types
from aiogram.dispatcher import FSMContext
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import State, StatesGroup
from supabase import create_client, Client

# --- КОНФИГ ---
API_TOKEN = '8607818846:AAEjGMfOMw8JmUsXu8Zj5mUdzfP1RylLVjU'
CRYPTO_PAY_TOKEN = '560149:AAdisc69jC2qejfxQvAD5y56K4Jx1oBn9f1'
ADMIN_ID = 6332767725 

SUPABASE_URL = "https://yuksepnwkzffudhcrjnl.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inl1a3NlcG53a3pmZnVkaGNyam5sIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzUwNDM5OTksImV4cCI6MjA5MDYxOTk5OX0.6IvYWJiWqVeFVkQ-SK1NbG5_yEXVyHijFMGwvMbn1q4"

logging.basicConfig(level=logging.INFO)
storage = MemoryStorage()
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot, storage=storage)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

class Form(StatesGroup):
    waiting_days = State()
    waiting_activation = State()

def gen_str(prefix="DX9-", length=10):
    return prefix + ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

# --- ФУНКЦИЯ ДОБАВЛЕНИЯ КЛЮЧА (БОТ + ЛОАДЕР) ---
def add_key_to_db(key_str, days):
    # В таблицу keys для управления
    supabase.table("keys").insert({
        "key": key_str, 
        "days": days, 
        "max_uses": 1, 
        "is_active": True, 
        "used_count": 0
    }).execute()
    # В таблицу username для твоего лоадера
    supabase.table("username").insert({"password": key_str}).execute()

# --- CRYPTO BOT API ---
async def create_invoice(amount):
    headers = {'Crypto-Pay-API-Token': CRYPTO_PAY_TOKEN}
    data = {'asset': 'USDT', 'amount': str(amount), 'description': 'DX9WARE Sub'}
    async with aiohttp.ClientSession() as session:
        async with session.post('https://pay.crypt.bot/api/createInvoice', json=data, headers=headers) as resp:
            return await resp.json()

async def check_invoice(invoice_id):
    headers = {'Crypto-Pay-API-Token': CRYPTO_PAY_TOKEN}
    async with aiohttp.ClientSession() as session:
        params = {'invoice_ids': str(invoice_id)}
        async with session.get('https://pay.crypt.bot/api/getInvoices', params=params, headers=headers) as resp:
            res = await resp.json()
            if res['ok'] and res['result']['items']:
                return res['result']['items'][0]['status'] == 'paid'
    return False

# --- ОБРАБОТКА СТАРТА И МЕНЮ ---
@dp.message_handler(commands=['start'], state='*')
async def start_cmd(message: types.Message, state: FSMContext):
    await state.finish() # Сброс всех зависших состояний
    supabase.table("users").upsert({"id": message.from_user.id}).execute()
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("👤 Профиль", "🛒 Товары", "🔑 Активировать", "🎁 Промо")
    await message.answer("👋 Добро пожаловать в DX9WARE!", reply_markup=markup)

@dp.message_handler(lambda m: m.text == "👤 Профиль", state='*')
async def profile_h(message: types.Message):
    r = supabase.table("users").select("*").eq("id", message.from_user.id).execute()
    u = r.data[0] if r.data else {}
    await message.answer(f"👤 **ПРОФИЛЬ**\n\nID: `{message.from_user.id}`\nПодписка до: `{u.get('active_until') or 'Нет'}`\nКлюч: `{u.get('current_key') or 'Нет'}`", parse_mode="Markdown")

@dp.message_handler(lambda m: m.text == "🔑 Активировать", state='*')
async def start_act(message: types.Message):
    await Form.waiting_activation.set()
    await message.answer("🔑 Введите ваш лицензионный ключ:")

@dp.message_handler(state=Form.waiting_activation)
async def act_key_logic(message: types.Message, state: FSMContext):
    key = message.text.strip()
    res = supabase.table("keys").select("*").eq("key", key).execute()
    
    if res.data:
        k = res.data[0]
        if k['is_active'] and k['used_count'] < k['max_uses']:
            exp = (datetime.now() + timedelta(days=k['days'])).strftime("%Y-%m-%d")
            supabase.table("users").update({"active_until": exp, "current_key": key}).eq("id", message.from_user.id).execute()
            supabase.table("keys").update({"used_count": k['used_count'] + 1}).eq("key", key).execute()
            await message.answer(f"✅ **Успешно!**\nПодписка до: `{exp}`", parse_mode="Markdown")
        else:
            await message.answer("❌ Ключ заморожен или уже использован.")
    else:
        await message.answer("❌ Ключ не найден.")
    await state.finish()

# --- МАГАЗИН ---
@dp.message_handler(lambda m: m.text == "🛒 Товары", state='*')
async def shop_main(message: types.Message):
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(types.InlineKeyboardButton("Android", callback_data="sh_apk"),
           types.InlineKeyboardButton("iOS", callback_data="sh_ios"))
    await message.answer("🛒 Выберите платформу:", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith('sh_'))
async def shop_os(call: types.CallbackQuery):
    os = call.data.split('_')[1]
    p7, p30 = (4, 8) if os == "apk" else (6, 12)
    kb = types.InlineKeyboardMarkup(row_width=1).add(
        types.InlineKeyboardButton(f"💳 7 Дней ({p7}$)", callback_data=f"buy_7_{p7}"),
        types.InlineKeyboardButton(f"💳 Месяц ({p30}$)", callback_data=f"buy_30_{p30}")
    )
    await call.message.edit_text(f"📦 Тарифы для {os.upper()}:", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith('buy_'))
async def pay_create(call: types.CallbackQuery):
    _, days, price = call.data.split('_')
    res = await create_invoice(price)
    if res['ok']:
        kb = types.InlineKeyboardMarkup().add(
            types.InlineKeyboardButton("🔗 Оплатить", url=res['result']['pay_url']),
            types.InlineKeyboardButton("✅ Проверить", callback_data=f"chk_{res['result']['invoice_id']}_{days}")
        )
        await call.message.answer(f"Счет на {price} USDT создан:", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith('chk_'))
async def pay_check(call: types.CallbackQuery):
    _, inv_id, days = call.data.split('_')
    if await check_invoice(inv_id):
        nk = gen_str()
        add_key_to_db(nk, int(days))
        await call.message.answer(f"✅ Оплачено! Ключ:\n`{nk}`", parse_mode="Markdown")
    else:
        await call.answer("❌ Оплата не найдена", show_alert=True)

# --- АДМИН ПАНЕЛЬ ---
@dp.message_handler(commands=['admin'], state='*')
async def adm_start(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    await state.finish()
    kb = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("➕ Создать ключ", callback_data="adm_gen"))
    await message.answer("⚙️ Админ-панель:", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data == "adm_gen")
async def adm_gen_days(call: types.CallbackQuery):
    await Form.waiting_days.set()
    await call.message.answer("На сколько дней создать ключ? (Введите число)")

@dp.message_handler(state=Form.waiting_days)
async def adm_gen_final(message: types.Message, state: FSMContext):
    if not message.text.isdigit(): # Защита от текста
        return await message.answer("⚠️ Введите только число!")
    
    days = int(message.text)
    nk = gen_str()
    add_key_to_db(nk, days) # Бот + Лоадер
    await message.answer(f"✅ Ключ создан:\n`{nk}`", parse_mode="Markdown")
    await state.finish()

# --- КОМАНДЫ УПРАВЛЕНИЯ ---
@dp.message_handler(commands=['akey', 'Akey', 'allkey', 'Allkey'], state='*')
async def adm_list(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    res = supabase.table("keys").select("*").execute()
    if not res.data: return await message.answer("Ключей нет.")
    
    is_full = "all" not in message.get_command().lower()
    text = "🔑 **СПИСОК:**\n\n"
    for k in res.data:
        disp = f"`{k['key']}`" if is_full else f"`{k['key'][:5]}***`"
        text += f"{'✅' if k['is_active'] else '❄️'} {disp} | {k['days']}д | {k['used_count']}/{k['max_uses']}\n"
    await message.answer(text, parse_mode="Markdown")

@dp.message_handler(commands=['freeze', 'unfreeze', 'delkey', 'remove'], state='*')
async def adm_mng(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    cmd, key = message.get_command().lower(), message.get_args().strip()
    if not key: return await message.answer(f"Пример: `/{cmd} КЛЮЧ`")

    check = supabase.table("keys").select("*").eq("key", key).execute()
    if not check.data: return await message.answer("Ключ не найден.")

    if cmd == 'freeze':
        supabase.table("keys").update({"is_active": False}).eq("key", key).execute()
        await message.answer(f"❄️ `{key}` заморожен.")
    elif cmd == 'unfreeze':
        supabase.table("keys").update({"is_active": True}).eq("key", key).execute()
        await message.answer(f"☀️ `{key}` активен.")
    elif cmd in ['delkey', 'remove']:
        supabase.table("keys").delete().eq("key", key).execute()
        supabase.table("username").delete().eq("password", key).execute()
        await message.answer(f"🗑 `{key}` удален отовсюду.")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
    
