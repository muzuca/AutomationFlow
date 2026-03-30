import os
import pathlib
from dotenv import load_dotenv

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

EMAIL = os.getenv("FG_EMAIL")
SENHA = os.getenv("FG_SENHA")

EXE_PATH = os.getenv(
    "FG_EXE_PATH",
    r"C:\Users\vinic\AppData\Local\ferramentas_guru_v9\ferramentas-guru-v9.exe",
)

DEBUG_PORT_FG = int(os.getenv("FG_DEBUG_PORT", "9222"))
WAIT = int(os.getenv("FG_WAIT", "20"))
CHROMEDRIVER_PATH = str(PROJECT_ROOT / "chromedriver.exe")
DOWNLOAD_DIR = pathlib.Path(os.path.expanduser("~")) / "Downloads"
TESSERACT_PATH = os.getenv(
    "TESSERACT_PATH",
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
)

# Pasta para salvar prints de debug OCR
OCR_DEBUG_DIR = PROJECT_ROOT / "ocr_debug"
OCR_DEBUG_DIR.mkdir(exist_ok=True)