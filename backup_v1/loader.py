from aiogram import Bot, Dispatcher
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from config import DefaultConfig
from database import Database
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)

# 初始化核心对象
bot = Bot(token=DefaultConfig.API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)
db = Database()
