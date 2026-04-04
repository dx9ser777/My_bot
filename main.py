import logging
import os
import asyncio
import aiohttp
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor

# --- НАСТРОЙКИ (Берем из Секретов Amvera) ---
API_TOKEN = os.getenv('BOT_TOKEN')
CRYPTO_PAY_TOKEN = os.getenv('CRYPTO_TOKEN')

# Проверка: если секреты не подтянулись, бот напишет об этом в логи
if not API_TOKEN:
    logging.error("КРИТИЧЕСКАЯ ОШИБКА: Секрет BOT_TOKEN не найден!")
if not CRYPTO_PAY_TOKEN:
    logging.error("КРИТИЧЕСКАЯ ОШИБКА: Секрет CRYPTO_TOKEN не найден!")

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)
