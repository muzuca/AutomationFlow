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

from automation_flow.core.config.settings import (
    PROJECT_ROOT,
    FFMPEG_PATH as SETTINGS_FFMPEG_PATH,
    get_personagem_output_dir,
)

# .env da raiz do projeto
ENV_PATH = PROJECT_ROOT / ".env"
load_dotenv(ENV_PATH, override=True)

# FFMPEG ----------------------------------------------------------------------

# Permite override via .env, mas centralizado no settings.py
_ffmpeg_env = os.getenv("FFMPEG_PATH", SETTINGS_FFMPEG_PATH)
FFMPEG_PATH = Path(_ffmpeg_env)

DOWNLOADS_DIR = Path(os.getenv("DOWNLOADS_DIR", str(Path.home() / "Downloads")))

print(f"[VIDEO_MANAGER] ENV_PATH={ENV_PATH}")
print(f"[VIDEO_MANAGER] FFMPEG_PATH={FFMPEG_PATH}")
print(f"[VIDEO_MANAGER] DOWNLOADS_DIR={DOWNLOADS_DIR}")


# ── Helpers de identificação/prefixo ─────────────────────────────────────────

def _ident_personagem(personagem: str) -> str:
    """
    Normaliza o identificador/prefixo a partir do nome lógico do personagem.
    'AnaCartomante'  -> 'AnaCartomante'
    'CoachEspiritual'-> 'CoachEspiritual'
    """
    return "".join(ch for ch in personagem if ch.isalnum())


def _prefixo_personagem(personagem: str) -> str:
    """
    Prefixo padrão do arquivo final, derivado do personagem.
    Você pode customizar aqui se quiser nomes diferentes do ID.
    """
    return _ident_personagem(personagem)


# ── Helpers internos ─────────────────────────────────────────────────--------

def _gerar_nome_final(prefixo: str, signo: str | None, tema: str) -> str:
    """Gera nome do arquivo final com timestamp."""
    agora = datetime.now().strftime("%Y%m%d_%H%M%S")

    signo_ = (signo or "").replace(" ", "").replace("/", "") or "SemSigno"
    tema_ = tema.replace(" ", "_").replace("/", "")[:30]

    return f"{prefixo}_{signo_}_{tema_}_{agora}.mp4"


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
        str(FFMPEG_PATH),
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


def _mover_para_destino(arquivo: Path, destino_dir: Path) -> Path | None:
    """Move o vídeo final para a pasta destino (Google Drive base + personagem)."""
    try:
        print(f"  ℹ Destino final: {destino_dir}")
        destino_dir.mkdir(parents=True, exist_ok=True)
        destino = destino_dir / arquivo.name

        shutil.move(str(arquivo), str(destino))
        print(f"  ✔ Vídeo movido para: {destino}")
        return destino

    except Exception as e:
        print(f"  ❌ Erro ao mover vídeo final: {e}")
        return None


# ── API principal ────────────────────────────────────────────────────────────

def processar_videos(
    personagem: str,
    arquivos: list[str | Path],
    tema: str,
    signo: str | None = None,
    gdrive_dir_override: Path | None = None,
    prefixo_override: str | None = None,
) -> Path | None:
    """
    Concatena, limpa e move os vídeos gerados para o personagem informado.

    Args:
        personagem: nome lógico do personagem (ex: "AnaCartomante", "CoachEspiritual")
        arquivos: lista de paths dos .mp4 gerados
        tema: tema final usado no roteiro (vai para o nome do arquivo)
        signo: signo (ou None, para personagens que não usam signo)
        gdrive_dir_override: se informado, sobrescreve a pasta padrão derivada do personagem
        prefixo_override: se informado, sobrescreve o prefixo padrão

    Returns:
        Path final do arquivo na pasta do personagem (ou None em caso de erro)
    """
    print("\n[VIDEO MANAGER] Iniciando processamento dos vídeos...")

    arquivos = [Path(a) for a in arquivos]

    destino_base = gdrive_dir_override or get_personagem_output_dir(personagem)
    prefixo = prefixo_override or _prefixo_personagem(personagem)

    faltando = [a for a in arquivos if not a.exists()]
    if faltando:
        print(f"  ❌ Arquivos não encontrados: {[str(a) for a in faltando]}")
        return None

    print(f"  ℹ Personagem: {personagem}")
    print(f"  ℹ Pasta base do personagem: {destino_base}")
    print(f"  ℹ {len(arquivos)} arquivo(s) para processar:")
    for i, a in enumerate(arquivos, 1):
        print(f"     {i}. {a.name}")

    if len(arquivos) == 1:
        print("  ℹ Apenas 1 arquivo — pulando concatenação.")
        video_final = arquivos[0].parent / _gerar_nome_final(prefixo, signo, tema)
        arquivos[0].rename(video_final)
    else:
        video_final = DOWNLOADS_DIR / _gerar_nome_final(prefixo, signo, tema)
        ok = _concatenar_ffmpeg(arquivos, video_final)
        if not ok:
            print("  ❌ Falha na concatenação. Arquivos originais mantidos.")
            return None
        _remover_arquivos(arquivos)

    caminho_final = _mover_para_destino(video_final, destino_base)

    if caminho_final:
        print(f"\n  ✅ Processamento concluído!")
        print(f"     Arquivo final: {caminho_final}")
    else:
        print(f"\n  ⚠ Vídeo gerado mas não movido. Está em: {video_final}")

    return caminho_final