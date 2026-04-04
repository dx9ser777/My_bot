import logging
import os
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor

# --- НАСТРОЙКИ ---
API_TOKEN = '8607818846:AAHnoGKXL-zWEWXlh8V1BbUm9Yq1puuV_Is'
SUPPORT_URL = "https://t.me/WareSupport"
CHANNEL_URL = "https://t.me/Luci4DX9"
FILE_NAME = "cheat_file.zip" 

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)
logging.basicConfig(level=logging.INFO)

# Список активных юзеров в памяти
active_users = set()

# Функция для создания меню (только инлайн-кнопки под текстом)
def get_main_menu(user_id):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("👤 Профиль", callback_data="profile"),
        types.InlineKeyboardButton("🛒 Купить ключ", url=SUPPORT_URL),
        types.InlineKeyboardButton("🔑 Активировать ключ", callback_data="activate")
    )
    if user_id in active_users:
        markup.add(types.InlineKeyboardButton("📁 Получить файлы", callback_data="get_files"))
    
    markup.add(types.InlineKeyboardButton("📢 Наш канал", url=CHANNEL_URL))
    return markup

# Команда /start - убрали ReplyKeyboard (обычные кнопки), теперь только текст
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    # Удаляем обычную клавиатуру, если она осталась от старых версий
    await message.answer(
        "Привет дорогой игрок! Здесь ты сможешь купить лучшее дополнение по низким ценам "
        "для Standoff 2 и быть всегда наверху!", 
        reply_markup=get_main_menu(message.from_user.id)
    )

@dp.callback_query_handler(lambda c: c.data)
async def process_callback(callback_query: types.CallbackQuery):
    uid = callback_query.from_user.id
    
    if callback_query.data == 'activate':
        await bot.send_message(uid, "Отправь мне ключ активации:")
        
    elif callback_query.data == 'profile':
        has_key = "Есть (Активен)" if uid in active_users else "нет ключа"
        end_time = "неизвестно" if uid in active_users else "—"
        
        text = (f"👤 **Твой профиль**\n\n"
                f"🆔 Твой ID: `{uid}`\n"
                f"🔑 Ключ: {has_key}\n"
                f"⏳ Закончится: {end_time}")
        await bot.send_message(uid, text, parse_mode="Markdown", reply_markup=get_main_menu(uid))
        
    elif callback_query.data == 'get_files':
        if uid in active_users:
            if os.path.exists(FILE_NAME):
                with open(FILE_NAME, 'rb') as f:
                    await bot.send_document(uid, f, caption="Твои файлы готовы!")
            else:
                await bot.send_message(uid, "Файл чита еще не загружен на сервер.")
        else:
            await bot.send_message(uid, "Сначала активируй ключ!")

    await bot.answer_callback_query(callback_query.id)

# Проверка ключа (теперь максимально простая)
@dp.message_handler()
async def check_key(message: types.Message):
    user_key = message.text.strip()
    uid = message.from_user.id
    
    # Пытаемся прочитать keys.txt из текущей папки
    try:
        with open("keys.txt", "r", encoding="utf-8") as f:
            valid_keys = [line.strip() for line in f.readlines() if line.strip()]
        
        if user_key in valid_keys:
            active_users.add(uid)
            await message.answer("✅ Ключ подтвержден! Появилась кнопка «Получить файлы».", reply_markup=get_main_menu(uid))
        else:
            await message.answer("Неверный ключ")
    except:
        # Если файла нет или ошибка - просто пишем "Неверный ключ"
        await message.answer("Неверный ключ")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
        
