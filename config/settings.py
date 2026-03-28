import os
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, ".env"), override=True)

def _resolve_db_path() -> str:
    configured = os.environ.get("DB_PATH", "")
    if configured:
        parent = os.path.dirname(configured)
        # 若指定目錄不存在且無法建立，fallback 到本地路徑
        try:
            os.makedirs(parent, exist_ok=True)
            return configured
        except OSError:
            pass
    return os.path.join(BASE_DIR, "database", "travel_wallet.db")

DB_PATH = _resolve_db_path()
LINE_CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET", "")
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
LIFF_ID = os.environ.get("LIFF_ID", "")
STREAMLIT_URL = os.environ.get("STREAMLIT_URL", "http://localhost:8501")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
