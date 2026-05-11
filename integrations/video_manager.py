# arquivo: integrations/video_manager.py
# descricao: Gerenciador de vídeos pós-geração.
# Etapa 1: Concatena as cenas parciais em 720p (mantendo o áudio original intacto) para gerar as variantes.
# Etapa 2: Faz o upscaling (1080p) controlado por semáforo (N conversões simultâneas via THREADS_1080P).

import os
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import List
from integrations.utils import _log as log_base


def _log(msg: str):
    log_base(msg, prefixo="VIDEO_MANAGER")

# =============================================================================
# 🔒 SEMÁFORO DE CONVERSÃO 1080P (CPU-BOUND)
# Controla quantas conversões FFmpeg rodam em paralelo.
# Inicializado com 1 slot por padrão; main.py ajusta via configurar_semaforo_1080p()
# =============================================================================
_semaforo_1080p = threading.Semaphore(1)


def configurar_semaforo_1080p(max_paralelo: int = 1) -> None:
    """Reconfigura o semáforo de conversão 1080p.
    Chamado pelo main.py com o valor de THREADS_1080P do .env.
    """
    global _semaforo_1080p
    max_paralelo = max(1, max_paralelo)  # Mínimo 1
    _semaforo_1080p = threading.Semaphore(max_paralelo)
    _log(f"🔒 Semáforo 1080p configurado: {max_paralelo} conversão(ões) simultânea(s)")


def _criar_lista_ffmpeg(arquivos: List[Path], lista_path: Path):
    with open(lista_path, "w", encoding="utf-8") as f:
        for arq in arquivos:
            f.write(f"file '{arq.as_posix()}'\n")

def concatenar_cenas_720p(arquivos_mp4: List[Path], saida_path: Path) -> bool:
    """Junta as cenas originais (720p) mantendo o áudio original intacto."""
    _log(f"Concatenando {len(arquivos_mp4)} cenas em 720p...")
    lista_path = saida_path.parent / f"_lista_{saida_path.stem}.txt"
    _criar_lista_ffmpeg(arquivos_mp4, lista_path)
    
    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(lista_path), "-c", "copy", str(saida_path)
    ]
    
    try:
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60, check=True)
        lista_path.unlink(missing_ok=True)
        return True
    except Exception as e:
        _log(f"❌ Erro na concatenação 720p: {e}")
        return False

def converter_para_1080p(entrada: Path, saida: Path) -> bool:
    """Faz o upscaling do vídeo vencedor para 1080p vertical.
    🔒 SERIALIZADO VIA SEMÁFORO: Controla a quantidade máxima de conversões
    FFmpeg rodando em paralelo para não explodir a CPU.
    """
    _log(f"⏳ Aguardando slot de conversão 1080p ({entrada.name})...")
    
    with _semaforo_1080p:
        _log(f"🔄 Fazendo upscale do vídeo para 1080p: {entrada.name}")
        cmd = [
            "ffmpeg", "-y", "-i", str(entrada),
            "-vf", "scale=1080:1920,setdar=9/16",
            "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-pix_fmt", "yuv420p", "-c:a", "copy", str(saida)
        ]
        
        try:
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=300, check=True)
            _log(f"✔ Upscale concluído: {saida.name}")
            return True
        except Exception as e:
            _log(f"❌ Erro no upscale: {e}")
            return False

def limpar_arquivos_temporarios(arquivos: List[Path]):
    """Remove os arquivos individuais após a conclusão."""
    for arq in arquivos:
        try:
            if arq.exists():
                arq.unlink()
                _log(f"🗑 Removido arquivo parcial: {arq.name}")
        except Exception as e:
            _log(f"⚠ Não consegui remover {arq.name}: {e}")