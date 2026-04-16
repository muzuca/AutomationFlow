"""
arquivo: config.py
descrição: Centraliza configurações, variáveis de ambiente (.env) e caminhos essenciais (Selenium, FFmpeg, pastas e contas).
"""

import os
import pathlib

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent

CHROMEDRIVER_PATH = str(PROJECT_ROOT / "chromedriver.exe")
FFMPEG_PATH = os.getenv("FFMPEG_PATH", str(PROJECT_ROOT / "ffmpeg.exe"))

DOWNLOAD_DIR = pathlib.Path(os.path.expanduser("~")) / "Downloads"

VIDEOS_BASE_DIR = pathlib.Path(
    os.getenv("VIDEOS_BASE_DIR", r"G:\Meu Drive\Videos")
)
VIDEOS_BASE_DIR.mkdir(parents=True, exist_ok=True)

def get_personagem_output_dir(personagem_id: str) -> pathlib.Path:
    pasta = VIDEOS_BASE_DIR / personagem_id
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta

WAIT = int(os.getenv("FG_WAIT", "20"))
HUMBLE_FLOW_URL = os.getenv("HUMBLE_FLOW_URL", "https://labs.google/fx/pt/tools/flow")

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