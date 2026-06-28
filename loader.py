from aiogram import Bot, Dispatcher
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from config import DefaultConfig
from database import Database
from middleware.logging_mw import IncomingLogMiddleware
import logging

# 配置日志（写入 bot.log / nohup.out）
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

# 初始化核心对象
bot = Bot(token=DefaultConfig.API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)
dp.middleware.setup(IncomingLogMiddleware())
db = Database()
