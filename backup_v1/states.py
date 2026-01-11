from aiogram.dispatcher.filters.state import State, StatesGroup

class AdminStates(StatesGroup):
    WAITING_FOR_AD_IMAGE_DECISION = State()
    WAITING_FOR_AD_IMAGES = State()
    WAITING_FOR_AD_TEXT = State()
    WAITING_FOR_AD_BUTTONS = State()
    WAITING_FOR_AD_TITLE = State()
    WAITING_FOR_AD_INTERVAL = State()
    
    WAITING_FOR_CHANNEL_NAME = State()
    WAITING_FOR_CHANNEL_ID = State()
    WAITING_FOR_CHANNEL_URL = State()
    
    WAITING_FOR_CONTACT_NAME = State()
    WAITING_FOR_CONTACT_URL = State()
    
    WAITING_FOR_LINK_NEWBIE = State()
    WAITING_FOR_LINK_RULES = State()
    WAITING_FOR_LINK_SAFETY = State()
    WAITING_FOR_LINK_TERMS = State()
    WAITING_FOR_LINK_SERVICE = State()
    WAITING_FOR_LINK_HUAIAN = State()
    WAITING_FOR_LINK_GROUP = State()
    
    WAITING_FOR_BUTTON_TEXT = State()
    WAITING_FOR_BUTTON_URL = State()
    WAITING_FOR_BUTTON_PAGE = State()
    
    WAITING_FOR_KEYWORD_KEY = State()
    WAITING_FOR_KEYWORD_REPLY = State()
    
    WAITING_FOR_REPORT_CHANNEL = State()

    # Start Menu Wizard
    WAITING_FOR_START_TEXT = State()
    WAITING_FOR_START_TYPE = State()
    WAITING_FOR_START_VALUE = State()

class ReportStates(StatesGroup):
    WAITING_FOR_CONTENT = State()
