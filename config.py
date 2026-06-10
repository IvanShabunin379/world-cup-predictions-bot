import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
API_FOOTBALL_KEY = os.getenv("API_FOOTBALL_KEY")

VANYA_TELEGRAM_ID = int(os.getenv("VANYA_TELEGRAM_ID", "0"))
NIK_TELEGRAM_ID = int(os.getenv("NIK_TELEGRAM_ID", "0"))

PRIVATE_LEAGUE_USERS = {
    "vanya": VANYA_TELEGRAM_ID,
    "nik": NIK_TELEGRAM_ID,
}

MOSCOW_TZ = "Europe/Moscow"

# League IDs (populated after first run)
PRIVATE_LEAGUE_NAME = "Братья"
PUBLIC_LEAGUE_NAME = "Весенние Зори"
