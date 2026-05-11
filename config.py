# arquivo: config.py
# descricao: Configuração centralizada do projeto. Carrega .env e expõe Settings (dataclass).
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from dotenv import load_dotenv

# ── Carrega .env da raiz do projeto ──────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
_env_path = BASE_DIR / ".env"
load_dotenv(_env_path, override=True)


def _bool(val: str | None, default: bool = False) -> bool:
    if val is None:
        return default
    return val.strip().lower() in ("true", "1", "yes")


def _int(val: str | None, default: int = 0) -> int:
    if val is None:
        return default
    try:
        return int(val.strip())
    except (ValueError, AttributeError):
        return default


# ── Conta Google (dataclass) ─────────────────────────────────────────────────
@dataclass(frozen=True)
class GoogleAccount:
    email: str
    password: str
    prioridade: int = 0


def _carregar_contas() -> List[GoogleAccount]:
    """Carrega contas do .env no formato HUMBLE_EMAIL_N / HUMBLE_PASSWORD_N."""
    contas: List[GoogleAccount] = []
    
    emails_encontrados: dict[int, str] = {}
    senhas_encontradas: dict[int, str] = {}
    
    for chave, valor in os.environ.items():
        # Formato PRIORIDADE: HUMBLE_EMAIL_PRIORIDADE_0=...
        m = re.match(r"HUMBLE_EMAIL_PRIORIDADE_(\d+)$", chave)
        if m:
            idx = int(m.group(1))
            emails_encontrados[idx] = valor.strip()
            continue
        
        # Formato simples: HUMBLE_EMAIL_1=...
        m = re.match(r"HUMBLE_EMAIL_(\d+)$", chave)
        if m:
            idx = int(m.group(1))
            emails_encontrados[idx] = valor.strip()
            continue
    
    for chave, valor in os.environ.items():
        m = re.match(r"HUMBLE_PASSWORD_PRIORIDADE_(\d+)$", chave)
        if m:
            idx = int(m.group(1))
            senhas_encontradas[idx] = valor.strip()
            continue
        
        m = re.match(r"HUMBLE_PASSWORD_(\d+)$", chave)
        if m:
            idx = int(m.group(1))
            senhas_encontradas[idx] = valor.strip()
            continue
    
    for idx in sorted(emails_encontrados.keys()):
        email = emails_encontrados[idx]
        senha = senhas_encontradas.get(idx, "")
        if email and senha:
            contas.append(GoogleAccount(email=email, password=senha, prioridade=idx))
    
    return contas


# ── Settings (dataclass principal) ───────────────────────────────────────────
@dataclass(frozen=True)
class Settings:
    base_dir: Path
    
    # Diretórios
    videos_base_dir: str
    downloads_dir: str
    ffmpeg_path: str
    logs_dir: str
    
    # URLs
    google_login_url: str
    gemini_url: str
    gemini_selfhealing_url: str
    gemini_captcha_url: str
    flow_url: str
    humble_doc_id: str
    
    # Navegador
    chrome_headless: bool
    use_proxy: bool
    proxy_url: str
    use_profile_cache: bool
    use_credits: bool
    disable_screenshots: bool
    chrome_implicit_wait: int
    chrome_page_load_timeout: int
    browser_engine: str  # UNDETECT | CHROMEDRIVER | MISTO
    
    # Paralelismo
    cenas_em_paralelo: int
    conversoes_1080p_em_paralelo: int
    
    # Produção
    videos_por_personagem: int
    
    # Flow
    modelo_imagem_flow: str
    
    # Sistema
    account_mode: str  # SINGLE | MULTI | AUTO
    sync_humble: bool
    log_retention_hours: int
    tentativas_por_conta: int
    limite_falhas_ban: int
    intervalo_manutencao_horas: float
    
    # Watcher (gera até atingir o alvo, depois monitora)
    max_videos_por_personagem: int
    watcher_poll_minutos: int
    
    # Ultima conta que logou com sucesso (persistida no .env)
    last_account_index: str
    
    # Contas
    accounts: List[GoogleAccount] = field(default_factory=list)


def get_settings() -> Settings:
    """Constrói Settings a partir do .env (carregado no topo do módulo)."""
    contas = _carregar_contas()
    
    return Settings(
        base_dir=BASE_DIR,
        
        # Diretórios
        videos_base_dir=os.getenv("VIDEOS_BASE_DIR", "G:/Meu Drive/Videos"),
        downloads_dir=os.getenv("DOWNLOADS_DIR", "logs/downloads"),
        ffmpeg_path=os.getenv("FFMPEG_PATH", "ffmpeg.exe"),
        logs_dir=os.getenv("LOGS_DIR", "logs"),
        
        # URLs
        google_login_url=os.getenv("GOOGLE_LOGIN_URL", "https://accounts.google.com/"),
        gemini_url=os.getenv("GEMINI_URL", "https://gemini.google.com/app/pt"),
        gemini_selfhealing_url=os.getenv("GEMINI_SELFHEALING_URL", "https://gemini.google.com/app/ce6a5110e188a415"),
        gemini_captcha_url=os.getenv("GEMINI_CAPTCHA_URL", "https://gemini.google.com/app/bb6cbeb2a8123972"),
        flow_url=os.getenv("FLOW_URL", "https://labs.google/fx/pt/tools/flow"),
        humble_doc_id=os.getenv("HUMBLE_DOC_ID", ""),
        
        # Navegador
        chrome_headless=_bool(os.getenv("CHROME_HEADLESS"), default=True),
        use_proxy=_bool(os.getenv("USE_PROXY"), default=False),
        proxy_url=os.getenv("PROXY_URL", "").strip(),
        use_profile_cache=_bool(os.getenv("USE_PROFILE_CACHE"), default=True),
        use_credits=_bool(os.getenv("USE_CREDITS"), default=False),
        disable_screenshots=_bool(os.getenv("DISABLE_SCREENSHOTS"), default=False),
        chrome_implicit_wait=_int(os.getenv("CHROME_IMPLICIT_WAIT"), default=5),
        chrome_page_load_timeout=_int(os.getenv("CHROME_PAGE_LOAD_TIMEOUT"), default=60),
        browser_engine=os.getenv("BROWSER_ENGINE", "UNDETECT").strip().upper(),
        
        # Paralelismo
        cenas_em_paralelo=_int(os.getenv("CENAS_EM_PARALELO"), default=1),
        conversoes_1080p_em_paralelo=_int(os.getenv("CONVERSOES_1080P_EM_PARALELO"), default=1),
        
        # Produção
        videos_por_personagem=_int(os.getenv("VIDEOS_POR_PERSONAGEM"), default=6),
        
        # Flow
        modelo_imagem_flow=os.getenv("MODELO_IMAGEM_FLOW", "Nano Banana Pro").strip(),
        
        # Sistema
        account_mode=os.getenv("ACCOUNT_MODE", "SINGLE").strip().upper(),
        sync_humble=_bool(os.getenv("SYNC_HUMBLE"), default=False),
        log_retention_hours=_int(os.getenv("LOG_RETENTION_HOURS"), default=12),
        tentativas_por_conta=_int(os.getenv("TENTATIVAS_POR_CONTA"), default=4),
        limite_falhas_ban=_int(os.getenv("LIMITE_FALHAS_BAN"), default=5),
        intervalo_manutencao_horas=float(os.getenv("INTERVALO_MANUTENCAO_HORAS", "0")),
        
        # Watcher
        max_videos_por_personagem=_int(os.getenv("MAX_VIDEOS_POR_PERSONAGEM"), default=15),
        watcher_poll_minutos=_int(os.getenv("WATCHER_POLL_MINUTOS"), default=2),
        
        # Ultima conta valida
        last_account_index=os.getenv("LAST_ACCOUNT_INDEX", "").strip(),
        
        # Contas
        accounts=contas,
    )
