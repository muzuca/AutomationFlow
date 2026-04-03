# humble_client.py

import os
import time
import shutil
from pathlib import Path
from datetime import datetime
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

from .config import (
    CHROMEDRIVER_PATH,
    DOWNLOAD_DIR,
    WAIT,
    HUMBLE_FLOW_URL,
)

pyautogui.FAILSAFE = False  # desativa fail-safe só neste script
DEBUG_NAO_FECHAR = False


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
#   DETECÇÃO DE CONTA DESATIVADA
# ============================================================================


def detectar_conta_google_desativada(driver, timeout=5) -> str | None:
    """
    Retorna o e-mail detectado se a tela 'Sua conta foi desativada' estiver visível.
    Caso contrário, retorna None.
    """
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
        email = driver.find_element(
            By.CSS_SELECTOR,
            ".yAlK0b[data-email]"
        ).get_attribute("data-email")
    except Exception:
        pass

    return email or "email_desconhecido"


# ============================================================================
#   DRIVER
# ============================================================================


def criar_driver_humble(download_dir: Path | None = None):
    download_dir = Path(download_dir or DOWNLOAD_DIR)

    opts = Options()
    opts.add_argument("--start-maximized")
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

    service = Service(
        CHROMEDRIVER_PATH,
        log_output=os.devnull,
    )

    driver = webdriver.Chrome(service=service, options=opts)
    driver.maximize_window()
    return driver


def _wait_click(driver, by, value, timeout=WAIT, descricao="elemento"):
    el = WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable((by, value))
    )
    el.click()
    _log(f"✔ Clicado: {descricao}")
    return el


def _wait_visible(driver, by, value, timeout=WAIT, descricao="elemento"):
    el = WebDriverWait(driver, timeout).until(
        EC.visibility_of_element_located((by, value))
    )
    _log(f"✔ Visível: {descricao}")
    return el


# ============================================================================
#   LOGIN + PREPARO
# ============================================================================


def abrir_flow(driver):
    _log(f"[HUMBLE] Abrindo Flow: {HUMBLE_FLOW_URL}")
    driver.get(HUMBLE_FLOW_URL)
    time.sleep(3)


def clicar_create_with_flow(driver):
    _log("[HUMBLE] Clicando em 'Create with Flow'...")
    xpath = "//button[.//span[contains(., 'Create with Flow')] ]"
    _wait_click(driver, By.XPATH, xpath, descricao="Create with Flow")
    time.sleep(2)


def fazer_login_google(driver, email: str, senha: str):
    _log(f"[HUMBLE] Login Google: {email}")

    campo_email = _wait_visible(
        driver,
        By.XPATH,
        "//input[@type='email' and @name='identifier' and @id='identifierId']",
        timeout=25,
        descricao="campo e-mail",
    )
    campo_email.clear()
    campo_email.send_keys(email)

    _wait_click(
        driver,
        By.XPATH,
        (
            "//div[@id='identifierNext']"
            " | //button[.//span[normalize-space()='Avançar' or normalize-space()='Next']]"
            " | //div[@role='button'][.//span[normalize-space()='Avançar' or normalize-space()='Next']]"
        ),
        timeout=30,
        descricao="Avançar/Next e-mail",
    )

    campo_senha = _wait_visible(
        driver,
        By.XPATH,
        "//input[@type='password' and @name='Passwd']",
        timeout=25,
        descricao="campo senha",
    )
    campo_senha.clear()
    campo_senha.send_keys(senha)

    _wait_click(
        driver,
        By.XPATH,
        (
            "//div[@id='passwordNext']"
            " | //button[.//span[normalize-space()='Avançar' or normalize-space()='Next']]"
            " | //div[@role='button'][.//span[normalize-space()='Avançar' or normalize-space()='Next']]"
        ),
        timeout=30,
        descricao="Avançar/Next senha",
    )

    time.sleep(3)

    email_bloqueado = detectar_conta_google_desativada(driver, timeout=5)
    if email_bloqueado:
        raise HumbleAccountDisabledError(
            f"Conta Google desativada/bloqueada: {email_bloqueado}"
        )

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
    try:
        wins = [w for w in gw.getWindowsWithTitle("Flow -")]
        if wins:
            wins[0].activate()
            time.sleep(0.5)
    except Exception:
        pass

    try:
        screen_w, screen_h = pyautogui.size()
        cx = int(screen_w * 0.5)
        cy = int(screen_h * 0.4)
        pyautogui.moveTo(cx, cy, duration=0.1)
        pyautogui.click()
        time.sleep(0.2)
        pyautogui.press("esc")
        time.sleep(1)
    except pyautogui.FailSafeException:
        _log("⚠ Fail-safe do PyAutoGUI disparou ao tentar fechar popup. Ignorando.")
    except Exception as e:
        _log(f"⚠ Erro ao tentar fechar popup (ignorado): {e}")

def _fechar_overlays_flow(driver):
    """
    Fecha overlays/modais genéricos do Flow:
    - changelog / release notes (como o iframe da tela 'Experimental Voice Ingredients')
    - banners com botões 'Comece já', 'Fechar', 'Close', 'Entendi', 'OK'
    - tenta também ESC + clique no fundo.
    """
    _log("[HUMBLE] Verificando se há overlays/banners do Flow para fechar...")

    # 1) ESC direto (muitos modais fecham com Esc)
    try:
        from selenium.webdriver.common.keys import Keys
        body = driver.find_element(By.TAG_NAME, "body")
        body.send_keys(Keys.ESCAPE)
        time.sleep(0.8)
    except Exception:
        pass

    # 2) Tenta clicar em botões comuns de fechamento
    xpaths_botoes = [
        "//button[span[normalize-space()='Comece já']]",
        "//button[normalize-space()='Comece já']",
        "//button[normalize-space()='Fechar']",
        "//button[normalize-space()='OK']",
        "//button[normalize-space()='Ok']",
        "//button[normalize-space()='Entendi']",
        "//button[contains(., 'Got it')]",
        "//button[contains(., 'Close')]",
        "//button[contains(., 'Dismiss')]",
    ]
    for xp in xpaths_botoes:
        try:
            btn = WebDriverWait(driver, 2).until(
                EC.element_to_be_clickable((By.XPATH, xp))
            )
            _log(f"[HUMBLE] Fechando overlay via botão: {xp}")
            btn.click()
            time.sleep(1)
            break
        except Exception:
            continue

    # 3) Clique no fundo (às vezes o overlay fecha assim)
    try:
        body = driver.find_element(By.TAG_NAME, "body")
        driver.execute_script("arguments[0].click();", body)
        time.sleep(0.5)
    except Exception:
        pass

def clicar_novo_projeto(driver):
    """
    Clica no botão real de 'Novo projeto' do header do Flow.
    """
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
            btn = WebDriverWait(driver, 8).until(
                EC.element_to_be_clickable((By.XPATH, xp))
            )
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
            time.sleep(0.5)

            try:
                btn.click()
            except Exception:
                driver.execute_script("arguments[0].click();", btn)

            _log("✔ Clicado em 'Novo projeto'.")
            time.sleep(3)
            return
        except Exception as e:
            ultimo_erro = e

    _log("❌ Não achei/clicou o botão 'Novo projeto' após o login.")
    if DEBUG_NAO_FECHAR:
        input("DEBUG: ENTER depois de olhar o Flow...")
    raise HumbleFlowError(f"Não achei o botão 'Novo projeto' após o login: {ultimo_erro}")


def fluxo_completo_login_e_preparo(driver, email: str, senha: str):
    abrir_flow(driver)
    clicar_create_with_flow(driver)
    fazer_login_google(driver, email, senha)

    _fechar_popup_login_chrome()

    email_bloqueado = detectar_conta_google_desativada(driver, timeout=3)
    if email_bloqueado:
        raise HumbleAccountDisabledError(
            f"Conta Google desativada/bloqueada após popup: {email_bloqueado}"
        )

    aguardar_flow_pronto(driver)

    # NOVO: limpa qualquer changelog / banner da tela inicial
    _fechar_overlays_flow(driver)

    clicar_novo_projeto(driver)

    # NOVO: se o changelog abrir só depois do "Novo projeto", fecha aqui também
    _fechar_overlays_flow(driver)

    abrir_chip_nano(driver)
    configurar_nano_video_9x16_x1_fast(driver)


# ============================================================================
#   NANO / PROMPT / RESTO
# ============================================================================


def abrir_chip_nano(driver):
    _log("[HUMBLE] Abrindo chip Nano Banana 2...")
    chip_xpath = "//button[contains(., 'Nano Banana 2') and @aria-haspopup='menu']"
    _wait_click(driver, By.XPATH, chip_xpath, descricao="chip Nano Banana 2")

    WebDriverWait(driver, WAIT).until(
        EC.presence_of_element_located(
            (By.XPATH, "//div[contains(@class,'DropdownMenuContent') and @role='menu']")
        )
    )
    time.sleep(1)


def configurar_nano_video_9x16_x1_fast(driver):
    _log("[HUMBLE] Configurando Nano: Vídeo + 9:16 + x1 + Fast [Lower Priority]")

    painel = _wait_visible(
        driver,
        By.XPATH,
        "//div[contains(@class,'DropdownMenuContent') and @role='menu']",
        descricao="painel Nano",
    )

    painel.find_element(
        By.XPATH, ".//button[.//i[text()='videocam'] or contains(., 'Vídeo')]"
    ).click()
    time.sleep(0.5)

    painel.find_element(
        By.XPATH, ".//button[.//i[text()='crop_9_16'] or contains(., '9:16')]"
    ).click()
    time.sleep(0.5)

    painel.find_element(
        By.XPATH, ".//button[normalize-space()='x1']"
    ).click()
    time.sleep(0.5)

    _wait_click(
        driver,
        By.XPATH,
        "//button[contains(., 'Veo 3.1 - Fast')]"
        " | //span[contains(., 'Veo 3.1 - Fast')]"
        " | //div[@role='menuitem'][contains(., 'Veo 3.1 - Fast')]",
        timeout=15,
        descricao="submenu Veo 3.1 - Fast",
    )
    time.sleep(1)

    _wait_click(
        driver,
        By.XPATH,
        "//button[contains(., 'Veo 3.1 - Fast [Lower Priority]')]"
        " | //span[contains(., 'Veo 3.1 - Fast [Lower Priority]')]"
        " | //div[@role='menuitem'][contains(., 'Veo 3.1 - Fast [Lower Priority]')]",
        timeout=15,
        descricao="modelo Veo 3.1 - Fast [Lower Priority]",
    )
    time.sleep(1)


def _ler_texto_prompt_box(box):
    try:
        txt = box.get_attribute("innerText")
        return (txt or "").strip()
    except Exception:
        return ""


def _debug_dump_cards(driver):
    cards = driver.find_elements(By.XPATH, "//*[@data-tile-id]")
    _log(f"[DEBUG CARDS] Total de cards visíveis: {len(cards)}")
    for idx, card in enumerate(cards[:10], 1):
        try:
            txt = (card.text or "").replace("\n", " ")[:200]
        except Exception:
            txt = "<sem texto>"
        try:
            tid = card.get_attribute("data-tile-id")
        except Exception:
            tid = None
        _log(f"[DEBUG CARDS] #{idx} tile_id={tid} texto={txt!r}")


def preencher_prompt(driver, prompt: str):
    _log("[HUMBLE] Preenchendo prompt (COLAR de uma vez)...")

    box = _wait_visible(
        driver,
        By.XPATH,
        "//div[@role='textbox' and @contenteditable='true']",
        timeout=20,
        descricao="campo prompt",
    )

    driver.execute_script(
        "arguments[0].scrollIntoView({block: 'center', inline: 'center'});", box
    )
    time.sleep(0.3)

    try:
        driver.execute_script("arguments[0].focus();", box)
        driver.execute_script("arguments[0].click();", box)
    except Exception:
        try:
            overlays = driver.find_elements(
                By.XPATH,
                "//div[contains(@class,'sc-d23b167b-0') or contains(@class,'overlay')]",
            )
            for o in overlays:
                driver.execute_script("arguments[0].remove();", o)
            time.sleep(0.3)
            driver.execute_script("arguments[0].focus();", box)
            driver.execute_script("arguments[0].click();", box)
        except Exception:
            pass

    time.sleep(0.4)

    antes = _ler_texto_prompt_box(box)
    _log(f"[DEBUG PROMPT] Estado inicial: {antes[:120]!r}")

    try:
        box.send_keys(Keys.CONTROL, "a")
        time.sleep(0.2)
    except Exception:
        pass

    pyperclip.copy(prompt)
    box.send_keys(Keys.CONTROL, "v")
    time.sleep(1.2)

    depois = _ler_texto_prompt_box(box)
    _log(f"[DEBUG PROMPT] Depois de colar: {depois[:200]!r}")
    _log(f"[DEBUG PROMPT] Tamanho esperado={len(prompt)} | atual={len(depois)}")

    if prompt[:80].strip() not in depois:
        raise HumbleFlowError("Prompt não colou integralmente no campo.")


def clicar_criar(driver):
    _log("[HUMBLE] Clicando em Criar...")
    _wait_click(
        driver,
        By.XPATH,
        "//button[.//i[text()='arrow_forward'] or .//span[normalize-space()='Criar']]",
        timeout=20,
        descricao="botão Criar",
    )
    time.sleep(2)
    _debug_dump_cards(driver)


# ============================================================================
#   MONITOR DE GERAÇÃO (COM % EM UMA LINHA)
# ============================================================================

ERRO_KEYWORDS = ["Falha", "Erro", "Violação"]


def _print_progress_inline(msg: str):
    sys.stdout.write("\r" + msg.ljust(120))
    sys.stdout.flush()


def _finish_progress_inline(msg: str = ""):
    if msg:
        sys.stdout.write("\r" + msg.ljust(120) + "\n")
    else:
        sys.stdout.write("\n")
    sys.stdout.flush()


def _safe_len(iterable):
    try:
        return len(iterable)
    except Exception:
        return "?"


def _listar_cards(driver):
    return driver.find_elements(By.XPATH, "//*[@data-tile-id]")


def _card_mais_recente(driver):
    cards = _listar_cards(driver)
    return cards[0] if cards else None


def _encontrar_card_por_prompt(driver, prompt: str):
    trecho = prompt[:60].replace("'", " ").strip()
    if not trecho:
        _log("[HUMBLE] _encontrar_card_por_prompt: trecho vazio, retornando None.")
        return None

    _log(f"[HUMBLE] Procurando card pelo trecho: {trecho!r}")

    cards = _listar_cards(driver)
    _log(f"[HUMBLE] {_safe_len(cards)} cards encontrados na lista para fallback.")

    trecho_lower = trecho.lower()
    candidato_com_video = None
    candidato_sem_video = None

    for card in cards:
        try:
            txt = (card.text or "").lower()
        except Exception:
            continue

        if trecho_lower and trecho_lower not in txt:
            continue

        try:
            tem_video = bool(
                card.find_elements(
                    By.XPATH,
                    ".//video | .//*[contains(@src,'/fx/api/trpc/media.getMediaUrlRedirect')]",
                )
            )
        except Exception:
            tem_video = False

        if tem_video and not candidato_com_video:
            candidato_com_video = card
        elif not tem_video and not candidato_sem_video:
            candidato_sem_video = card

    if candidato_com_video:
        _log("[HUMBLE] Card encontrado pelo texto + vídeo pronto (estado PRONTO).")
        return candidato_com_video
    if candidato_sem_video:
        _log("[HUMBLE] Card encontrado pelo texto sem vídeo (fallback).")
        return candidato_sem_video

    _log("[HUMBLE] Nenhum card compatível encontrado.")
    return None


def _obter_tile_id(card):
    try:
        tid = card.get_attribute("data-tile-id")
        if tid:
            return tid
    except Exception:
        pass

    try:
        el = card.find_element(By.XPATH, ".//*[@data-tile-id]")
        tid = el.get_attribute("data-tile-id")
        if tid:
            return tid
    except Exception:
        pass

    return None


def _encontrar_card_por_tile_id(driver, tile_id: str):
    if not tile_id:
        return None

    try:
        card = driver.find_element(
            By.XPATH,
            f"//*[@data-tile-id='{tile_id}']"
        )
        return card
    except Exception:
        return None


def _texto_card(card) -> str:
    try:
        return " ".join((card.text or "").split())
    except Exception:
        return ""


def _card_tem_video_ou_preview(card) -> bool:
    xpaths = [
        ".//video",
        ".//img",
        ".//canvas",
        ".//button[.//video]",
        ".//*[contains(@aria-label,'Open') or contains(@aria-label,'Abrir')]",
        ".//*[contains(@aria-label,'Download') or contains(@aria-label,'Baixar')]",
        ".//i[text()='download']",
    ]
    for xp in xpaths:
        try:
            if card.find_elements(By.XPATH, xp):
                return True
        except Exception:
            pass
    return False


def _card_tem_sinal_processando(card) -> bool:
    xpaths = [
        ".//*[contains(text(), '%')]",
        ".//*[contains(text(), 'Generating')]",
        ".//*[contains(text(), 'Gerando')]",
        ".//*[contains(text(), 'Processing')]",
        ".//*[contains(text(), 'Processando')]",
        ".//*[contains(@aria-label, 'loading')]",
        ".//*[contains(@class, 'spin')]",
        ".//*[contains(@class, 'loading')]",
        ".//svg[contains(@class,'animate-spin')]",
    ]
    for xp in xpaths:
        try:
            if card.find_elements(By.XPATH, xp):
                return True
        except Exception:
            pass
    return False


def _card_tem_erro(card) -> bool:
    termos = [
        "Falha", "Erro", "Violação", "Violation",
        "Failed", "Error", "Something went wrong",
        "Não foi possível", "Couldn’t generate", "Couldn't generate",
    ]
    try:
        txt = _texto_card(card).lower()
    except Exception:
        txt = ""
    return any(t.lower() in txt for t in termos)


def _extrair_percentual_card(card) -> int | None:
    """
    Tenta achar a porcentagem visível no card, ex.: 1%, 34%, 100%.
    Retorna int ou None.
    """
    candidatos_xpath = [
        ".//*[contains(text(), '%')]",
        ".//span[contains(text(), '%')]",
        ".//div[contains(text(), '%')]",
        ".//p[contains(text(), '%')]",
    ]

    textos = []

    for xp in candidatos_xpath:
        try:
            els = card.find_elements(By.XPATH, xp)
            for el in els:
                try:
                    txt = (el.text or "").strip()
                    if txt:
                        textos.append(txt)
                except Exception:
                    pass
        except Exception:
            pass

    try:
        txt_card = (card.text or "").strip()
        if txt_card:
            textos.append(txt_card)
    except Exception:
        pass

    for txt in textos:
        m = re.search(r'(?<!\d)(100|[1-9]?\d)\s*%', txt)
        if m:
            try:
                return int(m.group(1))
            except Exception:
                pass

    return None


def _snapshot_card(card):
    try:
        txt = _texto_card(card)
    except Exception:
        txt = ""

    try:
        html = card.get_attribute("innerHTML") or ""
    except Exception:
        html = ""

    percentual = _extrair_percentual_card(card)

    return {
        "texto": txt[:500],
        "tam_html": len(html),
        "tem_video": _card_tem_video_ou_preview(card),
        "tem_processando": _card_tem_sinal_processando(card),
        "tem_erro": _card_tem_erro(card),
        "percentual": percentual,
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
        if tile_id:
            card = _encontrar_card_por_tile_id(driver, tile_id)

        if not card:
            card = _card_mais_recente(driver)

        if not card:
            card = _encontrar_card_por_prompt(driver, prompt)

        if not card:
            if ultimo_status_inline != "sem_card":
                _print_progress_inline("[HUMBLE] Gerando vídeo... aguardando card aparecer")
                ultimo_status_inline = "sem_card"
                linha_progresso_ativa = True
            time.sleep(2)
            continue

        if not tile_id:
            tile_id = _obter_tile_id(card)
            if tile_id:
                if linha_progresso_ativa:
                    _finish_progress_inline()
                    linha_progresso_ativa = False
                _log(f"[HUMBLE] Tile ID detectado: {tile_id}")

        snap = _snapshot_card(card)

        if snap["tem_erro"]:
            if linha_progresso_ativa:
                _finish_progress_inline("[HUMBLE] Geração falhou.")
            _log("❌ Card em estado de erro detectado por texto real.")
            return {"status": "erro", "tile_id": tile_id}

        if snap["tem_video"]:
            if linha_progresso_ativa:
                pct_final = snap.get("percentual")
                msg_final = (
                    f"[HUMBLE] Gerando vídeo... {pct_final}% | pronto!"
                    if pct_final is not None else
                    "[HUMBLE] Gerando vídeo... pronto!"
                )
                _finish_progress_inline(msg_final)
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

        if not viu_sinal_de_vida:
            if time.time() - ultimo_movimento > 45:
                if linha_progresso_ativa:
                    _finish_progress_inline("[HUMBLE] Geração falhou por falta de atividade.")
                _log("❌ Card sem qualquer sinal de vida por 45s. Assumindo erro silencioso.")
                return {"status": "erro", "tile_id": tile_id}
        else:
            if time.time() - ultimo_movimento > 90:
                if linha_progresso_ativa:
                    _finish_progress_inline("[HUMBLE] Geração falhou por estagnação.")
                _log("❌ Card ficou estagnado por 90s após sinais de vida. Assumindo erro.")
                return {"status": "erro", "tile_id": tile_id}

        time.sleep(3)

    if linha_progresso_ativa:
        _finish_progress_inline("[HUMBLE] Timeout na geração do vídeo.")
    raise HumbleFlowError("Timeout aguardando geração do vídeo.")


# ============================================================================
#   DOWNLOAD / CONCLUSÃO
# ============================================================================


def abrir_video_pronto(driver, tile_id: str | None = None, prompt: str | None = None):
    _log("[HUMBLE] Abrindo página do vídeo pronto...")

    card = None
    if tile_id:
        _log(f"[HUMBLE] Tentando localizar card pelo tile_id: {tile_id}")
        card = _encontrar_card_por_tile_id(driver, tile_id)

    if not card and prompt:
        _log("[HUMBLE] Tentando localizar card pelo prompt (fallback)...")
        card = _encontrar_card_por_prompt(driver, prompt)

    if not card:
        _log("[HUMBLE] ERRO: Não encontrei card do vídeo pronto.")
        if DEBUG_NAO_FECHAR:
            input("DEBUG: ENTER depois de olhar o Flow...")
        raise HumbleFlowError("Não encontrei card do vídeo pronto.")

    _log("[HUMBLE] Card do vídeo localizado, procurando elemento clicável...")

    alvo_click = None
    try:
        alvo_click = card.find_element(
            By.XPATH,
            ".//button[contains(@class,'sc-d64366c4-1') and .//video]"
        )
        _log("[HUMBLE] Botão contendo <video> encontrado para clique.")
    except Exception:
        alvo_click = None

    if alvo_click is None:
        try:
            alvo_click = card.find_element(By.XPATH, ".//video")
            _log("[HUMBLE] <video> encontrado para clique direto.")
        except Exception:
            alvo_click = None

    if alvo_click is None:
        _log("[HUMBLE] ERRO: Encontrei o card, mas não achei botão/vídeo clicável.")
        if DEBUG_NAO_FECHAR:
            input("DEBUG: ENTER depois de olhar o Flow...")
        raise HumbleFlowError("Encontrei o card, mas não achei elemento clicável (botão/vídeo).")

    driver.execute_script(
        "arguments[0].scrollIntoView({block:'center', inline:'center'});",
        alvo_click,
    )
    time.sleep(0.4)
    try:
        alvo_click.click()
        _log("✔ Clique normal no card/vídeo disparado.")
    except Exception:
        _log("ℹ Clique normal falhou, tentando clique via JS...")
        driver.execute_script("arguments[0].click();", alvo_click)
        _log("✔ Clique via JS no card/vídeo disparado.")

    time.sleep(4)


def esperar_botao_baixar(driver, timeout=120):
    xpath = "//button[.//i[text()='download'] and .//div[contains(.,'Baixar')]]"
    return WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable((By.XPATH, xpath))
    )


def esperar_opcao_720p(driver, timeout=30):
    xpath = (
        "//button[@role='menuitem']"
        "[.//span[text()='720p'] and .//span[contains(.,'Tamanho original')]]"
    )
    return WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable((By.XPATH, xpath))
    )


def _snapshot_mp4s(diretorio: Path) -> set[str]:
    diretorio.mkdir(parents=True, exist_ok=True)
    return {p.name for p in diretorio.glob("*.mp4")}


def _esperar_download_mp4(download_dir: Path, antes: set[str], timeout=180) -> Path:
    fim = time.time() + timeout
    ultimo_temp = None

    while time.time() < fim:
        crdownloads = list(download_dir.glob("*.crdownload"))
        novos_mp4 = [p for p in download_dir.glob("*.mp4") if p.name not in antes]

        if novos_mp4 and not crdownloads:
            novos_mp4.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            arquivo = novos_mp4[0]
            _log(f"✔ Download concluído em: {arquivo}")
            return arquivo

        if crdownloads:
            crdownloads.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            atual = crdownloads[0]
            if ultimo_temp != atual.name:
                _log(f"ℹ Baixando: {atual.name}")
                ultimo_temp = atual.name

        time.sleep(1)

    raise HumbleFlowError("Timeout aguardando arquivo .mp4 no diretório temporário.")


def baixar_video_720p(
    driver,
    destino_dir: Path | None = None,
    nome_arquivo: str | None = None,
):
    download_dir = Path(DOWNLOAD_DIR)
    destino_dir = Path(destino_dir or DOWNLOAD_DIR)

    download_dir.mkdir(parents=True, exist_ok=True)
    destino_dir.mkdir(parents=True, exist_ok=True)

    _log(f"[HUMBLE] Iniciando download 720p...")
    _log(f"[HUMBLE] Pasta temporária: {download_dir}")
    _log(f"[HUMBLE] Pasta final: {destino_dir}")

    antes = _snapshot_mp4s(download_dir)

    btn_baixar = esperar_botao_baixar(driver)
    btn_baixar.click()
    time.sleep(0.8)

    btn_720 = esperar_opcao_720p(driver)
    btn_720.click()

    arquivo_baixado = _esperar_download_mp4(download_dir, antes)

    nome_final = nome_arquivo or f"Make_video_of_{datetime.now().strftime('%Y%m%d%H%M%S')}.mp4"
    destino_final = destino_dir / nome_final

    if destino_final.exists():
        destino_final.unlink()

    shutil.move(str(arquivo_baixado), str(destino_final))
    _log(f"✔ Arquivo movido para: {destino_final}")

    return destino_final


def voltar_para_lista_videos(driver):
    _log("[HUMBLE] Concluindo e voltando para lista de prompts...")
    xpath_concluir = (
        "//button[.//i[text()='check'] and .//div[contains(.,'Concluir')]]"
    )
    btn = WebDriverWait(driver, 60).until(
        EC.element_to_be_clickable((By.XPATH, xpath_concluir))
    )
    btn.click()
    time.sleep(3)


def gerar_video_humble(
    driver,
    prompt: str,
    destino_dir: Path | None = None,
):
    marker = f"[DBG-{uuid.uuid4().hex[:8]}]"
    _log(f"[DEBUG PROMPT] Marker (SO LOG): {marker}")

    preencher_prompt(driver, prompt)

    _log("[HUMBLE] Enviando prompt com ENTER...")
    box = driver.find_element(
        By.XPATH,
        "//div[@role='textbox' and @contenteditable='true']",
    )
    box.send_keys(Keys.ENTER)
    time.sleep(2)
    _log("✔ Prompt enviado ao Flow.")

    resultado = aguardar_geracao_video(driver, prompt)
    status = resultado.get("status")
    tile_id = resultado.get("tile_id")

    if status != "ok":
        raise HumbleFlowError(f"Geração falhou com status={status!r}")

    _log("✔ Geração concluída. Abrindo card do vídeo...")
    abrir_video_pronto(driver, tile_id=tile_id, prompt=prompt)
    arquivo_final = baixar_video_720p(driver, destino_dir=destino_dir)

    _log(f"✔ Download concluído em: {arquivo_final}")
    _log("✔ Voltando para tela de prompts.")
    voltar_para_lista_videos(driver)

    return arquivo_final