# settings.py
import os
import pathlib

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[3]

EMAIL = os.getenv("FG_EMAIL")
SENHA = os.getenv("FG_SENHA")

EXE_PATH = os.getenv(
    "FG_EXE_PATH",
    r"C:\Users\vinic\AppData\Local\ferramentas_guru_v9\ferramentas-guru-v9.exe",
)

DEBUG_PORT_FG = int(os.getenv("FG_DEBUG_PORT", "9222"))
WAIT = int(os.getenv("FG_WAIT", "20"))
CHROMEDRIVER_PATH = str(PROJECT_ROOT / "chromedriver.exe")

FFMPEG_PATH = os.getenv(
    "FFMPEG_PATH",
    str(PROJECT_ROOT / "ffmpeg.exe"),
)

DOWNLOAD_DIR = pathlib.Path(os.path.expanduser("~")) / "Downloads"

TESSERACT_PATH = os.getenv(
    "TESSERACT_PATH",
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
)

OCR_DEBUG_DIR = PROJECT_ROOT / "ocr_debug"
OCR_DEBUG_DIR.mkdir(exist_ok=True)

VIDEOS_BASE_DIR = pathlib.Path(
    os.getenv("VIDEOS_BASE_DIR", r"G:\Meu Drive\Videos")
)
VIDEOS_BASE_DIR.mkdir(parents=True, exist_ok=True)

def get_personagem_output_dir(personagem_id: str) -> pathlib.Path:
    pasta = VIDEOS_BASE_DIR / personagem_id
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta

def carregar_contas_humble() -> list[dict]:
    contas = []
    idx = 1

    while True:
        email = os.getenv(f"HUMBLE_EMAIL_{idx}")
        senha = os.getenv(f"HUMBLE_PASSWORD_{idx}")

        if not email and not senha:
            break

        if email and senha:
            contas.append({
                "indice": idx,
                "email": email,
                "senha": senha,
            })

        idx += 1

    return contas

HUMBLE_ACCOUNTS = carregar_contas_humble()
HUMBLE_FLOW_URL = os.getenv("HUMBLE_FLOW_URL", "https://labs.google/fx/pt/tools/flow")