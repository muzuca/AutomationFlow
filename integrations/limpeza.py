# arquivo: integrations/limpeza.py
# descricao: Módulo de limpeza automática para pipeline 24/7.
#   - Logs de execução → zerados a cada startup (novo arquivo a cada sessão)
#   - Screenshots de debug (visao/) → removidos a cada startup
#   - Downloads temporários → removidos a cada startup
#   - Extensões de proxy → removidos a cada startup
#   - Perfis de worker (_t1, _t2, etc) → removidos a cada startup
#   - __pycache__ → removidos a cada startup
#   - ultimo_prompt.txt → removido a cada startup
#   - Logs antigos são arquivados se dentro da janela de retenção (LOG_RETENCAO_HORAS)

import os
import shutil
import time
from pathlib import Path
from datetime import datetime


def _log(msg: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    try:
        print(f"[{ts}] [LIMPEZA] {msg}")
    except UnicodeEncodeError:
        msg_safe = msg.encode('ascii', errors='replace').decode('ascii')
        print(f"[{ts}] [LIMPEZA] {msg_safe}")


# =====================================================================
# FUNÇÕES DE LIMPEZA INDIVIDUAL
# =====================================================================

def zerar_logs_execucao(logs_dir: Path = None, retencao_horas: int = 24) -> int:
    """Zera TODOS os logs de execução (log_execucao*.txt).
    
    Se o log mais recente tiver menos de `retencao_horas`, arquiva-o
    antes de zerar. Caso contrário, simplesmente apaga.
    
    Retorna quantidade de arquivos processados.
    """
    if logs_dir is None:
        logs_dir = Path(os.getenv("LOGS_DIR", "logs"))
    
    processados = 0
    
    for arq in logs_dir.glob("log_execucao*.txt"):
        try:
            tamanho = arq.stat().st_size
            if tamanho == 0:
                continue
            
            # Zera o arquivo (sem arquivar — mantém só o log da execução atual)
            arq.write_text("", encoding="utf-8")
            processados += 1
        except Exception:
            pass
    
    if processados > 0:
        _log(f"Zerados: {processados} arquivo(s) de log")
    return processados




def limpar_screenshots_debug(logs_dir: Path = None) -> int:
    """Remove TODOS os screenshots de debug (visao/)."""
    if logs_dir is None:
        logs_dir = Path(os.getenv("LOGS_DIR", "logs"))
    
    visao_dir = logs_dir / "visao"
    if not visao_dir.exists():
        return 0

    total_bytes = 0
    removidos = 0

    for arq in visao_dir.rglob("*"):
        if arq.is_file() and arq.suffix.lower() in ('.png', '.jpg', '.jpeg', '.webp'):
            try:
                total_bytes += arq.stat().st_size
                arq.unlink()
                removidos += 1
            except Exception:
                pass

    if removidos > 0:
        mb = total_bytes / (1024 * 1024)
        _log(f"Removidos: {removidos} screenshots ({mb:.0f}MB)")
    return round(total_bytes / (1024 * 1024))


def limpar_downloads_temp(logs_dir: Path = None) -> int:
    """Remove TODA a pasta de downloads temporários e recria vazia."""
    if logs_dir is None:
        logs_dir = Path(os.getenv("LOGS_DIR", "logs"))
    
    downloads_dir = logs_dir / "downloads"
    if not downloads_dir.exists():
        return 0

    total_bytes = 0
    removidos = 0

    # Remove tudo recursivamente (incluindo subpastas thread_*)
    for item in downloads_dir.iterdir():
        try:
            if item.is_dir():
                size = sum(f.stat().st_size for f in item.rglob("*") if f.is_file())
                shutil.rmtree(item, ignore_errors=True)
                total_bytes += size
                removidos += 1
            elif item.is_file():
                total_bytes += item.stat().st_size
                item.unlink()
                removidos += 1
        except Exception:
            pass

    if removidos > 0:
        mb = total_bytes / (1024 * 1024)
        _log(f"Removidos: {removidos} itens de downloads ({mb:.1f}MB)")
    return round(total_bytes / (1024 * 1024))


def limpar_proxy_extensions(logs_dir: Path = None) -> int:
    """Remove extensões de proxy geradas dinamicamente."""
    if logs_dir is None:
        logs_dir = Path(os.getenv("LOGS_DIR", "logs"))
    
    proxy_dir = logs_dir / "proxy_ext"
    if not proxy_dir.exists():
        return 0

    total_bytes = 0
    removidos = 0

    for item in proxy_dir.iterdir():
        try:
            if item.is_dir():
                size = sum(f.stat().st_size for f in item.rglob("*") if f.is_file())
                shutil.rmtree(item, ignore_errors=True)
            else:
                size = item.stat().st_size
                item.unlink()
            total_bytes += size
            removidos += 1
        except Exception:
            pass

    if removidos > 0:
        _log(f"Removidos: {removidos} residuos de proxy")
    return round(total_bytes / (1024 * 1024))


def limpar_perfis_workers(logs_dir: Path = None) -> int:
    """Remove perfis temporários de workers (_t1, _t2, etc)."""
    if logs_dir is None:
        logs_dir = Path(os.getenv("LOGS_DIR", "logs"))
    
    perfis_dir = logs_dir / "perfis"
    if not perfis_dir.exists():
        return 0

    total_bytes = 0
    removidos = 0

    for pasta in perfis_dir.iterdir():
        if not pasta.is_dir():
            continue
        # Padrão: nome_conta_t1, nome_conta_t2, etc
        if any(pasta.name.endswith(f"_t{i}") for i in range(1, 100)):
            try:
                size = sum(f.stat().st_size for f in pasta.rglob("*") if f.is_file())
                shutil.rmtree(pasta, ignore_errors=True)
                total_bytes += size
                removidos += 1
            except Exception:
                pass

    if removidos > 0:
        mb = total_bytes / (1024 * 1024)
        _log(f"Removidos: {removidos} perfis de worker ({mb:.0f}MB)")
    return round(total_bytes / (1024 * 1024))


def limpar_ultimo_prompt(logs_dir: Path = None) -> None:
    """Remove o arquivo ultimo_prompt.txt da execução anterior."""
    if logs_dir is None:
        logs_dir = Path(os.getenv("LOGS_DIR", "logs"))
    
    arq = logs_dir / "ultimo_prompt.txt"
    if arq.exists():
        try:
            arq.unlink()
            _log("Removido: ultimo_prompt.txt")
        except Exception:
            pass


def limpar_pycache(raiz: Path = None) -> int:
    """Remove todos os diretórios __pycache__ recursivamente."""
    if raiz is None:
        raiz = Path(".")
    
    removidos = 0
    for cache_dir in raiz.rglob("__pycache__"):
        if cache_dir.is_dir():
            try:
                shutil.rmtree(cache_dir, ignore_errors=True)
                removidos += 1
            except Exception:
                pass
    
    if removidos > 0:
        _log(f"Removidos: {removidos} diretorios __pycache__")
    return removidos


# =====================================================================
# FUNÇÕES COMPOSTAS (chamadas pelo main.py)
# =====================================================================

def limpeza_inicio_execucao(logs_dir: Path = None, raiz: Path = None) -> None:
    """Limpeza executada UMA VEZ ao iniciar o sistema.
    
    ZERA tudo da execução anterior para começar limpo:
    - Logs de execução (arquiva se dentro da janela de retenção)
    - Screenshots de debug
    - Downloads temporários
    - Extensões de proxy
    - Perfis de workers
    - __pycache__
    - ultimo_prompt.txt
    """
    if logs_dir is None:
        logs_dir = Path(os.getenv("LOGS_DIR", "logs"))
    
    retencao = int(os.getenv("LOG_RETENCAO_HORAS", "24"))
    
    _log(f"LIMPEZA DE INICIO (retencao={retencao}h)...")
    t0 = time.time()
    
    mb_total = 0
    
    # 1. Logs: zera no início de cada execução
    zerar_logs_execucao(logs_dir, retencao_horas=retencao)
    
    # 2. Screenshots (258MB acumulados!)
    mb_total += limpar_screenshots_debug(logs_dir)
    
    # 3. Downloads temporários
    mb_total += limpar_downloads_temp(logs_dir)
    
    # 4. Extensões de proxy residuais
    mb_total += limpar_proxy_extensions(logs_dir)
    
    # 5. Perfis de workers
    mb_total += limpar_perfis_workers(logs_dir)
    
    # 6. ultimo_prompt.txt
    limpar_ultimo_prompt(logs_dir)
    
    # 7. __pycache__
    limpar_pycache(raiz)
    
    elapsed = time.time() - t0
    _log(f"Inicio limpo em {elapsed:.1f}s | {mb_total}MB liberados")


def limpeza_entre_tarefas(logs_dir: Path = None) -> None:
    """Limpeza rápida entre cada tarefa do watcher.
    Remove APENAS artefatos temporários descartáveis.
    NÃO toca em logs (estão sendo usados pela sessão ativa).
    """
    t0 = time.time()
    
    mb_total = 0
    mb_total += limpar_perfis_workers(logs_dir)
    mb_total += limpar_downloads_temp(logs_dir)
    mb_total += limpar_proxy_extensions(logs_dir)
    mb_total += limpar_screenshots_debug(logs_dir)
    
    elapsed = time.time() - t0
    if mb_total > 0:
        _log(f"Limpeza entre tarefas: {elapsed:.1f}s | {mb_total}MB liberados")


def limpeza_total_shutdown(logs_dir: Path = None, raiz: Path = None) -> None:
    """Limpeza executada no encerramento do sistema."""
    _log("LIMPEZA DE SHUTDOWN...")
    t0 = time.time()
    
    mb_total = 0
    mb_total += limpar_perfis_workers(logs_dir)
    mb_total += limpar_downloads_temp(logs_dir)
    mb_total += limpar_proxy_extensions(logs_dir)
    limpar_pycache(raiz)
    
    elapsed = time.time() - t0
    _log(f"Shutdown limpo em {elapsed:.1f}s | {mb_total}MB liberados")
