import os
import time
import shutil
from pathlib import Path
from datetime import datetime
from importlib import reload
import uuid
import pyperclip
import sys
import re

import pyautogui
import pygetwindow as gw

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

# Novo import simplificado apontando para o config.py na raiz do projeto
import config
from acesso_humble import sincronizar_credenciais_humble

pyautogui.FAILSAFE = False
DEBUG_NAO_FECHAR = False
MAX_TENTATIVAS_MESMO_FLOW = 3
ESPERA_ENTRE_TENTATIVAS_S = 5

class HumbleFlowError(RuntimeError):
    pass

class HumbleAccountDisabledError(RuntimeError):
    """Conta Google/Humble desativada ou bloqueada durante o login."""
    pass

def _ts() -> str:
    return datetime.now().strftime("%H:%M:%S")

def _log(msg: str):
    print(f"[{_ts()}] {msg}")

# ============================================================================
#   CONTROLE DE CONTAS DESATIVADAS
# ============================================================================
_contas_desativadas: set[str] = set()

def _marcar_conta_desativada(email: str):
    _contas_desativadas.add(email)
    _log(f"🚫 Conta marcada como desativada e ignorada: {email}")

def _conta_esta_desativada(conta: dict) -> bool:
    return conta["email"] in _contas_desativadas

def _recarregar_contas() -> list[dict]:
    _log("♻ Ressincronizando credenciais Humble a partir do Google Doc...")
    try:
        sincronizar_credenciais_humble()
    except Exception as e:
        _log(f"❌ Erro ao sincronizar credenciais Humble: {e}")
        return []

    try:
        reload(config)
    except Exception as e:
        _log(f"❌ Erro ao recarregar módulo de config: {e}")
        return []

    novas = config.HUMBLE_ACCOUNTS or []
    _log(f"ℹ {len(novas)} contas Humble carregadas após ressincronização.")

    config.HUMBLE_ACCOUNTS.clear()
    config.HUMBLE_ACCOUNTS.extend(novas)
    _contas_desativadas.clear()

    return novas

# ============================================================================
#   DETECÇÃO DE CONTA DESATIVADA NO NAVEGADOR
# ============================================================================
def detectar_conta_google_desativada(driver, timeout=5) -> str | None:
    try:
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.ID, "headingText"))
        )
    except Exception:
        return None

    try:
        heading = driver.find_element(By.ID, "headingText").text.strip().lower()
    except Exception:
        heading = ""

    if "sua conta foi desativada" not in heading and "desativada" not in heading:
        return None

    email = None
    try:
        email = driver.find_element(By.CSS_SELECTOR, ".yAlK0b[data-email]").get_attribute("data-email")
    except Exception:
        pass

    return email or "email_desconhecido"

# ============================================================================
#   POSICIONAMENTO DE JANELAS E DRIVER
# ============================================================================
def ajustar_chrome_para_area_livre(driver):
    try:
        driver.maximize_window()
    except Exception:
        pass

    try:
        screen_w, screen_h = pyautogui.size()
    except Exception:
        screen_w, screen_h = (1920, 1080)

    try:
        ps_windows = [
            w for w in gw.getAllWindows()
            if w.title and ("Windows PowerShell" in w.title or "Administrador: Windows PowerShell" in w.title)
        ]
    except Exception:
        ps_windows = []

    if not ps_windows:
        try:
            driver.maximize_window()
        except Exception:
            pass
        return

    ps = sorted(ps_windows, key=lambda w: w.top)[-1]
    top_powershell = ps.top
    
    if top_powershell <= 0 or top_powershell > screen_h:
        try:
            driver.maximize_window()
        except Exception:
            pass
        return

    largura = screen_w
    altura = max(400, top_powershell)

    try:
        driver.set_window_position(0, 0)
        driver.set_window_size(largura, altura)
        _log(f"[HUMBLE] Janela do Chrome ajustada para 0,0 com {largura}x{altura} (acima do PowerShell).")
    except Exception as e:
        _log(f"[HUMBLE] Falha ao ajustar janela do Chrome: {e}")
        try:
            driver.maximize_window()
        except Exception:
            pass

def criar_driver_humble(download_dir: Path | None = None):
    download_dir = Path(download_dir or config.DOWNLOAD_DIR)

    opts = Options()
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-logging")
    opts.add_argument("--log-level=3")
    opts.add_argument("--silent")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--disable-features=MediaRouter,OptimizationHints,CalculateNativeWinOcclusion")
    opts.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
    opts.add_experimental_option("useAutomationExtension", False)
    opts.add_experimental_option(
        "prefs",
        {
            "download.default_directory": str(download_dir),
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True,
            "profile.default_content_setting_values.notifications": 2,
            "credentials_enable_service": False,
            "profile.password_manager_enabled": False,
        },
    )

    service = Service(config.CHROMEDRIVER_PATH, log_output=os.devnull)
    driver = webdriver.Chrome(service=service, options=opts)
    ajustar_chrome_para_area_livre(driver)
    return driver

def _wait_click(driver, by, value, timeout=None, descricao="elemento"):
    t = timeout if timeout is not None else config.WAIT
    el = WebDriverWait(driver, t).until(EC.element_to_be_clickable((by, value)))
    el.click()
    _log(f"✔ Clicado: {descricao}")
    return el

def _wait_visible(driver, by, value, timeout=None, descricao="elemento"):
    t = timeout if timeout is not None else config.WAIT
    el = WebDriverWait(driver, t).until(EC.visibility_of_element_located((by, value)))
    _log(f"✔ Visível: {descricao}")
    return el

# ============================================================================
#   INTERAÇÕES DO FLOW
# ============================================================================
def refresh_flow(driver, motivo: str = ""):
    msg = "[HUMBLE] Refresh do Flow"
    if motivo:
        msg += f" ({motivo})"
    _log(msg + "...")

    try:
        wins = [w for w in gw.getWindowsWithTitle("Flow -")]
        if wins:
            wins[0].activate()
            time.sleep(0.3)
    except Exception:
        pass

    try:
        pyautogui.press("f5")
    except pyautogui.FailSafeException:
        _log("⚠ Fail-safe do PyAutoGUI disparou ao enviar F5. Ignorando.")
    except Exception as e:
        _log(f"⚠ Erro ao enviar F5 via PyAutoGUI: {e}")

    time.sleep(3)
    try:
        _fechar_overlays_flow(driver)
    except Exception:
        pass

def abrir_flow(driver):
    _log(f"[HUMBLE] Abrindo Flow: {config.HUMBLE_FLOW_URL}")
    driver.get(config.HUMBLE_FLOW_URL)
    time.sleep(3)

def clicar_create_with_flow(driver):
    _log("[HUMBLE] Clicando em 'Create with Flow'...")
    xpath = "//button[.//span[contains(., 'Create with Flow')] ]"
    _wait_click(driver, By.XPATH, xpath, descricao="Create with Flow")
    time.sleep(2)

def fazer_login_google(driver, email: str, senha: str):
    _log(f"[HUMBLE] Login Google: {email}")

    campo_email = _wait_visible(driver, By.XPATH, "//input[@type='email' and @id='identifierId']", timeout=25, descricao="campo e-mail")
    campo_email.clear()
    campo_email.send_keys(email)

    _wait_click(driver, By.XPATH, "//div[@id='identifierNext'] | //button[.//span[normalize-space()='Avançar' or normalize-space()='Next']]", timeout=30, descricao="Avançar/Next e-mail")
    
    campo_senha = _wait_visible(driver, By.XPATH, "//input[@type='password' and @name='Passwd']", timeout=25, descricao="campo senha")
    campo_senha.clear()
    campo_senha.send_keys(senha)

    _wait_click(driver, By.XPATH, "//div[@id='passwordNext'] | //button[.//span[normalize-space()='Avançar' or normalize-space()='Next']]", timeout=30, descricao="Avançar/Next senha")
    time.sleep(3)

    email_bloqueado = detectar_conta_google_desativada(driver, timeout=5)
    if email_bloqueado:
        raise HumbleAccountDisabledError(f"Conta Google desativada/bloqueada: {email_bloqueado}")
    time.sleep(3)

def aguardar_flow_pronto(driver):
    _log("[HUMBLE] Aguardando tela do Flow ficar pronta...")
    fim = time.time() + 40
    while time.time() < fim:
        try:
            driver.find_element(By.XPATH, "//header | //button[contains(., 'Novo projeto')]")
            _log("✔ Flow pronto.")
            return
        except Exception:
            time.sleep(2)
    raise HumbleFlowError("Flow não ficou pronto após login.")

def _fechar_popup_login_chrome():
    _log("[HUMBLE] Tentando fechar popup 'Fazer login no Chrome' (clique + ESC)...")
    win_flow = None
    try:
        wins = [w for w in gw.getAllWindows() if w.title and "Flow" in w.title and "Chrome" not in w.title]
        if not wins:
            wins = [w for w in gw.getAllWindows() if w.title and "labs.google" in w.title.lower()]
        if wins:
            win_flow = wins[0]
            win_flow.activate()
            time.sleep(0.5)
    except Exception:
        pass

    try:
        if win_flow:
            cx = win_flow.left + win_flow.width // 2
            cy = win_flow.top + win_flow.height // 2
        else:
            screen_w, screen_h = pyautogui.size()
            cx = int(screen_w * 0.5)
            cy = int(screen_h * 0.3) 

        pyautogui.moveTo(cx, cy, duration=0.1)
        pyautogui.click()
        time.sleep(0.3)
        pyautogui.press("esc")
        time.sleep(0.5)
        pyautogui.press("esc") 
        time.sleep(0.5)
    except Exception as e:
        _log(f"⚠ Erro ao tentar fechar popup (ignorado): {e}")

def _fechar_overlays_flow(driver):
    _log("[HUMBLE] Verificando se há overlays/banners do Flow para fechar...")
    try:
        body = driver.find_element(By.TAG_NAME, "body")
        body.send_keys(Keys.ESCAPE)
        time.sleep(0.1)
    except Exception:
        pass

    xpaths_botoes = [
        "//button[span[normalize-space()='Comece já']]", "//button[normalize-space()='Comece já']",
        "//button[normalize-space()='Fechar']", "//button[normalize-space()='OK']",
        "//button[normalize-space()='Ok']", "//button[normalize-space()='Entendi']",
        "//button[contains(., 'Got it')]", "//button[contains(., 'Close')]", "//button[contains(., 'Dismiss')]"
    ]
    for xp in xpaths_botoes:
        try:
            btn = WebDriverWait(driver, 0.2).until(EC.element_to_be_clickable((By.XPATH, xp)))
            _log(f"[HUMBLE] Fechando overlay via botão: {xp}")
            btn.click()
            time.sleep(0.2)
            break
        except Exception:
            continue

    try:
        body = driver.find_element(By.TAG_NAME, "body")
        driver.execute_script("arguments[0].click();", body)
        time.sleep(0.1)
    except Exception:
        pass

def clicar_novo_projeto(driver):
    _log("[HUMBLE] Clicando em 'Novo projeto'...")
    xpaths = [
        "//button[.//i[normalize-space()='add_2'] and contains(., 'Novo projeto')]",
        "//button[contains(@class,'sc-a38764c7-0') and .//i[normalize-space()='add_2'] and contains(., 'Novo projeto')]",
        "//button[.//div[@data-type='button-overlay'] and .//i[normalize-space()='add_2'] and contains(., 'Novo projeto')]",
        "//button[contains(., 'Novo projeto')]",
    ]
    ultimo_erro = None
    for xp in xpaths:
        try:
            btn = WebDriverWait(driver, 8).until(EC.element_to_be_clickable((By.XPATH, xp)))
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
            time.sleep(0.5)
            try: btn.click()
            except Exception: driver.execute_script("arguments[0].click();", btn)
            _log("✔ Clicado em 'Novo projeto'.")
            time.sleep(3)
            return
        except Exception as e:
            ultimo_erro = e
    raise HumbleFlowError(f"Não achei o botão 'Novo projeto' após o login: {ultimo_erro}")

def fluxo_completo_login_e_preparo(driver, email: str, senha: str):
    abrir_flow(driver)
    clicar_create_with_flow(driver)
    fazer_login_google(driver, email, senha)
    _fechar_popup_login_chrome()
    time.sleep(2)
    try: _fechar_overlays_flow(driver)
    except Exception: pass

    email_bloqueado = detectar_conta_google_desativada(driver, timeout=3)
    if email_bloqueado:
        raise HumbleAccountDisabledError(f"Conta Google desativada/bloqueada após popup: {email_bloqueado}")
    aguardar_flow_pronto(driver)
    _fechar_overlays_flow(driver)
    clicar_novo_projeto(driver)
    refresh_flow(driver, "após Novo projeto")
    _wait_visible(driver, By.XPATH, "//button[contains(., 'Nano Banana 2') and @aria-haspopup='menu']", timeout=30, descricao="chip Nano Banana 2")
    abrir_chip_nano(driver)
    configurar_nano_video_9x16_x1_fast(driver)

def abrir_chip_nano(driver):
    _log("[HUMBLE] Abrindo chip Nano Banana 2...")
    _wait_click(driver, By.XPATH, "//button[contains(., 'Nano Banana 2') and @aria-haspopup='menu']", descricao="chip Nano Banana 2")
    WebDriverWait(driver, config.WAIT).until(EC.presence_of_element_located((By.XPATH, "//div[contains(@class,'DropdownMenuContent') and @role='menu']")))
    time.sleep(1)

def configurar_nano_video_9x16_x1_fast(driver):
    _log("[HUMBLE] Configurando Nano: Vídeo + 9:16 + x1 + Fast [Lower Priority]")
    painel = _wait_visible(driver, By.XPATH, "//div[contains(@class,'DropdownMenuContent') and @role='menu']", descricao="painel Nano")
    painel.find_element(By.XPATH, ".//button[.//i[text()='videocam'] or contains(., 'Vídeo')]").click()
    time.sleep(0.5)
    painel.find_element(By.XPATH, ".//button[.//i[text()='crop_9_16'] or contains(., '9:16')]").click()
    time.sleep(0.5)
    painel.find_element(By.XPATH, ".//button[normalize-space()='x1']").click()
    time.sleep(0.5)
    _wait_click(driver, By.XPATH, "//button[contains(., 'Veo 3.1 - Fast')] | //span[contains(., 'Veo 3.1 - Fast')]", timeout=15, descricao="submenu Veo 3.1 - Fast")
    time.sleep(1)
    _wait_click(driver, By.XPATH, "//button[contains(., 'Veo 3.1 - Fast [Lower Priority]')] | //span[contains(., 'Veo 3.1 - Fast [Lower Priority]')]", timeout=15, descricao="modelo Veo 3.1 - Fast [Lower Priority]")
    time.sleep(1)

def _ler_texto_prompt_box(box):
    try: return (box.get_attribute("innerText") or "").strip()
    except Exception: return ""

def preencher_prompt(driver, prompt: str):
    _log("[HUMBLE] Preenchendo prompt (COLAR de uma vez)...")
    box = _wait_visible(driver, By.XPATH, "//div[@role='textbox' and @contenteditable='true']", timeout=20, descricao="campo prompt")
    driver.execute_script("arguments[0].scrollIntoView({block: 'center', inline: 'center'});", box)
    time.sleep(0.3)
    try:
        driver.execute_script("arguments[0].focus();", box)
        driver.execute_script("arguments[0].click();", box)
    except Exception:
        try:
            overlays = driver.find_elements(By.XPATH, "//div[contains(@class,'sc-d23b167b-0') or contains(@class,'overlay')]")
            for o in overlays: driver.execute_script("arguments[0].remove();", o)
            time.sleep(0.3)
            driver.execute_script("arguments[0].focus();", box)
            driver.execute_script("arguments[0].click();", box)
        except Exception: pass
    time.sleep(0.4)
    try:
        box.send_keys(Keys.CONTROL, "a")
        time.sleep(0.2)
    except Exception: pass
    pyperclip.copy(prompt)
    box.send_keys(Keys.CONTROL, "v")
    time.sleep(1.2)
    depois = _ler_texto_prompt_box(box)
    if prompt[:80].strip() not in depois:
        raise HumbleFlowError("Prompt não colou integralmente no campo.")

# ============================================================================
#   MONITOR DE GERAÇÃO
# ============================================================================
def _print_progress_inline(msg: str):
    sys.stdout.write("\r" + msg.ljust(120))
    sys.stdout.flush()

def _finish_progress_inline(msg: str = ""):
    if msg: sys.stdout.write("\r" + msg.ljust(120) + "\n")
    else: sys.stdout.write("\n")
    sys.stdout.flush()

def _listar_cards(driver):
    return driver.find_elements(By.XPATH, "//*[@data-tile-id]")

def _encontrar_card_por_prompt(driver, prompt: str):
    trecho = prompt[:60].replace("'", " ").strip().lower()
    if not trecho: return None
    candidato_com_video = None
    candidato_sem_video = None
    for card in _listar_cards(driver):
        try: txt = (card.text or "").lower()
        except Exception: continue
        if trecho and trecho not in txt: continue
        try:
            tem_video = bool(card.find_elements(By.XPATH, ".//video | .//*[contains(@src,'/fx/api/trpc/media.getMediaUrlRedirect')]"))
        except Exception: tem_video = False
        if tem_video and not candidato_com_video: candidato_com_video = card
        elif not tem_video and not candidato_sem_video: candidato_sem_video = card
    if candidato_com_video: return candidato_com_video
    if candidato_sem_video: return candidato_sem_video
    return None

def _obter_tile_id(card):
    try:
        tid = card.get_attribute("data-tile-id")
        if tid: return tid
    except Exception: pass
    try:
        el = card.find_element(By.XPATH, ".//*[@data-tile-id]")
        tid = el.get_attribute("data-tile-id")
        if tid: return tid
    except Exception: pass
    return None

def _encontrar_card_por_tile_id(driver, tile_id: str):
    if not tile_id: return None
    try: return driver.find_element(By.XPATH, f"//*[@data-tile-id='{tile_id}']")
    except Exception: return None

def _texto_card(card) -> str:
    try: return " ".join((card.text or "").split())
    except Exception: return ""

def _card_tem_video_ou_preview(card) -> bool:
    xpaths = [".//video", ".//img", ".//canvas", ".//button[.//video]", ".//*[contains(@aria-label,'Open')]", ".//i[text()='download']"]
    for xp in xpaths:
        try:
            if card.find_elements(By.XPATH, xp): return True
        except Exception: pass
    return False

def _card_tem_sinal_processando(card) -> bool:
    xpaths = [".//*[contains(text(), '%')]", ".//*[contains(text(), 'Gerando')]", ".//*[contains(@aria-label, 'loading')]", ".//*[contains(@class, 'spin')]"]
    for xp in xpaths:
        try:
            if card.find_elements(By.XPATH, xp): return True
        except Exception: pass
    return False

def _card_tem_erro(card) -> bool:
    termos = ["Falha", "Erro", "Violação", "Failed", "Não foi possível"]
    try: txt = _texto_card(card).lower()
    except Exception: txt = ""
    return any(t.lower() in txt for t in termos)

def _extrair_percentual_card(card) -> int | None:
    candidatos_xpath = [".//*[contains(text(), '%')]", ".//span[contains(text(), '%')]"]
    textos = []
    for xp in candidatos_xpath:
        try:
            els = card.find_elements(By.XPATH, xp)
            for el in els:
                try:
                    txt = (el.text or "").strip()
                    if txt: textos.append(txt)
                except Exception: pass
        except Exception: pass
    try:
        txt_card = (card.text or "").strip()
        if txt_card: textos.append(txt_card)
    except Exception: pass
    for txt in textos:
        m = re.search(r'(?<!\d)(100|[1-9]?\d)\s*%', txt)
        if m:
            try: return int(m.group(1))
            except Exception: pass
    return None

def _snapshot_card(card):
    return {
        "texto": _texto_card(card)[:500],
        "tem_video": _card_tem_video_ou_preview(card),
        "tem_processando": _card_tem_sinal_processando(card),
        "tem_erro": _card_tem_erro(card),
        "percentual": _extrair_percentual_card(card),
    }

def aguardar_geracao_video(driver, prompt: str, timeout=420):
    _log("[HUMBLE] Aguardando geração do vídeo...")
    fim = time.time() + timeout
    card = None
    tile_id = None
    ultimo_movimento = time.time()
    viu_sinal_de_vida = False
    ultimo_percentual_logado = None
    ultimo_status_inline = None
    linha_progresso_ativa = False

    while time.time() < fim:
        if tile_id: card = _encontrar_card_por_tile_id(driver, tile_id)
        if not card:
            cards = _listar_cards(driver)
            card = cards[0] if cards else None
        if not card: card = _encontrar_card_por_prompt(driver, prompt)

        if not card:
            if ultimo_status_inline != "sem_card":
                _print_progress_inline("[HUMBLE] Gerando vídeo... aguardando card aparecer")
                ultimo_status_inline = "sem_card"
                linha_progresso_ativa = True
            time.sleep(2)
            continue

        if not tile_id:
            tile_id = _obter_tile_id(card)
            if tile_id and linha_progresso_ativa:
                _finish_progress_inline()
                linha_progresso_ativa = False

        snap = _snapshot_card(card)

        if snap["tem_erro"]:
            if linha_progresso_ativa: _finish_progress_inline("[HUMBLE] Geração falhou.")
            _log("❌ Card em estado de erro detectado.")
            return {"status": "erro", "tile_id": tile_id}

        if snap["tem_video"]:
            if linha_progresso_ativa:
                pct = snap.get("percentual")
                _finish_progress_inline(f"[HUMBLE] Gerando vídeo... {pct}% | pronto!" if pct is not None else "[HUMBLE] Gerando vídeo... pronto!")
            _log("✔ Card com preview/vídeo/download detectado. Vídeo pronto.")
            return {"status": "ok", "tile_id": tile_id}

        percentual = snap.get("percentual")
        if percentual is not None:
            viu_sinal_de_vida = True
            ultimo_movimento = time.time()
            if percentual != ultimo_percentual_logado:
                _print_progress_inline(f"[HUMBLE] Gerando vídeo... {percentual}%")
                ultimo_percentual_logado = percentual
                ultimo_status_inline = "percentual"
                linha_progresso_ativa = True
        elif snap["tem_processando"]:
            viu_sinal_de_vida = True
            ultimo_movimento = time.time()
            if ultimo_status_inline != "processando":
                _print_progress_inline("[HUMBLE] Gerando vídeo... processando")
                ultimo_status_inline = "processando"
                linha_progresso_ativa = True
        else:
            parado = int(time.time() - ultimo_movimento)
            msg = f"[HUMBLE] Gerando vídeo... aguardando progresso ({parado}s)"
            if ultimo_status_inline != msg:
                _print_progress_inline(msg)
                ultimo_status_inline = msg
                linha_progresso_ativa = True

        if not viu_sinal_de_vida and (time.time() - ultimo_movimento > 45):
            if linha_progresso_ativa: _finish_progress_inline("[HUMBLE] Geração falhou por falta de atividade.")
            return {"status": "erro", "tile_id": tile_id}
        elif viu_sinal_de_vida and (time.time() - ultimo_movimento > 90):
            if linha_progresso_ativa: _finish_progress_inline("[HUMBLE] Geração falhou por estagnação.")
            return {"status": "erro", "tile_id": tile_id}

        time.sleep(3)

    if linha_progresso_ativa: _finish_progress_inline("[HUMBLE] Timeout na geração.")
    raise HumbleFlowError("Timeout aguardando geração do vídeo.")

# ============================================================================
#   DOWNLOAD / CONCLUSÃO
# ============================================================================
def abrir_video_pronto(driver, tile_id: str | None = None, prompt: str | None = None):
    _log("[HUMBLE] Abrindo página do vídeo pronto...")
    card = _encontrar_card_por_tile_id(driver, tile_id) if tile_id else _encontrar_card_por_prompt(driver, prompt)
    if not card: raise HumbleFlowError("Não encontrei card do vídeo pronto.")

    try: alvo_click = card.find_element(By.XPATH, ".//button[contains(@class,'sc-d64366c4-1') and .//video]")
    except Exception:
        try: alvo_click = card.find_element(By.XPATH, ".//video")
        except Exception: raise HumbleFlowError("Não achei elemento clicável (botão/vídeo).")

    driver.execute_script("arguments[0].scrollIntoView({block:'center', inline:'center'});", alvo_click)
    time.sleep(0.4)
    try: alvo_click.click()
    except Exception: driver.execute_script("arguments[0].click();", alvo_click)
    time.sleep(4)

def esperar_botao_baixar(driver, timeout=120):
    return WebDriverWait(driver, timeout).until(EC.element_to_be_clickable((By.XPATH, "//button[.//i[text()='download'] and .//div[contains(.,'Baixar')]]")))

def esperar_opcao_720p(driver, timeout=30):
    return WebDriverWait(driver, timeout).until(EC.element_to_be_clickable((By.XPATH, "//button[@role='menuitem'][.//span[text()='720p']]")))

def baixar_video_720p(driver, destino_dir: Path | None = None, nome_arquivo: str | None = None):
    download_dir = Path(config.DOWNLOAD_DIR)
    destino_dir = Path(destino_dir or config.DOWNLOAD_DIR)
    download_dir.mkdir(parents=True, exist_ok=True)
    destino_dir.mkdir(parents=True, exist_ok=True)

    antes = {p.name for p in download_dir.glob("*.mp4")}
    esperar_botao_baixar(driver).click()
    time.sleep(0.8)
    esperar_opcao_720p(driver).click()

    fim = time.time() + 180
    arquivo_baixado = None
    while time.time() < fim:
        crdownloads = list(download_dir.glob("*.crdownload"))
        novos_mp4 = [p for p in download_dir.glob("*.mp4") if p.name not in antes]
        if novos_mp4 and not crdownloads:
            novos_mp4.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            arquivo_baixado = novos_mp4[0]
            break
        time.sleep(1)

    if not arquivo_baixado:
        raise HumbleFlowError("Timeout aguardando arquivo .mp4.")

    nome_final = nome_arquivo or f"Make_video_of_{datetime.now().strftime('%Y%m%d%H%M%S')}.mp4"
    destino_final = destino_dir / nome_final
    if destino_final.exists(): destino_final.unlink()
    shutil.move(str(arquivo_baixado), str(destino_final))
    _log(f"✔ Arquivo movido para: {destino_final}")
    return destino_final

def voltar_para_lista_videos(driver):
    _log("[HUMBLE] Voltando para lista de prompts...")
    btn = WebDriverWait(driver, 60).until(EC.element_to_be_clickable((By.XPATH, "//button[.//i[text()='check'] and .//div[contains(.,'Concluir')]]")))
    btn.click()
    time.sleep(3)

def gerar_video_humble(driver, prompt: str, destino_dir: Path | None = None):
    refresh_flow(driver, "antes de preencher o prompt")
    _wait_visible(driver, By.XPATH, "//div[@role='textbox' and @contenteditable='true']", timeout=30)
    preencher_prompt(driver, prompt)
    
    box = driver.find_element(By.XPATH, "//div[@role='textbox' and @contenteditable='true']")
    box.send_keys(Keys.ENTER)
    time.sleep(2)
    
    resultado = aguardar_geracao_video(driver, prompt)
    if resultado.get("status") != "ok":
        raise HumbleFlowError(f"Geração falhou com status={resultado.get('status')!r}")

    abrir_video_pronto(driver, tile_id=resultado.get("tile_id"), prompt=prompt)
    arquivo_final = baixar_video_720p(driver, destino_dir=destino_dir)
    voltar_para_lista_videos(driver)
    return arquivo_final

# ============================================================================
#   ORQUESTRADOR MAIN
# ============================================================================
def _abrir_conta(conta: dict):
    _log(f"[CONTA #{conta['indice']}] Inicializando conta: {conta['email']}")
    driver = criar_driver_humble()
    fluxo_completo_login_e_preparo(driver, conta['email'], conta['senha'])
    _log(f"[CONTA #{conta['indice']}] Flow pronto para gerar.")
    return driver

def _fechar_driver(driver):
    if driver:
        try: driver.quit()
        except Exception: pass

def _tentar_gerar_na_mesma_sessao(driver, conta: dict, prompt: str, idx_prompt: int) -> Path | None:
    for tentativa in range(1, MAX_TENTATIVAS_MESMO_FLOW + 1):
        try:
            _log(f"[CONTA #{conta['indice']}] Tentativa {tentativa}/{MAX_TENTATIVAS_MESMO_FLOW} da cena {idx_prompt} no mesmo Flow...")
            arquivo = gerar_video_humble(driver, prompt)
            if arquivo: return arquivo
        except HumbleAccountDisabledError:
            raise
        except Exception as e:
            _log(f"❌ Conta #{conta['indice']} falhou na cena {idx_prompt} (tentativa {tentativa}): {e}")
        
        if tentativa < MAX_TENTATIVAS_MESMO_FLOW:
            time.sleep(ESPERA_ENTRE_TENTATIVAS_S)
    return None

def rodar_automacao(prompts: list[str]) -> list[Path]:
    if not config.HUMBLE_ACCOUNTS:
        raise ValueError("Nenhuma conta encontrada.")
    if not prompts: return []

    arquivos_baixados: list[Path] = []
    ultimo_erro = None
    total_contas = len(config.HUMBLE_ACCOUNTS)
    indice_conta_atual = 0
    driver_atual = None
    conta_atual = None

    for idx_prompt, prompt in enumerate(prompts, 1):
        _log(f"[VÍDEO {idx_prompt}/{len(prompts)}]")
        gerou = False
        contas_tentadas_nesta_cena = 0

        while not gerou:
            if driver_atual is not None and conta_atual is not None:
                try:
                    arquivo = _tentar_gerar_na_mesma_sessao(driver_atual, conta_atual, prompt, idx_prompt)
                except HumbleAccountDisabledError as e:
                    _marcar_conta_desativada(conta_atual["email"])
                    _fechar_driver(driver_atual)
                    driver_atual, conta_atual, arquivo = None, None, None

                if arquivo:
                    arquivos_baixados.append(arquivo)
                    gerou = True
                    break

                _fechar_driver(driver_atual)
                driver_atual, conta_atual = None, None

            contas_ativas = [c for c in config.HUMBLE_ACCOUNTS if not _conta_esta_desativada(c)]
            if contas_tentadas_nesta_cena >= len(contas_ativas) and contas_ativas:
                novas_contas = _recarregar_contas()
                if not novas_contas:
                    raise HumbleFlowError(f"Não foi possível gerar a cena {idx_prompt}. Último erro: {ultimo_erro}")
                total_contas = len(config.HUMBLE_ACCOUNTS)
                indice_conta_atual = 0
                contas_tentadas_nesta_cena = 0
                contas_ativas = [c for c in config.HUMBLE_ACCOUNTS if not _conta_esta_desativada(c)]
                if not contas_ativas:
                    raise HumbleFlowError("Todas as contas desativadas após ressincronizar.")

            tentativas_rotacao = 0
            conta = None
            while tentativas_rotacao < total_contas:
                candidata = config.HUMBLE_ACCOUNTS[indice_conta_atual]
                indice_conta_atual = (indice_conta_atual + 1) % total_contas
                tentativas_rotacao += 1
                if not _conta_esta_desativada(candidata):
                    conta = candidata
                    break
            else:
                raise HumbleFlowError("Todas as contas estão desativadas. Impossível continuar.")

            contas_tentadas_nesta_cena += 1

            try:
                driver_atual = _abrir_conta(conta)
                conta_atual = conta
            except HumbleAccountDisabledError as e:
                _marcar_conta_desativada(conta["email"])
                _fechar_driver(driver_atual)
                driver_atual, conta_atual, ultimo_erro = None, None, e
                continue
            except Exception as e:
                ultimo_erro = e
                _fechar_driver(driver_atual)
                driver_atual, conta_atual = None, None
                continue

            try:
                arquivo = _tentar_gerar_na_mesma_sessao(driver_atual, conta_atual, prompt, idx_prompt)
            except HumbleAccountDisabledError as e:
                _marcar_conta_desativada(conta_atual["email"])
                _fechar_driver(driver_atual)
                driver_atual, conta_atual, arquivo = None, None, None

            if arquivo:
                arquivos_baixados.append(arquivo)
                gerou = True
                break

            _fechar_driver(driver_atual)
            driver_atual, conta_atual = None, None

    _fechar_driver(driver_atual)
    return arquivos_baixados