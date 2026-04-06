import logging
import random
import string
import aiohttp
import os
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputFile
from aiogram.dispatcher import FSMContext
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import State, StatesGroup
from supabase import create_client, Client

# --- КОНФИГ ---
API_TOKEN = '8607818846:AAEjGMfOMw8JmUsXu8Zj5mUdzfP1RylLVjU'
ADMIN_ID = 6332767725 
CRYPTO_PAY_TOKEN = '560149:AAdisc69jC2qejfxQvAD5y56K4Jx1oBn9f1'
FILE_NAME = "cheat_file.zip" # Файл должен лежать в папке с ботом

SUPABASE_URL = "https://yuksepnwkzffudhcrjnl.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inl1a3NlcG53a3pmZnVkaGNyam5sIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzUwNDM5OTksImV4cCI6MjA5MDYxOTk5OX0.6IvYWJiWqVeFVkQ-SK1NbG5_yEXVyHijFMGwvMbn1q4"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

class Form(StatesGroup):
    waiting_days = State()
    waiting_activation = State()

PRICES_CRYPTO = {
    "apk_7": 4, "apk_30": 8, "ios_7": 6, "ios_30": 12
}

def get_main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("👤 Профиль", "🛒 Товары", "🔑 Активировать", "🎁 Промо")
    return markup

def gen_str(prefix="DX9-", length=10):
    return prefix + ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

# --- API CRYPTO PAY ---

async def create_invoice(amount):
    headers = {'Crypto-Pay-API-Token': CRYPTO_PAY_TOKEN}
    data = {'asset': 'USDT', 'amount': str(amount), 'description': 'DX9WARE Subscription'}
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

# --- ОБРАБОТКА ФАЙЛОВ ---

@dp.callback_query_handler(lambda c: c.data == "download_file", state='*')
async def send_cheat_file(callback: types.CallbackQuery):
    if os.path.exists(FILE_NAME):
        await callback.message.answer_document(InputFile(FILE_NAME), caption="🚀 **Ваш файл DX9WARE готов!**")
    else:
        await callback.answer("⚠️ Файл временно недоступен, обратитесь в поддержку.", show_alert=True)

# --- ТОВАРЫ ---

@dp.message_handler(lambda m: m.text == "🛒 Товары", state='*')
async def shop_start(message: types.Message, state: FSMContext):
    await state.finish()
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("Android 🤖", callback_data="shop_apk"),
        InlineKeyboardButton("iOS 🍎", callback_data="shop_ios")
    )
    await message.answer("🛒 **Выберите вашу платформу:**", reply_markup=markup)

@dp.callback_query_handler(lambda c: c.data.startswith('shop_'), state='*')
async def shop_platform(callback: types.CallbackQuery):
    plat = callback.data.split('_')[1]
    is_ios = plat == "ios"
    
    text = (
        f"💎 **МАГАЗИН DX9WARE [{'iOS 🍎' if is_ios else 'Android 🤖'}]**\n\n"
        f"🌟 **Stars:**\n├ 7 дней — {'400⭐️' if is_ios else '350⭐️'}\n└ Месяц — {'800⭐️' if is_ios else '700⭐️'}\n\n"
        f"🌐 **Crypto:**\n├ 7 дней — {'6$' if is_ios else '4$'}\n└ Месяц — {'12$' if is_ios else '8$'}\n\n"
        f"📩 Покупка через Stars: @ware4"
    )
    
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton(f"💳 Купить 7 дней ({'6$' if is_ios else '4$'})", callback_data=f"buy_{plat}_7"),
        InlineKeyboardButton(f"💳 Купить Месяц ({'12$' if is_ios else '8$'})", callback_data=f"buy_{plat}_30"),
        InlineKeyboardButton("✨ Stars (Администратор)", url="https://t.me/ware4"),
        InlineKeyboardButton("⬅️ Назад", callback_data="back_shop")
    )
    await callback.message.edit_text(text, reply_markup=markup, parse_mode="Markdown")

@dp.callback_query_handler(lambda c: c.data.startswith('buy_'), state='*')
async def process_buy(callback: types.CallbackQuery):
    plan = callback.data.replace('buy_', '')
    amount = PRICES_CRYPTO.get(plan, 8)
    
    res = await create_invoice(amount)
    if res['ok']:
        markup = InlineKeyboardMarkup().add(
            InlineKeyboardButton("🔗 Перейти к оплате", url=res['result']['pay_url']),
            InlineKeyboardButton("✅ Проверить оплату", callback_data=f"check_{res['result']['invoice_id']}_{plan}")
        )
        await callback.message.answer(f"💰 **Счет на {amount} USDT создан!**\nОплатите его в Crypto Bot:", reply_markup=markup)

@dp.callback_query_handler(lambda c: c.data.startswith('check_'), state='*')
async def process_check(callback: types.CallbackQuery):
    data = callback.data.split('_')
    inv_id, plan_days = data[1], int(data[3])
    
    if await check_invoice(inv_id):
        new_key = gen_str()
        supabase.table("keys").insert({"key": new_key, "days": plan_days}).execute()
        try: supabase.table("username").insert({"password": new_key}).execute()
        except: pass
        
        markup = InlineKeyboardMarkup().add(InlineKeyboardButton("📁 Получить файлы", callback_data="download_file"))
        await callback.message.answer(f"🎉 **Оплата подтверждена!**\n\n🔑 Твой ключ: `{new_key}`\n\n👇 Нажми кнопку ниже, чтобы скачать чит:", reply_markup=markup, parse_mode="Markdown")
    else:
        await callback.answer("❌ Оплата еще не поступила!", show_alert=True)

# --- ПРОФИЛЬ ---

@dp.message_handler(lambda m: m.text == "👤 Профиль", state='*')
async def profile_view(message: types.Message, state: FSMContext):
    await state.finish()
    res = supabase.table("users").select("*").eq("id", message.from_user.id).execute()
    if res.data:
        u = res.data[0]
        sub = u.get('active_until')
        markup = InlineKeyboardMarkup()
        if sub and sub != "Нет":
            markup.add(InlineKeyboardButton("📁 Получить файлы", callback_data="download_file"))
            
        await message.answer(
            f"👤 **ВАШ ПРОФИЛЬ**\n\n"
            f"🆔 ID: `{u['id']}`\n"
            f"📅 Подписка: `{sub or 'Отсутствует ❌'}`\n"
            f"🔑 Последний ключ: `{u.get('current_key') or '—'}`", 
            parse_mode="Markdown", reply_markup=markup
        )

# --- АКТИВАЦИЯ ---

@dp.message_handler(lambda m: m.text == "🔑 Активировать", state='*')
async def act_start(message: types.Message, state: FSMContext):
    await state.finish()
    await Form.waiting_activation.set()
    await message.answer("🔑 **Введите ваш лицензионный ключ:**", reply_markup=types.ReplyKeyboardRemove())

@dp.message_handler(state=Form.waiting_activation)
async def act_logic(message: types.Message, state: FSMContext):
    key_input = message.text.strip()
    res = supabase.table("keys").select("*").eq("key", key_input).execute()
    
    if res.data:
        k = res.data[0]
        days = k['days']
        exp = "Lifetime ♾" if days >= 90000 else (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
        
        supabase.table("users").update({"active_until": exp, "current_key": key_input}).eq("id", message.from_user.id).execute()
        supabase.table("keys").delete().eq("key", key_input).execute()
        
        markup = InlineKeyboardMarkup().add(InlineKeyboardButton("📁 Получить файлы", callback_data="download_file"))
        await message.answer(f"✅ **Успешно!**\nПодписка активна до: `{exp}`", reply_markup=get_main_menu())
        await message.answer("📦 Вы можете скачать файлы проекта:", reply_markup=markup)
    else:
        await message.answer("❌ **Ошибка:** Ключ неверный или истек.", reply_markup=get_main_menu())
    await state.finish()

# --- АДМИН КОМАНДЫ ---

@dp.message_handler(commands=['admin'], state='*')
async def admin_gen(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    await Form.waiting_days.set()
    await message.answer("⚙️ **На сколько дней создать ключ?** (0 = Lifetime)")

@dp.message_handler(state=Form.waiting_days)
async def admin_gen_logic(message: types.Message, state: FSMContext):
    if not message.text.isdigit(): return
    days = 99999 if message.text == "0" else int(message.text)
    new_key = gen_str()
    supabase.table("keys").insert({"key": new_key, "days": days}).execute()
    try: supabase.table("username").insert({"password": new_key}).execute()
    except: pass
    await message.answer(f"✅ **Ключ создан:** `{new_key}`", parse_mode="Markdown", reply_markup=get_main_menu())
    await state.finish()

@dp.message_handler(commands=['allkey', 'delkey', 'clearkey'], state='*')
async def admin_utils(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    cmd = message.get_command()
    if cmd == '/allkey':
        res = supabase.table("keys").select("*").execute()
        text = "🔑 **База ключей:**\n" + "\n".join([f"`{k['key']}` ({k['days']}д)" for k in res.data]) if res.data else "Пусто 📭"
        await message.answer(text, parse_mode="Markdown")
    elif cmd == '/clearkey':
        supabase.table("keys").delete().neq("key", "0").execute()
        await message.answer("🗑 **База ключей полностью очищена!**")

# --- СТАРТ ---

@dp.message_handler(commands=['start'], state='*')
async def start(message: types.Message, state: FSMContext):
    await state.finish()
    supabase.table("users").upsert({"id": message.from_user.id, "username": message.from_user.username}).execute()
    await message.answer("👋 **Привет! DX9WARE Bot готов к работе.**\nИспользуй меню ниже для навигации:", reply_markup=get_main_menu())

@dp.callback_query_handler(lambda c: c.data == "back_shop", state='*')
async def back_shop(callback: types.CallbackQuery, state: FSMContext):
    await shop_start(callback.message, state)

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
    
