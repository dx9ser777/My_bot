import logging
import os
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor

# --- НАСТРОЙКИ ---
API_TOKEN = '8607818846:AAHnoGKXL-zWEWXlh8V1BbUm9Yq1puuV_Is'
SUPPORT_URL = "https://t.me/WareSupport"
PAYMENT_ADMIN = "@ware4"
CHANNEL_URL = "https://t.me/Luci4DX9"
FILE_NAME = "cheat_file.zip" 

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)
logging.basicConfig(level=logging.INFO)

active_users = set()

def get_keys():
    paths = ["keys.txt", "/data/keys.txt", "data/keys.txt"]
    for path in paths:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return [line.strip() for line in f.readlines() if line.strip()]
    return []

def get_main_menu(user_id):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("👤 Профиль", callback_data="profile"),
        types.InlineKeyboardButton("🛒 Товары и Цены", callback_data="shop"),
        types.InlineKeyboardButton("🔑 Активировать ключ", callback_data="activate")
    )
    if user_id in active_users:
        markup.add(types.InlineKeyboardButton("📁 Получить файлы", callback_data="get_files"))
    markup.add(types.InlineKeyboardButton("📢 Наш канал", url=CHANNEL_URL))
    return markup

@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    await message.answer(
        "Привет дорогой игрок! Здесь ты сможешь купить лучшее дополнение по низким ценам для Standoff 2.", 
        reply_markup=types.ReplyKeyboardRemove() 
    )
    await message.answer("Выбери действие:", reply_markup=get_main_menu(message.from_user.id))

@dp.callback_query_handler(lambda c: c.data)
async def process_callback(callback_query: types.CallbackQuery):
    uid = callback_query.from_user.id
    
    if callback_query.data == 'shop':
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("Android (APK)", callback_data="shop_apk"),
            types.InlineKeyboardButton("iOS", callback_data="shop_ios"),
            types.InlineKeyboardButton("⬅️ Назад", callback_data="back_main")
        )
        await bot.edit_message_text("Выберите вашу платформу:", uid, callback_query.message.message_id, reply_markup=markup)

    elif callback_query.data == 'shop_apk':
        text = (
            "🍏 **APK DX9WARE**\n\n"
            "🌟 **Цены в Stars:**\n"
            "├ 7 Days — 350⭐️\n"
            "└ Month — 700⭐️\n"
            "⚠️ _Комиссия на вас_\n\n"
            "🌐 **Price on Crypto:**\n"
            "├ 7 Days — 4☺️\n"
            "└ Month — 8☺️\n\n"
            f"📩 Для оплаты писать: {PAYMENT_ADMIN}"
        )
        markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("⬅️ Назад", callback_data="shop"))
        await bot.edit_message_text(text, uid, callback_query.message.message_id, parse_mode="Markdown", reply_markup=markup)

    elif callback_query.data == 'shop_ios':
        text = (
            "🍎 **IOS DX9WARE**\n\n"
            "🌟 **Цены в Stars:**\n"
            "├ 7 Days — 400⭐️\n"
            "└ Month — 800⭐️\n"
            "⚠️ _Комиссия на вас_\n\n"
            "🌐 **Price on Crypto:**\n"
            "├ 7 Days — 6☺️\n"
            "└ Month — 12☺️\n\n"
            f"📩 Для оплаты писать: {PAYMENT_ADMIN}"
        )
        markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("⬅️ Назад", callback_data="shop"))
        await bot.edit_message_text(text, uid, callback_query.message.message_id, parse_mode="Markdown", reply_markup=markup)

    elif callback_query.data == 'back_main':
        await bot.edit_message_text("Выбери действие:", uid, callback_query.message.message_id, reply_markup=get_main_menu(uid))

    elif callback_query.data == 'activate':
        await bot.send_message(uid, "Отправь мне ключ активации:")
        
    elif callback_query.data == 'profile':
        has_key = "Есть (Активен)" if uid in active_users else "нет ключа"
        end_time = "неизвестно" if uid in active_users else "—"
        text = (f"👤 **Твой профиль**\n\n🆔 Твой ID: `{uid}`\n🔑 Ключ: {has_key}\n⏳ Закончится: {end_time}")
        await bot.send_message(uid, text, parse_mode="Markdown", reply_markup=get_main_menu(uid))
        
    elif callback_query.data == 'get_files':
        if uid in active_users:
            if os.path.exists(FILE_NAME):
                with open(FILE_NAME, 'rb') as f:
                    await bot.send_document(uid, f, caption="Твои файлы готовы!")
            else:
                await bot.send_message(uid, "Файл еще не загружен.")
        else:
            await bot.send_message(uid, "Сначала активируй ключ!")
            
    await bot.answer_callback_query(callback_query.id)

@dp.message_handler()
async def check_key(message: types.Message):
    user_key = message.text.strip()
    uid = message.from_user.id
    valid_keys = get_keys()
    
    if user_key in valid_keys:
        active_users.add(uid)
        await message.answer("✅ Ключ подтвержден!", reply_markup=get_main_menu(uid))
    else:
        await message.answer("Неверный ключ")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
        
