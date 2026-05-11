# arquivo: integrations/pid_manager.py
# descricao: Sistema robusto de rastreamento de PIDs de Chrome/ChromeDriver.
# Garante que TODOS os processos abertos pelo script são registrados em arquivo
# e eliminados no shutdown (Ctrl+C, atexit, ou início da próxima execução).
#
# Estratégia:
# 1. Cada Chrome/ChromeDriver criado tem seus PIDs registrados em meus_pids.txt
# 2. No Ctrl+C / atexit, todos os PIDs registrados são mortos via taskkill /T
# 3. No INÍCIO de cada execução, PIDs da execução anterior são limpos
# 4. O arquivo é sobrescrito (não append) a cada atualização para evitar lixo

from __future__ import annotations

import os
import atexit
import signal
import subprocess
import threading
from pathlib import Path
from datetime import datetime

_PID_FILE = Path(__file__).resolve().parent.parent / "meus_pids.txt"
_lock = threading.Lock()
_pids: set[int] = set()
_shutdown_called = False


def _log_pid(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}][PID-MGR] {msg}")


# ── Registro ─────────────────────────────────────────────────────────────────

def registrar(pid: int | None):
    """Registra um PID para rastreamento. Thread-safe."""
    if not pid:
        return
    with _lock:
        _pids.add(pid)
        _salvar_arquivo()


def registrar_driver(driver) -> None:
    """Extrai e registra TODOS os PIDs de um driver Selenium (ChromeDriver + Chrome browser)."""
    # 1. PID do processo chromedriver
    try:
        cd_pid = driver.service.process.pid
        registrar(cd_pid)
    except Exception:
        cd_pid = None

    # 2. PID do browser Chrome (via capabilities)
    try:
        caps = getattr(driver, 'capabilities', {}) or {}
        chrome_info = caps.get('chrome', {})
        
        # userDataDir approach: pega pelo processo que tem o user-data-dir
        browser_pid = chrome_info.get('chromedriverProcessId')
        if browser_pid:
            registrar(browser_pid)
    except Exception:
        pass
    
    # 3. PIDs filhos do chromedriver (chrome.exe spawned by chromedriver)
    if cd_pid:
        try:
            result = subprocess.run(
                ['wmic', 'process', 'where',
                 f'ParentProcessId={cd_pid}',
                 'get', 'ProcessId', '/format:csv'],
                capture_output=True, text=True, timeout=5
            )
            for line in result.stdout.splitlines():
                line = line.strip()
                if not line or 'ProcessId' in line or 'Node' in line:
                    continue
                parts = line.split(',')
                child_pid = parts[-1].strip()
                if child_pid.isdigit():
                    registrar(int(child_pid))
        except Exception:
            pass


def desregistrar(pid: int | None):
    """Remove um PID do rastreamento (após close_driver bem-sucedido)."""
    if not pid:
        return
    with _lock:
        _pids.discard(pid)
        _salvar_arquivo()


# ── Persistência ─────────────────────────────────────────────────────────────

def _salvar_arquivo():
    """Sobrescreve o arquivo com os PIDs atuais (chamado dentro do lock)."""
    try:
        _PID_FILE.write_text(
            "\n".join(str(p) for p in sorted(_pids)) + "\n",
            encoding="utf-8"
        )
    except Exception:
        pass


def _carregar_arquivo() -> set[int]:
    """Lê PIDs do arquivo (da execução anterior)."""
    pids = set()
    try:
        if _PID_FILE.exists():
            for line in _PID_FILE.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.isdigit():
                    pids.add(int(line))
    except Exception:
        pass
    return pids


# ── Kill ─────────────────────────────────────────────────────────────────────

def matar_todos(motivo: str = "shutdown"):
    """Mata TODOS os PIDs registrados (em memória + arquivo). Thread-safe."""
    global _shutdown_called
    if _shutdown_called:
        return
    _shutdown_called = True
    
    with _lock:
        pids_memoria = set(_pids)
    
    pids_arquivo = _carregar_arquivo()
    todos = pids_memoria | pids_arquivo
    
    if not todos:
        return
    
    _log_pid(f"🧹 Matando {len(todos)} processo(s) [{motivo}]...")
    mortos = 0
    
    for pid in todos:
        try:
            # /T mata a árvore inteira de processos filhos
            result = subprocess.run(
                ['taskkill', '/f', '/pid', str(pid), '/T'],
                capture_output=True, timeout=5
            )
            if result.returncode == 0:
                mortos += 1
        except Exception:
            pass
    
    # Fallback: mata chromedriver.exe órfãos
    try:
        subprocess.run(
            ['taskkill', '/F', '/IM', 'chromedriver.exe'],
            capture_output=True, timeout=5
        )
    except Exception:
        pass
    
    # Limpa arquivo e memória
    with _lock:
        _pids.clear()
    try:
        _PID_FILE.unlink(missing_ok=True)
    except Exception:
        pass
    
    if mortos > 0:
        _log_pid(f"✅ {mortos} processo(s) eliminados.")


def matar_pid(pid: int):
    """Mata um PID específico e remove do rastreamento."""
    try:
        subprocess.run(
            ['taskkill', '/f', '/pid', str(pid), '/T'],
            capture_output=True, timeout=5
        )
    except Exception:
        pass
    desregistrar(pid)


def limpar_execucao_anterior():
    """Chamada no INÍCIO do script — mata PIDs órfãos da execução anterior."""
    global _shutdown_called
    _shutdown_called = False  # Reset para nova execução
    
    pids_antigos = _carregar_arquivo()
    if not pids_antigos:
        return
    
    _log_pid(f"🔍 Encontrados {len(pids_antigos)} PID(s) da execução anterior. Limpando...")
    mortos = 0
    
    for pid in pids_antigos:
        try:
            result = subprocess.run(
                ['taskkill', '/f', '/pid', str(pid), '/T'],
                capture_output=True, timeout=5
            )
            if result.returncode == 0:
                mortos += 1
        except Exception:
            pass
    
    # Também mata chromedriver órfãos
    try:
        subprocess.run(
            ['taskkill', '/F', '/IM', 'chromedriver.exe'],
            capture_output=True, timeout=5
        )
    except Exception:
        pass
    
    # Limpa o arquivo
    try:
        _PID_FILE.unlink(missing_ok=True)
    except Exception:
        pass
    
    if mortos > 0:
        _log_pid(f"✅ {mortos} processo(s) órfão(s) eliminados.")
    else:
        _log_pid("✅ Nenhum processo órfão ativo encontrado.")


def contar_registrados() -> int:
    """Retorna quantos PIDs estão sendo rastreados."""
    with _lock:
        return len(_pids)


# ── Signal Handlers (Ctrl+C / SIGTERM) ───────────────────────────────────────

def _signal_handler(sig, frame):
    print("\n\n⚠️ Ctrl+C detectado! Encerrando e matando processos Chrome...")
    matar_todos(motivo="Ctrl+C")
    
    # Fallback nuclear: garante ZERO chrome/chromedriver (mesmo se matar_todos falhou)
    try:
        subprocess.run(['taskkill', '/F', '/IM', 'chromedriver.exe'],
                       capture_output=True, timeout=5)
    except Exception:
        pass
    
    # Mata Chrome por perfil (logs/perfis) via WMIC
    try:
        perfis_dir = str(Path("logs/perfis").resolve()).replace("\\", "\\\\")
        result = subprocess.run(
            ['wmic', 'process', 'where',
             f"name='chrome.exe' AND CommandLine LIKE '%{perfis_dir}%'",
             'get', 'ProcessId'],
            capture_output=True, text=True, timeout=10,
        )
        for line in result.stdout.strip().split('\n'):
            pid_str = line.strip()
            if pid_str.isdigit():
                try:
                    subprocess.run(['taskkill', '/f', '/pid', pid_str, '/T'],
                                   capture_output=True, timeout=5)
                except Exception:
                    pass
    except Exception:
        pass
    
    os._exit(0)  # Força saída imediata


def instalar_handlers():
    """Instala handlers de Ctrl+C e atexit. Chamar UMA VEZ no início do script."""
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)
    atexit.register(lambda: matar_todos(motivo="atexit"))
