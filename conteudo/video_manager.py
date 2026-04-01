"""
Gerenciador de vídeos pós-geração:
  1. Concatena os arquivos .mp4 gerados em um único vídeo final
  2. Remove os arquivos individuais
  3. Move o vídeo final para a pasta do Google Drive do personagem
"""

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


def _gerar_nome_final(signo: str, tema: str) -> str:
    """Gera nome do arquivo final com timestamp."""
    agora = datetime.now().strftime("%Y%m%d_%H%M%S")
    signo_ = signo.replace(" ", "").replace("/", "")
    tema_ = tema.replace(" ", "_").replace("/", "")[:30]
    return f"{VIDEO_PREFIX}_{signo_}_{tema_}_{agora}.mp4"


def _criar_lista_ffmpeg(arquivos: list[Path], lista_path: Path):
    """Cria o arquivo de lista no formato exigido pelo ffmpeg concat."""
    with open(lista_path, "w", encoding="utf-8") as f:
        for arq in arquivos:
            f.write(f"file '{arq.as_posix()}'\n")


def _concatenar_ffmpeg(arquivos: list[Path], saida: Path) -> bool:
    """
    Usa ffmpeg para concatenar sem re-encode (copy).
    Requer que todos os vídeos tenham o mesmo codec/resolução.
    """
    lista_path = saida.parent / "_lista_concat.txt"
    _criar_lista_ffmpeg(arquivos, lista_path)

    cmd = [
        FFMPEG_PATH,
        "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(lista_path),
        "-c", "copy",
        str(saida),
    ]

    print(f"  → Executando ffmpeg para concatenar {len(arquivos)} arquivos...")
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=120,
        )
        lista_path.unlink(missing_ok=True)

        if result.returncode != 0:
            erro = result.stderr.decode("utf-8", errors="replace")[-500:]
            print(f"  ❌ ffmpeg retornou erro:\n{erro}")
            return False

        print(f"  ✔ Vídeo concatenado: {saida.name} ({saida.stat().st_size // 1024} KB)")
        return True

    except subprocess.TimeoutExpired:
        print("  ❌ ffmpeg excedeu o tempo limite de 120s.")
        lista_path.unlink(missing_ok=True)
        return False
    except FileNotFoundError:
        print(f"  ❌ ffmpeg não encontrado em '{FFMPEG_PATH}'. Configure FFMPEG_PATH no .env")
        lista_path.unlink(missing_ok=True)
        return False


def _remover_arquivos(arquivos: list[Path]):
    """Remove os arquivos individuais após concatenação."""
    for arq in arquivos:
        try:
            arq.unlink()
            print(f"  🗑 Removido: {arq.name}")
        except Exception as e:
            print(f"  ⚠ Não consegui remover {arq.name}: {e}")


def _mover_para_gdrive(arquivo: Path, destino_dir: Path) -> Path | None:
    """Move o vídeo final para a pasta do Google Drive."""
    try:
        print(f"  ℹ Destino Google Drive: {destino_dir}")
        destino_dir.mkdir(parents=True, exist_ok=True)
        destino = destino_dir / arquivo.name

        shutil.move(str(arquivo), str(destino))
        print(f"  ✔ Vídeo movido para: {destino}")
        return destino

    except Exception as e:
        print(f"  ❌ Erro ao mover para o Google Drive: {e}")
        return None


def processar_videos(
    arquivos: list[str | Path],
    signo: str,
    tema: str,
    gdrive_dir: Path | None = None,
) -> Path | None:
    """
    Concatena, limpa e move os vídeos gerados.
    """
    print("\n[VIDEO MANAGER] Iniciando processamento dos vídeos...")

    arquivos = [Path(a) for a in arquivos]
    destino_drive = gdrive_dir or GDRIVE_DIR

    faltando = [a for a in arquivos if not a.exists()]
    if faltando:
        print(f"  ❌ Arquivos não encontrados: {[str(a) for a in faltando]}")
        return None

    print(f"  ℹ {len(arquivos)} arquivo(s) para processar:")
    for i, a in enumerate(arquivos, 1):
        print(f"     {i}. {a.name}")

    if len(arquivos) == 1:
        print("  ℹ Apenas 1 arquivo — pulando concatenação.")
        video_final = arquivos[0].parent / _gerar_nome_final(signo, tema)
        arquivos[0].rename(video_final)
    else:
        video_final = DOWNLOADS_DIR / _gerar_nome_final(signo, tema)
        ok = _concatenar_ffmpeg(arquivos, video_final)
        if not ok:
            print("  ❌ Falha na concatenação. Arquivos originais mantidos.")
            return None
        _remover_arquivos(arquivos)

    caminho_final = _mover_para_gdrive(video_final, destino_drive)

    if caminho_final:
        print(f"\n  ✅ Processamento concluído!")
        print(f"     Arquivo final: {caminho_final}")
    else:
        print(f"\n  ⚠ Vídeo gerado mas não movido. Está em: {video_final}")

    return caminho_final