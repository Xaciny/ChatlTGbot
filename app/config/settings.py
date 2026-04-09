import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings:
    TOKEN: str = os.getenv('TOKEN')
    GROUP_ID: int = int(os.getenv('GROUP_ID'))
    
    # Пути
    WELCOME_FILE: Path = BASE_DIR / 'media' / 'welcome_message.txt'
    
    # База данных
    DB_HOST: str = os.getenv('DB_HOST', 'localhost')
    DB_PORT: str = os.getenv('DB_PORT', '5432')
    DB_NAME: str = os.getenv('DB_NAME', 'chatl_bot')
    DB_USER: str = os.getenv('DB_USER', 'chatl_user')
    DB_PASSWORD: str = os.getenv('DB_PASSWORD', 'change_me')

    # Time-webовские креды
    TIMEWEB_API_TOKEN: str = os.getenv('TIMEWEB_API_TOKEN', '')
    TIMEWEB_DAILY_COST: float = float(os.getenv('TIMEWEB_DAILY_COST', '50'))

    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

settings = Settings()