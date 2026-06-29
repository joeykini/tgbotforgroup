from loader import dp
from filters import register_admin_filter

def setup_handlers():
    register_admin_filter(dp)
    import handlers.private
    import handlers.group
    import handlers.admin
