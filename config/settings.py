import os
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, ".env"), override=True)

DB_PATH = os.environ.get("DB_PATH", os.path.join(BASE_DIR, "database", "travel_wallet.db"))
LINE_CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET", "")
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
LIFF_ID = os.environ.get("LIFF_ID", "")
STREAMLIT_URL = os.environ.get("STREAMLIT_URL", "http://localhost:8501")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
