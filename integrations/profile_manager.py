# arquivo: integrations/profile_manager.py
# descricao: Gerenciador inteligente de perfis Chrome para cache de sessão.
# Cada conta Humble logada com sucesso tem seu perfil persistido em logs/perfis/<email_slug>/
# Na sincronização, perfis de contas que deixaram de existir são removidos automaticamente.
# Perfis de acessibilidade (Médico) também ficam em logs/perfis/medico/

from __future__ import annotations

import os
import re
import shutil
import threading
from pathlib import Path
from typing import Optional

from integrations.utils import _log

# Lock global para operações de perfil (evita race conditions entre threads)
_lock_perfis = threading.Lock()

# Diretório raiz de todos os perfis
PERFIS_DIR = Path("logs/perfis")


def _slugificar_email(email: str) -> str:
    """Converte email em slug seguro para nome de pasta.
    Ex: 'veoanti64359940@reyschnitzler2.asia' → 'veoanti64359940_reyschnitzler2_asia'
    """
    slug = email.strip().lower()
    slug = re.sub(r'[^a-z0-9]', '_', slug)
    slug = re.sub(r'_+', '_', slug).strip('_')
    return slug


def obter_caminho_perfil(email: str) -> Path:
    """Retorna o caminho do perfil para uma conta específica.
    Cria o diretório se não existir.
    """
    slug = _slugificar_email(email)
    caminho = PERFIS_DIR / slug
    caminho.mkdir(parents=True, exist_ok=True)
    return caminho


def obter_caminho_perfil_medico() -> Path:
    """Retorna o caminho do perfil da Unidade Médica (acessibilidade)."""
    caminho = PERFIS_DIR / "medico"
    caminho.mkdir(parents=True, exist_ok=True)
    return caminho


def perfil_existe(email: str) -> bool:
    """Verifica se já existe um perfil cacheado para esta conta."""
    slug = _slugificar_email(email)
    caminho = PERFIS_DIR / slug
    # Perfil existe se a pasta tem conteúdo (não basta existir vazia)
    return caminho.exists() and any(caminho.iterdir())


def conta_tem_sessao_valida(email: str) -> bool:
    """Verifica se a conta tem um perfil cacheado COM cookies de sessão.
    
    Usado pelo ACCOUNT_MODE=MULTI para filtrar contas que realmente
    podem ser usadas sem login interativo (sem risco de CAPTCHA).
    
    Returns:
        True se o perfil existe e tem arquivos de cookie.
        False se não existe, está vazio, ou não tem cookies.
    """
    slug = _slugificar_email(email)
    caminho = PERFIS_DIR / slug
    
    if not caminho.exists() or not any(caminho.iterdir()):
        return False
    
    # Verifica se tem pelo menos um arquivo de Cookies (prova de sessão)
    # O Chrome guarda cookies em Default/Cookies ou Profile 1/Cookies
    for subdir in caminho.iterdir():
        if subdir.is_dir():
            cookies_file = subdir / "Cookies"
            if cookies_file.exists() and cookies_file.stat().st_size > 0:
                return True
            # Alternativa: Network/Cookies
            net_cookies = subdir / "Network" / "Cookies"
            if net_cookies.exists() and net_cookies.stat().st_size > 0:
                return True
    
    # Cookies pode estar na raiz do perfil também
    root_cookies = caminho / "Default" / "Cookies"
    if root_cookies.exists() and root_cookies.stat().st_size > 0:
        return True
    
    return False


def preparar_perfis_workers(email: str, thread_ids: list[int]) -> None:
    """Copia o perfil base para diretórios de workers ANTES das threads iniciarem.
    
    Deve ser chamado no main thread (sequencial) para evitar race conditions.
    Cada worker terá uma cópia isolada do perfil com cookies/sessão.
    
    Se USE_PROFILE_CACHE=False, esta função é um no-op (workers usam perfil descartável).
    
    Args:
        email: Email da conta cujo perfil será copiado
        thread_ids: Lista de IDs das threads (ex: [1, 2])
    """
    # 🧹 Se cache de perfil está desligado, não tem nada pra copiar
    import os
    if os.getenv('USE_PROFILE_CACHE', 'True').strip().lower() in ('false', '0', 'no'):
        _log(f"🧹 USE_PROFILE_CACHE=False — perfis descartáveis, pulando cópia.", "PERFIL")
        return
    slug = _slugificar_email(email)
    caminho_base = PERFIS_DIR / slug
    
    if not caminho_base.exists() or not any(caminho_base.iterdir()):
        _log(f"⚠️ Perfil base vazio para {email[:20]}... — workers farão login fresco.", "PERFIL")
        return
    
    # 🔥 MATAR TODOS OS CHROME.EXE QUE USAM ESTE PERFIL (senão os file handles não soltam)
    _matar_chromes_do_perfil(str(caminho_base.resolve()))
    
    import time
    time.sleep(2)  # Dá tempo ao Windows para liberar os handles
    
    with _lock_perfis:
        for tid in thread_ids:
            caminho_thread = PERFIS_DIR / f"{slug}_t{tid}"
            
            # Limpa perfil antigo da thread (pode estar corrompido)
            if caminho_thread.exists():
                # Remove locks primeiro
                for lock_name in ["SingletonLock", "SingletonCookie", "SingletonSocket"]:
                    lock_file = caminho_thread / lock_name
                    if lock_file.exists():
                        try: lock_file.unlink()
                        except: pass
                shutil.rmtree(str(caminho_thread), ignore_errors=True)
            
            # Copia o perfil base com tolerância a falhas
            _copiar_perfil_resiliente(caminho_base, caminho_thread, tid, slug)


def _matar_chromes_do_perfil(caminho_perfil: str) -> None:
    """Mata TODOS os processos chrome.exe que usam este diretório de perfil.
    No Windows, subprocessos do Chrome (GPU, utility) mantêm file handles mesmo após driver.quit().
    """
    import subprocess
    
    try:
        # Busca PIDs de chrome.exe via WMIC que usam este caminho
        result = subprocess.run(
            ['wmic', 'process', 'where', 
             f"name='chrome.exe' AND CommandLine LIKE '%{caminho_perfil.replace(os.sep, os.sep + os.sep)}%'",
             'get', 'ProcessId'],
            capture_output=True, text=True, timeout=10
        )
        
        pids = []
        for line in result.stdout.strip().split('\n'):
            line = line.strip()
            if line.isdigit():
                pids.append(line)
        
        if pids:
            _log(f"🔪 Matando {len(pids)} processo(s) Chrome residual(is) do perfil...", "PERFIL")
            for pid in pids:
                subprocess.run(['taskkill', '/f', '/pid', pid], 
                             capture_output=True, timeout=5)
    except Exception:
        pass
    
    # ⚠️ REMOVIDO: Fallback nuclear 'taskkill /im chromedriver.exe' matava
    # TODOS os chromedriver do sistema, incluindo o Médico (Unidade Médica).
    # O WMIC acima já mata apenas os processos do perfil específico.


def _copiar_perfil_resiliente(origem: Path, destino: Path, tid: int, slug: str) -> None:
    """Copia perfil com retry para arquivos críticos e tolerância para não-críticos."""
    import time
    
    # Arquivos que NÃO precisam ser copiados (Chrome recria automaticamente)
    ignorar = shutil.ignore_patterns(
        "SingletonLock", "SingletonCookie", "SingletonSocket",
        "CrashpadMetrics-active.pma", "*.tmp", "*.log",
        "BrowserMetrics*", "Crashpad"
    )
    
    # Tentativa 1: cópia normal
    try:
        shutil.copytree(str(origem), str(destino), dirs_exist_ok=True, ignore=ignorar)
        _log(f"📋 Perfil copiado para Thread {tid}: {slug[:25]}...", "PERFIL")
        return
    except shutil.Error as e:
        # copytree com erros parciais — verifica se os críticos foram copiados
        arquivos_falhos = [item[0] for item in e.args[0]] if e.args else []
        criticos_falhos = [f for f in arquivos_falhos if 'Cookies' in f or 'Login Data' in f]
        
        if not criticos_falhos:
            _log(f"📋 Perfil copiado para Thread {tid} (com {len(arquivos_falhos)} arquivo(s) não-críticos ignorados): {slug[:25]}...", "PERFIL")
            return
        
        # Cookies/Login Data falharam — retry após espera
        _log(f"⏳ Arquivos críticos travados. Aguardando 3s para retry...", "PERFIL")
        time.sleep(3)
    except Exception as e:
        _log(f"⏳ Erro na cópia. Aguardando 3s para retry...", "PERFIL")
        time.sleep(3)
    
    # Tentativa 2: retry
    try:
        if destino.exists():
            shutil.rmtree(str(destino), ignore_errors=True)
        shutil.copytree(str(origem), str(destino), dirs_exist_ok=True, ignore=ignorar)
        _log(f"📋 Perfil copiado para Thread {tid} (retry): {slug[:25]}...", "PERFIL")
    except shutil.Error as e:
        arquivos_falhos = [item[0] for item in e.args[0]] if e.args else []
        _log(f"⚠️ Perfil copiado para Thread {tid} com {len(arquivos_falhos)} arquivo(s) falhos (pode funcionar): {slug[:25]}...", "PERFIL")
    except Exception as e:
        _log(f"⚠️ Falha ao copiar perfil para Thread {tid}: {e}", "PERFIL")


def obter_caminho_download_thread(thread_id: int = 0) -> Path:
    """Retorna um diretório de download exclusivo para cada thread.
    Evita conflitos de arquivos entre downloads paralelos.
    """
    caminho = Path(f"logs/downloads/thread_{thread_id}")
    caminho.mkdir(parents=True, exist_ok=True)
    return caminho


def limpar_perfis_obsoletos(emails_ativos: list[str]) -> int:
    """Remove perfis de contas que não estão mais na lista ativa do Humble.
    
    Args:
        emails_ativos: Lista de emails que existem atualmente no .env
        
    Returns:
        Número de perfis removidos
    """
    if not PERFIS_DIR.exists():
        return 0
    
    slugs_ativos = {_slugificar_email(e) for e in emails_ativos}
    slugs_ativos.add("medico")  # Nunca remove o perfil médico
    
    removidos = 0
    
    with _lock_perfis:
        for pasta in PERFIS_DIR.iterdir():
            if pasta.is_dir() and pasta.name not in slugs_ativos:
                try:
                    # Tenta remover o SingletonLock antes (Chrome pode ter travado)
                    lock_file = pasta / "SingletonLock"
                    if lock_file.exists():
                        try:
                            lock_file.unlink()
                        except:
                            pass
                    
                    shutil.rmtree(str(pasta), ignore_errors=True)
                    _log(f"🧹 Perfil obsoleto removido: {pasta.name}", "PERFIL")
                    removidos += 1
                except Exception as e:
                    _log(f"⚠️ Não foi possível remover perfil {pasta.name}: {e}", "PERFIL")
    
    if removidos > 0:
        _log(f"🧹 {removidos} perfil(is) obsoleto(s) removido(s).", "PERFIL")
    
    return removidos


def desbloquear_perfil(email: str) -> None:
    """Remove o SingletonLock de um perfil para permitir reuso após crash.
    Necessário quando o Chrome não fechou limpo na sessão anterior.
    """
    slug = _slugificar_email(email)
    caminho = PERFIS_DIR / slug
    
    for lock_name in ["SingletonLock", "SingletonCookie", "SingletonSocket"]:
        lock_file = caminho / lock_name
        if lock_file.exists():
            try:
                lock_file.unlink()
            except:
                pass


def desbloquear_perfil_medico() -> None:
    """Remove locks do perfil médico."""
    caminho = PERFIS_DIR / "medico"
    for lock_name in ["SingletonLock", "SingletonCookie", "SingletonSocket"]:
        lock_file = caminho / lock_name
        if lock_file.exists():
            try:
                lock_file.unlink()
            except:
                pass


def listar_perfis_ativos() -> list[str]:
    """Retorna a lista de slugs de perfis existentes."""
    if not PERFIS_DIR.exists():
        return []
    return [p.name for p in PERFIS_DIR.iterdir() if p.is_dir()]


def invalidar_perfil(email: str) -> None:
    """Deleta o perfil cacheado de uma conta que falhou.
    Isso garante que na próxima tentativa, o Chrome inicia limpo
    sem tentar carregar um perfil corrompido.
    """
    slug = _slugificar_email(email)
    caminho = PERFIS_DIR / slug
    
    if not caminho.exists():
        return
    
    with _lock_perfis:
        try:
            # Remove locks primeiro
            for lock_name in ["SingletonLock", "SingletonCookie", "SingletonSocket"]:
                lock_file = caminho / lock_name
                if lock_file.exists():
                    try:
                        lock_file.unlink()
                    except:
                        pass
            
            shutil.rmtree(str(caminho), ignore_errors=True)
            _log(f"🗑️ Perfil corrompido removido: {email[:25]}...", "PERFIL")
        except Exception as e:
            _log(f"⚠️ Não foi possível invalidar perfil {email[:25]}: {e}", "PERFIL")
