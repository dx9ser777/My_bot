import logging
import os
import asyncio
import aiohttp
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor

# --- БЕЗОПАСНЫЕ НАСТРОЙКИ (Берем из Секретов Amvera) ---
API_TOKEN = os.getenv('BOT_TOKEN')
CRYPTO_PAY_TOKEN = os.getenv('CRYPTO_TOKEN')

# Контакты и ссылки
SUPPORT_URL = "https://t.me/WareSupport"
PAYMENT_ADMIN = "@ware4"
CHANNEL_URL = "https://t.me/Luci4DX9"
FILE_NAME = "cheat_file.zip" 

# Проверка наличия ключей (для логов)
if not API_TOKEN or not CRYPTO_PAY_TOKEN:
    logging.error("ОШИБКА: Ключи не найдены в Секретах Amvera!")

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)
logging.basicConfig(level=logging.INFO)

# Список активных юзеров (в памяти)
active_users = set()

# Прайс-лист для Крипто-бота (USDT)
PRICES_CRYPTO = {
    "apk_7": 4, "apk_30": 8,
    "ios_7": 6, "ios_30": 12
}

# --- ФУНКЦИЯ ВЫДАЧИ КЛЮЧА ИЗ ФАЙЛА ---
def extract_one_key():
    paths = ["keys.txt", "/data/keys.txt", "data/keys.txt"]
    for path in paths:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            if not lines: continue
            
            key_to_give = lines[0].strip()
            remaining_keys = lines[1:]
            
            with open(path, "w", encoding="utf-8") as f:
                f.writelines(remaining_keys)
            return key_to_give
    return None

# --- РАБОТА С CRYPTO PAY API ---
async def create_invoice(amount):
    headers = {'Crypto-Pay-API-Token': CRYPTO_PAY_TOKEN}
    data = {
        'asset': 'USDT', 
        'amount': str(amount), 
        'description': 'DX9WARE Subscription', 
        'allow_comments': False
    }
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

# --- КЛАВИАТУРА МЕНЮ ---
def get_main_menu(user_id):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("👤 Профиль", callback_data="profile"),
        types.InlineKeyboardButton("🛒 Товары и Цены", callback_data="shop")
    )
    if user_id not in active_users:
        markup.add(types.InlineKeyboardButton("🔑 Активировать ключ", callback_data="activate"))
    else:
        markup.add(types.InlineKeyboardButton("📁 Получить файлы", callback_data="get_files"))
    markup.add(types.InlineKeyboardButton("📢 Наш канал", url=CHANNEL_URL))
    return markup

# --- ОБРАБОТКА КОМАНД ---
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    await message.answer("Добро пожаловать в DX9WARE!", reply_markup=get_main_menu(message.from_user.id))

@dp.callback_query_handler(lambda c: c.data)
async def process_callback(callback_query: types.CallbackQuery):
    uid = callback_query.from_user.id
    
    # Главное меню магазина
    if callback_query.data == 'shop':
        markup = types.InlineKeyboardMarkup(row_width=2).add(
            types.InlineKeyboardButton("Android (APK) 😀", callback_data="shop_apk"),
            types.InlineKeyboardButton("iOS 😔", callback_data="shop_ios"),
            types.InlineKeyboardButton("⬅️ Назад", callback_data="back_main")
        )
        await bot.edit_message_text("Выберите вашу платформу:", uid, callback_query.message.message_id, reply_markup=markup)

    # Прайс для Android
    elif callback_query.data == 'shop_apk':
        text = (
            "🍏 **APK DX9WARE**\n\n"
            "🌟 **Stars:**\n"
            "├ 7 days — 350⭐️\n"
            "└ Month — 700⭐️\n"
            "⚠️ _Комиссия на вас_\n\n"
            "🌐 **Crypto Price:**\n"
            "├ 7 days — 4 USDT\n"
            "└ Month — 8 USDT\n\n"
            f"📩 По поводу Stars или NFT писать: {PAYMENT_ADMIN}"
        )
        markup = types.InlineKeyboardMarkup(row_width=1).add(
            types.InlineKeyboardButton("Купить 7 дней (4$ Crypto)", callback_data="buy_apk_7"),
            types.InlineKeyboardButton("Купить Месяц (8$ Crypto)", callback_data="buy_apk_30"),
            types.InlineKeyboardButton("⬅️ Назад", callback_data="shop")
        )
        await bot.edit_message_text(text, uid, callback_query.message.message_id, parse_mode="Markdown", reply_markup=markup)

    # Прайс для iOS
    elif callback_query.data == 'shop_ios':
        text = (
            "🍎 **IOS DX9WARE**\n\n"
            "🌟 **Stars:**\n"
            "├ 7 days — 400⭐️\n"
            "└ Month — 800⭐️\n"
            "⚠️ _Комиссия на вас_\n\n"
            "🌐 **Crypto Price:**\n"
            "├ 7 days — 6 USDT\n"
            "└ Month — 12 USDT\n\n"
            f"📩 По поводу Stars или NFT писать: {PAYMENT_ADMIN}"
        )
        markup = types.InlineKeyboardMarkup(row_width=1).add(
            types.InlineKeyboardButton("Купить 7 дней (6$ Crypto)", callback_data="buy_ios_7"),
            types.InlineKeyboardButton("Купить Месяц (12$ Crypto)", callback_data="buy_ios_30"),
            types.InlineKeyboardButton("⬅️ Назад", callback_data="shop")
        )
        await bot.edit_message_text(text, uid, callback_query.message.message_id, parse_mode="Markdown", reply_markup=markup)

    # Создание счета
    elif callback_query.data.startswith('buy_'):
        plan = callback_query.data.replace('buy_', '')
        res = await create_invoice(PRICES_CRYPTO[plan])
        if res['ok']:
            markup = types.InlineKeyboardMarkup(row_width=1).add(
                types.InlineKeyboardButton("💳 Оплатить в Crypto Bot", url=res['result']['pay_url']),
                types.InlineKeyboardButton("✅ Проверить оплату", callback_data=f"check_{res['result']['invoice_id']}")
            )
            await bot.send_message(uid, f"Счет на {PRICES_CRYPTO[plan]}$ создан. Оплатите и нажмите проверить:", reply_markup=markup)

    # Проверка оплаты и выдача ключа
    elif callback_query.data.startswith('check_'):
        inv_id = callback_query.data.replace('check_', '')
        await bot.answer_callback_query(callback_query.id, "Проверяю...")
        
        if await check_invoice(inv_id):
            new_key = extract_one_key()
            if new_key:
                active_users.add(uid)
                await bot.send_message(uid, f"✅ Оплата прошла!\n\nТвой ключ: `{new_key}`\nАктивируй его кнопкой в меню.", parse_mode="Markdown")
            else:
                await bot.send_message(uid, f"❌ Оплата ок, но ключи кончились! Пиши {PAYMENT_ADMIN}")
        else:
            await bot.answer_callback_query(callback_query.id, "Оплата не найдена!", show_alert=True)

    elif callback_query.data == 'back_main':
        await bot.edit_message_text("Меню:", uid, callback_query.message.message_id, reply_markup=get_main_menu(uid))
    
    elif callback_query.data == 'activate':
        await bot.send_message(uid, "Отправь ключ активации:")
    
    elif callback_query.data == 'profile':
        status = "Активен ✅" if uid in active_users else "нет ключа ❌"
        await bot.send_message(uid, f"👤 ID: `{uid}`\n🔑 Статус: {status}", parse_mode="Markdown")

    elif callback_query.data == 'get_files':
        if uid in active_users and os.path.exists(FILE_NAME):
            with open(FILE_NAME, 'rb') as f:
                await bot.send_document(uid, f, caption="Твои файлы готовы!")
    
    await bot.answer_callback_query(callback_query.id)

# --- ПРОВЕРКА КЛЮЧА ОТ ЮЗЕРА ---
@dp.message_handler()
async def handle_key_activation(message: types.Message):
    user_key = message.text.strip()
    valid_keys = []
    # Проверяем все возможные пути к файлу с ключами
    for p in ["keys.txt", "/data/keys.txt", "data/keys.txt"]:
        if os.path.exists(p):
            with open(p, "r") as f:
                valid_keys.extend([line.strip() for line in f.readlines()])
    
    if user_key in valid_keys:
        active_users.add(message.from_user.id)
        await message.answer("✅ Доступ открыт!", reply_markup=get_main_menu(message.from_user.id))
    else:
        await message.answer("❌ Неверный ключ")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
    
