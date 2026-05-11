# arquivo: integrations/browser.py
# descricao: cria e configura o navegador Chrome com preferências de download, timeouts e opções para reduzir ruído visual no terminal...
from __future__ import annotations

import os
import sys
import socket
import zipfile
import re
import shutil
import random
import string
from pathlib import Path
from subprocess import CREATE_NO_WINDOW # Necessário para esconder a janela do driver

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

from config import Settings
from integrations.utils import _log, registrar_pid_processo
from integrations import pid_manager
import threading
import logging
import sys

# ── Suprime "Task was destroyed but it is pending" do pproxy ──────────────────
# O pproxy cria tasks asyncio para cada conexão. Quando o Chrome é fechado,
# essas tasks ficam pendentes e o GC do Python 3.14 imprime diretamente no stderr.
# É noise cosmético — não afeta nada. Filtramos no stderr.
class _StderrFilter:
    def __init__(self, original):
        self._original = original
    def write(self, msg):
        if 'Task was destroyed' not in msg:
            self._original.write(msg)
    def flush(self):
        self._original.flush()
    def __getattr__(self, name):
        return getattr(self._original, name)

sys.stderr = _StderrFilter(sys.stderr)


def _resolver_engine(settings: Settings, thread_id: int = 0) -> str:
    """Decide qual engine usar para esta thread.
    
    CHROMEDRIVER → sempre ChromeDriver patcheado
    UNDETECT     → sempre undetected-chromedriver
    MISTO        → alterna: threads pares=UNDETECT, ímpares=CHROMEDRIVER
    """
    engine = getattr(settings, 'browser_engine', 'UNDETECT').upper()
    if engine == 'MISTO':
        escolhido = 'UNDETECT' if thread_id % 2 == 0 else 'CHROMEDRIVER'
        _log(f"🔀 MISTO: Thread {thread_id} → {escolhido}")
        return escolhido
    if engine in ('UNDETECT', 'CHROMEDRIVER'):
        return engine
    _log(f"⚠️ BROWSER_ENGINE='{engine}' inválido. Usando UNDETECT.")
    return 'UNDETECT'

# =========================================================================
# 🛡️ CHROMEDRIVER PATCHEADO — Remove a variável $cdc_ do binário
# A variável $cdc_asdjfkewiuhgiuw_ é injetada pelo ChromeDriver no DOM.
# É o sinal #1 que o Google usa para detectar Selenium/automação.
# Nenhuma evasão via JavaScript resolve isso — precisa patchear o binário.
# =========================================================================
_chromedriver_patcheado: str | None = None
_lock_patch = threading.Lock()


def _obter_chromedriver_patcheado() -> str:
    """Retorna o path de um ChromeDriver com a variável $cdc_ removida.
    
    1. Baixa/localiza o ChromeDriver via webdriver-manager (usa cache)
    2. Copia para logs/drivers_isolados/ (não altera o original)
    3. Patcha o binário: substitui '$cdc_' por string aleatória
    4. Retorna o path do binário patcheado (reutilizado em todas as chamadas)
    """
    global _chromedriver_patcheado
    
    with _lock_patch:
        if _chromedriver_patcheado and Path(_chromedriver_patcheado).exists():
            return _chromedriver_patcheado
        
        # 1. Resolve o path original (webdriver-manager cache)
        original = ChromeDriverManager().install()
        _log(f"🔧 ChromeDriver original: {original}")
        
        # 2. Copia para pasta isolada
        destino_dir = Path("logs/drivers_isolados")
        destino_dir.mkdir(parents=True, exist_ok=True)
        destino = destino_dir / Path(original).name
        
        # Sempre copia fresco para garantir patch limpo
        try:
            shutil.copy2(original, str(destino))
        except shutil.SameFileError:
            pass
        
        # 3. Patcha o binário
        _patchear_cdc(destino)
        
        _chromedriver_patcheado = str(destino)
        _log(f"🛡️ ChromeDriver PATCHEADO (anti-$cdc_): {destino}")
        return _chromedriver_patcheado


def _patchear_cdc(chromedriver_path: Path) -> None:
    """Substitui todas as ocorrências de '$cdc_' no binário por string aleatória.
    
    O ChromeDriver cria variáveis JS como 'cdc_adoQpoasnfa76pfcZLmcfl_' no DOM.
    Scripts de detecção procuram por 'cdc_' no prefixo.
    Substituímos o identificador inteiro por string aleatória de mesmo tamanho.
    """
    import re as _re
    
    with open(chromedriver_path, 'rb') as f:
        conteudo = f.read()
    
    # Procura o padrão REAL: cdc_ seguido de identificador alfanumérico
    # Formato: cdc_adoQpoasnfa76pfcZLmcfl (sem $ na frente no ChromeDriver 148+)
    padrao_regex = rb'cdc_[a-zA-Z0-9]{10,30}'
    matches = list(set(_re.findall(padrao_regex, conteudo)))
    
    if not matches:
        # Fallback: tenta com $ na frente (versões mais antigas)
        padrao_regex = rb'\$cdc_[a-zA-Z0-9]{10,30}'
        matches = list(set(_re.findall(padrao_regex, conteudo)))
    
    if not matches:
        _log("✅ ChromeDriver já está limpo (sem cdc_).")
        return
    
    conteudo_patcheado = conteudo
    total_patches = 0
    
    for match in matches:
        # Gera substituto de MESMO TAMANHO com caracteres aleatórios
        # Mantém a estrutura: xxx_<random> para não quebrar o parser
        tam = len(match)
        prefixo = ''.join(random.choices(string.ascii_lowercase, k=4)).encode()
        sufixo = ''.join(random.choices(string.ascii_lowercase + string.digits, k=tam - 5)).encode()
        substituto = prefixo + b'_' + sufixo
        substituto = substituto[:tam]  # Garante mesmo tamanho
        
        count = conteudo_patcheado.count(match)
        conteudo_patcheado = conteudo_patcheado.replace(match, substituto)
        total_patches += count
        _log(f"🔨 Patch: {match[:25].decode()}... → {substituto[:25].decode()}... ({count}x)")
    
    with open(chromedriver_path, 'wb') as f:
        f.write(conteudo_patcheado)
    
    _log(f"🔨 Total: {total_patches} substituição(ões) em {len(matches)} padrão(ões) cdc_")


def _limpar_locks_perfil(caminho_perfil: Path) -> None:
    """Remove lock files que o Chrome deixa quando é morto via taskkill.
    Sem isso, o próximo Chrome falha com 'cannot connect to chrome'."""
    locks = ['SingletonLock', 'SingletonSocket', 'SingletonCookie']
    for lock in locks:
        lock_path = caminho_perfil / lock
        try:
            if lock_path.exists():
                lock_path.unlink(missing_ok=True)
        except Exception:
            pass


def _encontrar_porta_livre() -> int:
    """Encontra uma porta TCP livre no sistema."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]


def criar_extensao_proxy(proxy_url: str, folder: str = "logs/proxy_ext", thread_id: int = 0) -> str | None:
    """Cria uma extensão temporária para autenticar o proxy nativamente no Chrome."""
    try:
        # Extrai dados: http://user:pass@host:port
        auth_proxy = re.findall(r'http://(.*):(.*)@(.*):(.*)', proxy_url)
        if not auth_proxy:
            return None
        
        user, password, host, port = auth_proxy[0]
        
        if not os.path.exists(folder):
            os.makedirs(folder)

        manifest_json = """
        {
            "version": "1.0.0",
            "manifest_version": 2,
            "name": "Chrome Proxy",
            "permissions": [
                "proxy", "tabs", "unlimitedStorage", "storage", "<all_urls>",
                "webRequest", "webRequestBlocking"
            ],
            "background": { "scripts": ["background.js"] },
            "minimum_chrome_version":"22.0.0"
        }
        """

        background_js = f"""
        var config = {{
                mode: "fixed_servers",
                rules: {{
                  singleProxy: {{
                    scheme: "http",
                    host: "{host}",
                    port: parseInt({port})
                  }},
                  bypassList: ["localhost"]
                }}
              }};
        chrome.proxy.settings.set({{value: config, scope: "regular"}}, function() {{}});
        chrome.webRequest.onAuthRequired.addListener(
                function(details) {{
                    return {{
                        authCredentials: {{
                            username: "{user}",
                            password: "{password}"
                        }}
                    }};
                }},
                {{urls: ["<all_urls>"]}},
                ['blocking']
        );
        """
        
        plugin_file = os.path.join(folder, f"proxy_auth_plugin_t{thread_id}.zip")
        with zipfile.ZipFile(plugin_file, 'w') as zp:
            zp.writestr("manifest.json", manifest_json)
            zp.writestr("background.js", background_js)
        
        return os.path.abspath(plugin_file)
    except Exception as e:
        _log(f"🚨 Erro ao criar extensão de proxy: {e}")
        return None


# =========================================================================
# 🌐 PROXY BRIDGE LOCAL — pproxy como relay
# Chrome 148+ NÃO suporta extensões de proxy em headless (nem MV2 nem MV3).
# Solução: proxy local sem auth (localhost:PORTA) → upstream com auth.
# Chrome usa --proxy-server=localhost:PORTA (funciona em --headless=new).
# =========================================================================
_proxy_bridge_started = False
_proxy_bridge_port: int | None = None
_proxy_bridge_lock = threading.Lock()


def _iniciar_proxy_bridge(upstream_url: str) -> int:
    """Inicia proxy bridge local via pproxy.
    
    Retorna a porta local do proxy bridge.
    Singleton: só inicia uma vez (reutiliza entre threads).
    """
    global _proxy_bridge_started, _proxy_bridge_port
    
    with _proxy_bridge_lock:
        if _proxy_bridge_started and _proxy_bridge_port:
            return _proxy_bridge_port
        
        import asyncio
        import pproxy
        
        # Encontra porta livre
        porta = _encontrar_porta_livre()
        
        # Parse upstream: protocolo://user:pass@host:port
        # Suporta http:// e socks5://
        match = re.match(r'(https?|socks5)://(.*):(.*)@(.*):(.*)', upstream_url)
        if not match:
            raise ValueError(f"URL de proxy inválida: {upstream_url}")
        
        proto, user, password, host, port = match.groups()
        
        # Mapeia protocolo para formato pproxy
        # pproxy usa: http, socks5, socks4, ss, etc.
        pproxy_proto = proto.replace('https', 'http')  # pproxy não tem 'https'
        
        def _run_bridge():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Suprime ConnectionResetError e "Task was destroyed" do pproxy (noise inofensivo)
            import warnings
            warnings.filterwarnings("ignore", message=".*Task was destroyed.*")
            
            def _exception_handler(loop, context):
                exc = context.get('exception')
                msg = context.get('message', '')
                if isinstance(exc, (ConnectionResetError, ConnectionAbortedError, OSError)):
                    return  # Silencia erros de conexão fechada
                if 'Task was destroyed' in msg:
                    return  # Silencia tasks órfãs do pproxy
                loop.default_exception_handler(context)
            loop.set_exception_handler(_exception_handler)
            
            async def _serve():
                # Servidor local: aceita HTTP e SOCKS5 (sem auth)
                server = pproxy.Server(f"http+socks5://0.0.0.0:{porta}")
                # Upstream: roteia com auth para o proxy remoto
                remote = pproxy.Connection(f"{pproxy_proto}://{host}:{port}#{user}:{password}")
                await server.start_server({"rserver": [remote]})
                while True:
                    await asyncio.sleep(3600)
            
            loop.run_until_complete(_serve())
        
        t = threading.Thread(target=_run_bridge, daemon=True, name="proxy-bridge")
        t.start()
        
        import time
        time.sleep(1.5)  # Aguarda servidor subir
        
        _proxy_bridge_started = True
        _proxy_bridge_port = porta
        _log(f"🌐 Proxy bridge ({pproxy_proto.upper()}): localhost:{porta} → {host}:{port}")
        return porta


def build_chrome_options(settings: Settings, thread_id: int = 0, email_perfil: str | None = None) -> Options:
    downloads_dir = str(Path(settings.downloads_dir).resolve())

    options = Options()
    options.add_argument('--start-maximized')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--disable-notifications')
    options.add_argument('--disable-popup-blocking')
    options.add_argument('--no-default-browser-check')
    options.add_argument('--disable-infobars')
    options.add_argument('--log-level=3')
    options.add_argument('--silent')
    options.add_argument('--disable-logging')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument("--mute-audio")
    # Anti-detecção: remove flags que denunciam automação
    options.add_experimental_option('excludeSwitches', ['enable-automation'])
    options.add_experimental_option('useAutomationExtension', False)
    
    # =========================================================================
    # 🛡️ ANTI-VAZAMENTO DE IP (WebRTC, DNS, SafeBrowsing, APIs Google)
    # Quando proxy ativo, NADA pode sair pelo IP real.
    # =========================================================================
    options.add_argument('--disable-features='
        'OptimizationGuideModelDownloading,'
        'OptimizationHints,'
        'MediaRouter,'
        'AutofillServerCommunication,'
        'WebRtcHideLocalIpsWithMdns,'
        'TranslateUI,'
        'SafeBrowsingEnhancedProtection'
    )
    # WebRTC: impede vazamento do IP real via STUN/TURN
    options.add_argument('--enforce-webrtc-ip-permission-check')
    options.add_argument('--webrtc-ip-handling-policy=disable_non_proxied_udp')
    # DNS: força resolução via proxy (não usa DNS do sistema)
    options.add_argument('--host-resolver-rules=MAP * ~NOTFOUND , EXCLUDE localhost')
    # Desabilita chamadas de telemetria que podem vazar IP
    options.add_argument('--disable-background-networking')
    options.add_argument('--disable-breakpad')
    options.add_argument('--disable-component-update')
    options.add_argument('--disable-domain-reliability')
    options.add_argument('--disable-sync')
    options.add_argument('--metrics-recording-only')
    options.add_argument('--no-first-run')

    # --- PROXY: usa PROXY_URL do .env e configura bridge local ---
    _proxy_url = None
    if settings.use_proxy and settings.proxy_url:
        _proxy_url = settings.proxy_url
        
        # Inicia proxy bridge local (singleton — reutiliza entre threads)
        bridge_port = _iniciar_proxy_bridge(_proxy_url)
        
        # SOCKS5: Chrome usa socks5:// para tunelar TUDO (HTTP, HTTPS, DNS, WS)
        if _proxy_url.startswith('socks5://'):
            options.add_argument(f'--proxy-server=socks5://localhost:{bridge_port}')
            # DNS via SOCKS5 (resolve no servidor proxy, não local)
            options.add_argument('--host-resolver-rules=')  # Remove regra anterior
        else:
            options.add_argument(f'--proxy-server=http://localhost:{bridge_port}')
        
        # Extrai host:port para log (suporta http:// e socks5://)
        auth_match = re.findall(r'(?:https?|socks5)://.*@(.*):(.*)', _proxy_url)
        host_port = f"{auth_match[0][0]}:{auth_match[0][1]}" if auth_match else _proxy_url
        _log(f"🌐 Proxy T{thread_id}: {host_port} via bridge localhost:{bridge_port} (conta: {email_perfil[:20] + '...' if email_perfil else 'N/A'})")

    if settings.chrome_headless:
        options.add_argument('--headless=new')
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--disable-gpu')

    prefs = {
        'download.default_directory': downloads_dir,
        'download.prompt_for_download': False,
        'download.directory_upgrade': True,
        'safebrowsing.enabled': False,
        'safebrowsing.disable_download_protection': True,
        # WebRTC: desabilita enumeração de IPs locais
        'webrtc.ip_handling_policy': 'disable_non_proxied_udp',
        'webrtc.multiple_routes_enabled': False,
        'webrtc.nonproxied_udp_enabled': False,
        'profile.default_content_setting_values.notifications': 2,
        'credentials_enable_service': False,
        'profile.password_manager_enabled': False,
        
        # --- A MÁGICA PARA MATAR O POPUP NO HEADLESS=FALSE ---
        'profile.default_content_settings.popups': 0,
        'protocol_handler.excluded_schemes': {
            'afc': True,
            'mailto': True,
            'ms-windows-store': True,
            'intent': True,
            'about': True,
            'unknown': True
        }
    }
    options.add_experimental_option('prefs', prefs)

    return options, _proxy_url


def _criar_driver_undetect(options: Options, settings: Settings, porta: int | None, thread_id: int):
    """Cria driver via undetected-chromedriver. Constrói opções LIMPAS para máxima evasão."""
    import undetected_chromedriver as uc
    
    _log("🛡️ Iniciando Chrome via undetected-chromedriver (evasão nativa)")
    
    uc_options = uc.ChromeOptions()
    
    # =========================================================================
    # ⚠️ REGRA DE OURO: NÃO copiar argumentos do Selenium Options!
    # O UC faz evasão nativa. Flags como --disable-blink-features, --headless=new,
    # excludeSwitches, useAutomationExtension SABOTAM a evasão.
    # Passamos APENAS o mínimo necessário para funcionalidade.
    # =========================================================================
    
    # Argumentos SEGUROS que não denunciam automação
    _safe_args = [
        '--start-maximized',
        '--disable-notifications',
        '--disable-popup-blocking',
        '--no-default-browser-check',
        '--mute-audio',
        '--log-level=3',
        '--silent',
        '--disable-logging',
    ]
    
    # Headless: UC precisa de window-size explícito (senão abre 800x600 — flag de bot)
    if settings.chrome_headless:
        _safe_args.append('--window-size=1920,1080')
    
    for arg in _safe_args:
        uc_options.add_argument(arg)
    
    # Porta de debug isolada por thread
    if porta:
        uc_options.add_argument(f'--remote-debugging-port={porta}')
    
    # Perfil + PROXY — copiar do Options original
    # ⚠️ MÍNIMO NECESSÁRIO: UC tem evasão própria, flags extras causam tab crash!
    _copy_prefixes = (
        '--user-data-dir=',
        '--profile-directory=',
        '--disk-cache-size=',
        '--proxy-server=',                    # 🔑 CRÍTICO: sem isso o proxy é ignorado!
        '--host-resolver-rules=',             # DNS via proxy
    )
    for arg in options.arguments:
        if arg.startswith(_copy_prefixes):
            uc_options.add_argument(arg)
    
    # Headless: UC precisa de --disable-gpu (sem isso, renderer crasha)
    if settings.chrome_headless:
        uc_options.add_argument('--disable-gpu')
    
    # Prefs (downloads, notificações, etc.)
    try:
        exp_opts = options.experimental_options
        if 'prefs' in exp_opts:
            uc_options.add_experimental_option('prefs', exp_opts['prefs'])
    except Exception:
        pass
    
    # Extensões (proxy) — UC suporta extensões normalmente
    try:
        for ext in options.extensions:
            uc_options.add_extension(ext)
    except Exception:
        pass
    
    # =========================================================================
    # 🚀 Criação do driver UC
    # headless: UC tem implementação PRÓPRIA (não usar --headless=new)
    # use_subprocess: True para evitar zombie processes
    # version_main: None = auto-detect da versão do Chrome instalado
    # =========================================================================
    is_headless = settings.chrome_headless
    
    driver = uc.Chrome(
        options=uc_options,
        headless=is_headless,
        use_subprocess=True,
        version_main=None,
    )
    
    _log(f"🛡️ UC ativo | headless={is_headless} | porta={porta}")
    
    return driver


def _criar_driver_chromedriver(options: Options, porta: int | None):
    """Cria driver via ChromeDriver patcheado (abordagem original com $cdc_ removido)."""
    _log("🛡️ Iniciando Chrome via ChromeDriver PATCHEADO (anti-detecção)")
    
    if porta:
        options.add_argument(f'--remote-debugging-port={porta}')
    
    chromedriver_path = _obter_chromedriver_patcheado()
    service = Service(chromedriver_path)
    service.creation_flags = CREATE_NO_WINDOW
    driver = webdriver.Chrome(service=service, options=options)
    return driver


def _registrar_pids(driver) -> None:
    """Registra PIDs do Chrome e do chromedriver para shutdown limpo."""
    pid_manager.registrar_driver(driver)


def create_driver(settings: Settings, perfil_acessibilidade: bool = False, 
                   email_perfil: str | None = None, thread_id: int = 0,
                   usar_perfil_base: bool = False):
    """Cria um driver Chrome com suporte a perfis cacheados.
    
    Modos de operação:
      1. email_perfil definido → Usa perfil cacheado da conta (sessão persistente)
      2. perfil_acessibilidade=True → Usa perfil médico (logs/perfis/medico/)
      3. Nenhum dos dois → Modo incógnito (legado)
    
    Args:
        settings: Configurações do projeto
        perfil_acessibilidade: Se True, usa o perfil da Unidade Médica
        email_perfil: Email da conta para reusar perfil cacheado
        thread_id: ID da thread para isolar diretório de download
    """
    from integrations.profile_manager import (
        obter_caminho_perfil, obter_caminho_perfil_medico,
        desbloquear_perfil, desbloquear_perfil_medico
    )
    
    # Passamos a usar a função build_chrome_options
    options, _proxy_url = build_chrome_options(settings, thread_id=thread_id, email_perfil=email_perfil)
    
    # ==========================================================
    # CONFIGURAÇÃO DE PERFIL (PRIORIDADE: email > médico > incógnito)
    # USE_PROFILE_CACHE=False → contas Humble NÃO usam perfil cacheado
    # O Médico SEMPRE usa perfil (precisa de sessão persistente)
    # ==========================================================
    if perfil_acessibilidade:
        desbloquear_perfil_medico()
        caminho_perfil = obter_caminho_perfil_medico().resolve()
        _limpar_locks_perfil(caminho_perfil)
        options.add_argument(f'--user-data-dir={str(caminho_perfil)}')
        options.add_argument('--profile-directory=Default')
        _log("🏥 Carregando Unidade Médica via PERFIL REAL (Sessão persistente).")
    elif email_perfil and settings.use_profile_cache:
        desbloquear_perfil(email_perfil)
        caminho_perfil_base = obter_caminho_perfil(email_perfil).resolve()
        
        if thread_id > 0 and not usar_perfil_base:
            caminho_perfil = caminho_perfil_base.parent / f"{caminho_perfil_base.name}_t{thread_id}"
            caminho_perfil.mkdir(parents=True, exist_ok=True)
        else:
            caminho_perfil = caminho_perfil_base
        
        _limpar_locks_perfil(caminho_perfil)
        options.add_argument(f'--user-data-dir={str(caminho_perfil)}')
        options.add_argument('--profile-directory=Default')
        _log(f"🔑 Carregando perfil cacheado para: {email_perfil[:20]}... (Thread {thread_id})")
    elif email_perfil and not settings.use_profile_cache:
        import tempfile
        temp_profile = Path(tempfile.mkdtemp(prefix=f"chrome_t{thread_id}_"))
        options.add_argument(f'--user-data-dir={str(temp_profile)}')
        options.add_argument('--profile-directory=Default')
        _log(f"🧹 Perfil descartável para: {email_perfil[:20]}... (Thread {thread_id}) — USE_PROFILE_CACHE=False")
    else:
        options.add_argument('--incognito')
        _log("🤖 Carregando Operador Principal via MODO INCOGNITO.")

    # ==========================================================
    # OTIMIZAÇÃO ADICIONAL
    # ==========================================================
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-application-cache')
    options.add_argument('--disk-cache-size=0')

    # 🔌 Remote Debugging: CADA driver recebe sua própria porta (isolamento total)
    porta = None
    if not perfil_acessibilidade and not usar_perfil_base:
        porta = _encontrar_porta_livre()
        _log(f"🔌 Remote Debugging T{thread_id} na porta {porta}")
    
    # =========================================================================
    # 🚀 CRIAÇÃO DO DRIVER — decide engine por thread
    # Proxy já está configurado via --proxy-server=localhost:BRIDGE_PORT
    # (pproxy bridge lida com autenticação — funciona em headless=new)
    # =========================================================================
    engine = _resolver_engine(settings, thread_id=thread_id)
    
    if engine == 'UNDETECT':
        driver = _criar_driver_undetect(options, settings, porta, thread_id)
    else:
        driver = _criar_driver_chromedriver(options, porta)

    # 📝 REGISTRA PIDs DO CHROME — chromedriver + browser (para shutdown limpo)
    _registrar_pids(driver)

    # Força tamanho da janela
    driver.set_window_size(1920, 1080)
    
    # =========================================================================
    # 🌐 VERIFICAÇÃO DE IP — confirma que o tráfego sai pelo proxy
    # =========================================================================
    if _proxy_url:
        try:
            driver.set_page_load_timeout(15)
            driver.get('http://checkip.amazonaws.com')
            import time as _t
            _t.sleep(3)
            _ip = driver.find_element('tag name', 'body').text.strip()
            auth_match = re.findall(r'(?:https?|socks5)://.*@(.*):(.*)', _proxy_url)
            proxy_host = auth_match[0][0] if auth_match else ''
            if proxy_host and proxy_host in _ip:
                _log(f"🌐 ✅ IP confirmado: {_ip} (proxy SOCKS5 ativo)")
            else:
                _log(f"🌐 ⚠️ IP detectado: {_ip} (esperado: {proxy_host})")
            driver.set_page_load_timeout(settings.chrome_page_load_timeout)
        except Exception as e:
            _log(f"🌐 ⚠️ Verificação de IP falhou: {str(e)[:60]}")
            try:
                driver.set_page_load_timeout(settings.chrome_page_load_timeout)
            except Exception:
                pass
    


    # Ajuste de Download CDP — diretório isolado por thread
    from integrations.profile_manager import obter_caminho_download_thread
    downloads_path = str(obter_caminho_download_thread(thread_id).resolve())

    try:
        driver.execute_cdp_cmd('Page.setDownloadBehavior', {
            'behavior': 'allow',
            'downloadPath': downloads_path
        })
    except Exception:
        pass

    # =========================================================================
    # 🛡️ ANTI-DETECÇÃO AVANÇADA — Aplicado a TODOS os engines
    # UC "faz nativamente" mas NÃO é suficiente para Google signin headless.
    # =========================================================================
    try:
        _browser_version = driver.capabilities.get('browserVersion', '148.0.7778.97')
        _major = _browser_version.split('.')[0]
    except Exception:
        _browser_version = '148.0.7778.97'
        _major = '148'
    
    _log(f"🛡️ Anti-detecção: alinhando com Chrome {_browser_version}")
    
    try:
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": f"""
                Object.defineProperty(navigator, 'webdriver', {{get: () => false, configurable: true}});
                const _origGOPD = Object.getOwnPropertyDescriptor;
                Object.getOwnPropertyDescriptor = function(obj, prop) {{
                    if (prop === 'webdriver' && obj === navigator) return undefined;
                    return _origGOPD.apply(this, arguments);
                }};
                Object.defineProperty(navigator, 'languages', {{get: () => ['pt-BR', 'pt', 'en-US', 'en']}});
                Object.defineProperty(navigator, 'language', {{get: () => 'pt-BR'}});
                Object.defineProperty(navigator, 'plugins', {{
                    get: () => {{
                        const a = [
                            {{name:'Chrome PDF Plugin',filename:'internal-pdf-viewer',description:'Portable Document Format',length:1}},
                            {{name:'Chrome PDF Viewer',filename:'mhjfbmdgcfjbbpaeojofohoefgiehjai',description:'',length:1}},
                            {{name:'Native Client',filename:'internal-nacl-plugin',description:'',length:2}}
                        ];
                        Object.setPrototypeOf(a, PluginArray.prototype);
                        return a;
                    }}
                }});
                Object.defineProperty(navigator, 'mimeTypes', {{
                    get: () => {{
                        const a = [
                            {{type:'application/pdf',suffixes:'pdf',description:'Portable Document Format'}},
                            {{type:'application/x-nacl',suffixes:'',description:'Native Client Executable'}}
                        ];
                        Object.setPrototypeOf(a, MimeTypeArray.prototype);
                        return a;
                    }}
                }});
                Object.defineProperty(navigator, 'hardwareConcurrency', {{get: () => {os.cpu_count() or 8}}});
                Object.defineProperty(navigator, 'deviceMemory', {{get: () => 8}});
                const gp = WebGLRenderingContext.prototype.getParameter;
                WebGLRenderingContext.prototype.getParameter = function(p) {{
                    if (p===37445) return 'Google Inc. (Intel)';
                    if (p===37446) return 'ANGLE (Intel, Intel(R) UHD Graphics Direct3D11 vs_5_0 ps_5_0, D3D11)';
                    return gp.apply(this, arguments);
                }};
                if (!window.chrome) window.chrome = {{}};
                if (!window.chrome.runtime) {{
                    window.chrome.runtime = {{
                        PlatformOs:{{MAC:'mac',WIN:'win',ANDROID:'android',CROS:'cros',LINUX:'linux',OPENBSD:'openbsd'}},
                        PlatformArch:{{ARM:'arm',X86_32:'x86-32',X86_64:'x86-64',MIPS:'mips',MIPS64:'mips64'}},
                        PlatformNaclArch:{{ARM:'arm',X86_32:'x86-32',X86_64:'x86-64',MIPS:'mips',MIPS64:'mips64'}},
                        RequestUpdateCheckStatus:{{THROTTLED:'throttled',NO_UPDATE:'no_update',UPDATE_AVAILABLE:'update_available'}},
                        OnInstalledReason:{{INSTALL:'install',UPDATE:'update',CHROME_UPDATE:'chrome_update',SHARED_MODULE_UPDATE:'shared_module_update'}},
                        OnRestartRequiredReason:{{APP_UPDATE:'app_update',OS_UPDATE:'os_update',PERIODIC:'periodic'}},
                        connect:function(){{return{{}}}},sendMessage:function(){{}},id:undefined
                    }};
                }}
                if (!window.chrome.csi) {{
                    window.chrome.csi = function(){{return{{startE:Date.now(),onloadT:Date.now(),pageT:Math.random()*1000+500,tran:15}}}};
                }}
                if (!window.chrome.loadTimes) {{
                    window.chrome.loadTimes = function(){{return{{commitLoadTime:Date.now()/1000,connectionInfo:'h2',finishDocumentLoadTime:Date.now()/1000,finishLoadTime:Date.now()/1000,firstPaintAfterLoadTime:0,firstPaintTime:Date.now()/1000,navigationType:'Other',npnNegotiatedProtocol:'h2',requestTime:Date.now()/1000-0.5,startLoadTime:Date.now()/1000,wasAlternateProtocolAvailable:false,wasFetchedViaSpdy:true,wasNpnNegotiated:true}}}};
                }}
                if (navigator.permissions) {{
                    const oq = navigator.permissions.query;
                    navigator.permissions.query = (p) => (p.name==='notifications'?Promise.resolve({{state:Notification.permission}}):oq(p));
                }}
                if (navigator.connection) {{
                    Object.defineProperty(navigator.connection,'rtt',{{get:()=>50}});
                }}
                if (navigator.userAgentData) {{
                    const fUA={{brands:[{{brand:'Google Chrome',version:'{_major}'}},{{brand:'Chromium',version:'{_major}'}},{{brand:'Not_A Brand',version:'24'}}],mobile:false,platform:'Windows'}};
                    Object.defineProperty(navigator,'userAgentData',{{get:()=>({{...fUA,getHighEntropyValues:function(){{return Promise.resolve({{...fUA,architecture:'x86',bitness:'64',fullVersionList:[{{brand:'Google Chrome',version:'{_browser_version}'}},{{brand:'Chromium',version:'{_browser_version}'}},{{brand:'Not_A Brand',version:'24.0.0.0'}}],model:'',platformVersion:'15.0.0',uaFullVersion:'{_browser_version}',wow64:false}})}},toJSON:function(){{return fUA}}}})}});
                }}
                if (typeof WebGL2RenderingContext!=='undefined') {{
                    const gp2=WebGL2RenderingContext.prototype.getParameter;
                    WebGL2RenderingContext.prototype.getParameter=function(p){{if(p===37445)return'Google Inc. (Intel)';if(p===37446)return'ANGLE (Intel, Intel(R) UHD Graphics Direct3D11 vs_5_0 ps_5_0, D3D11)';return gp2.apply(this,arguments)}};
                }}
                // WebRTC IP Leak Protection: bloqueia STUN/TURN
                if (window.RTCPeerConnection) {{
                    const OrigRTC = window.RTCPeerConnection;
                    window.RTCPeerConnection = function(config, constraints) {{
                        if (config && config.iceServers) {{
                            config.iceServers = [];
                        }}
                        return new OrigRTC(config, constraints);
                    }};
                    window.RTCPeerConnection.prototype = OrigRTC.prototype;
                }}
            """
        })
    except Exception as e:
        _log(f"⚠️ Falha ao injetar anti-detecção JS: {str(e)[:60]}")
    
    # User-Agent Override
    try:
        driver.execute_cdp_cmd("Network.setUserAgentOverride", {
            "userAgent": f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{_browser_version} Safari/537.36",
            "acceptLanguage": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "platform": "Win32"
        })
    except Exception:
        pass
    
    _log(f"🛡️ {engine} ativo — anti-detecção JS + UA override aplicados")
    
    driver.implicitly_wait(settings.chrome_implicit_wait)
    
    return driver


def close_driver(driver: webdriver.Chrome | None) -> None:
    if driver is None:
        return
    
    # 1. Captura PID antes de quit
    pid = None
    try:
        pid = driver.service.process.pid
    except:
        pass
    
    # 2. Tenta o caminho civilizado
    try:
        driver.quit()
    except Exception:
        pass
    
    # 3. Garante a morte via pid_manager (mata árvore + desregistra)
    if pid:
        pid_manager.matar_pid(pid)