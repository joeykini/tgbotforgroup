from loader import dp
import handlers.private
import handlers.group
import handlers.admin

def setup_handlers():
    # 这里的导入实际上就已经完成了注册，因为 aiogram 的装饰器在模块导入时生效
    pass
