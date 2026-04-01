import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / ".env"
load_dotenv(ENV_PATH, override=True)

_ffmpeg_env = os.getenv("FFMPEG_PATH", "ffmpeg.exe")
FFMPEG_PATH = str(PROJECT_ROOT / _ffmpeg_env) if not os.path.isabs(_ffmpeg_env) else _ffmpeg_env

GDRIVE_DIR_RAW = os.getenv("GDRIVE_ANA_CARTOMANTE", r"G:\Meu Drive\Videos\AnaCartomante")
GDRIVE_DIR = Path(GDRIVE_DIR_RAW)
DOWNLOADS_DIR = Path(os.getenv("DOWNLOADS_DIR", str(Path.home() / "Downloads")))
VIDEO_PREFIX = os.getenv("VIDEO_PREFIX", "AnaCartomante")

print(f"[VIDEO_MANAGER] ENV_PATH={ENV_PATH}")
print(f"[VIDEO_MANAGER] GDRIVE_ANA_CARTOMANTE={GDRIVE_DIR_RAW}")