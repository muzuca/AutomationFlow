# automation_flow.py
# Dependências:
#   pip install selenium python-dotenv pyautogui pygetwindow pillow pyperclip pytesseract

import os
import time
import subprocess
import pathlib

import pyautogui
import pygetwindow as gw
import pyperclip
from dotenv import load_dotenv

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys

import pytesseract
from PIL import Image

# ajuste o caminho se o Tesseract estiver em outro lugar
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# pasta de downloads (ajuste se for diferente)
DOWNLOAD_DIR = pathlib.Path(r"C:\Users\vinic\Downloads")

# ─────────────────────────────────────────────
# CONFIG GERAL
# ─────────────────────────────────────────────
load_dotenv()
EMAIL        = os.getenv("FG_EMAIL")
SENHA        = os.getenv("FG_SENHA")
PROMPT_VIDEO = os.getenv(
    "VIDEO_PROMPT",
    "Um pôr do sol incrível na praia com ondas suaves"
)

BASE_DIR          = pathlib.Path(__file__).parent
CHROMEDRIVER_PATH = str(BASE_DIR / "chromedriver.exe")  # mesmo usado pelo Guru

EXE_PATH      = r"C:\Users\vinic\AppData\Local\ferramentas_guru_v9\ferramentas-guru-v9.exe"
DEBUG_PORT_FG = 9222
WAIT          = 20

pyautogui.FAILSAFE = True
pyautogui.PAUSE    = 0.2

# ─────────────────────────────────────────────
# HELPERS SELENIUM (GURU)
# ─────────────────────────────────────────────
def attach_to_chrome(port, chromedriver_path=None):
    opts = Options()
    opts.add_experimental_option("debuggerAddress", f"127.0.0.1:{port}")
    opts.add_argument("--no-sandbox")
    svc = Service(chromedriver_path) if chromedriver_path else Service()
    driver = webdriver.Chrome(service=svc, options=opts)
    print(f"  ✔ Conectado ao Chrome na porta {port} — título: {driver.title}")
    return driver

def wait_and_click(driver, by, value, timeout=WAIT, description="elemento"):
    print(f"  → Aguardando: {description}")
    el = WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable((by, value))
    )
    el.click()
    print(f"  ✔ Clicado: {description}")
    return el

# ─────────────────────────────────────────────
# HELPERS PYAUTOGUI / OCR
# ─────────────────────────────────────────────
def focar_janela_flow(timeout=25):
    alvo = "labs.google/fx"
    print(f"  → Procurando janela do Flow contendo: {alvo!r}")
    for _ in range(timeout):
        wins = gw.getWindowsWithTitle(alvo)
        wins = [w for w in wins if "Visual Studio Code" not in w.title]
        if wins:
            win = wins[0]
            try:
                win.activate()
            except Exception:
                pass
            time.sleep(0.7)
            print(f"  ✔ Janela do Flow focada: {win.title}")
            return win
        time.sleep(1)
    raise RuntimeError(f"Janela do Flow contendo '{alvo}' não encontrada em {timeout}s.")

def focar_janela_login_google(timeout=25):
    alvo = "Fazer login nas Contas do Google"
    print(f"  → Procurando janela de login do Google contendo: {alvo!r}")
    for _ in range(timeout):
        wins = gw.getWindowsWithTitle(alvo)
        wins = [w for w in wins if "Visual Studio Code" not in w.title]
        if wins:
            win = wins[0]
            try:
                win.activate()
            except Exception:
                pass
            time.sleep(0.7)
            print(f"  ✔ Janela de login focada: {win.title}")
            return win
        time.sleep(1)
    print(f"  ✗ Janela de login do Google não encontrada em {timeout}s.")
    return None

def click_relativo_na_janela(win, x_pct, y_pct, descricao=""):
    x = win.left + int(win.width * x_pct)
    y = win.top  + int(win.height * y_pct)
    print(f"  → Clicando em {descricao} na janela ({x},{y}) "
          f"[{x_pct*100:.1f}%, {y_pct*100:.1f}%]")
    pyautogui.click(x, y)
    time.sleep(0.3)

def digitar_na_janela(texto):
    pyautogui.write(texto, interval=0.03)

def ocr_click_in_window(win, texto_alvo, region_rel=None, lang="por+eng"):
    x0, y0, w, h = win.left, win.top, win.width, win.height

    if region_rel:
        rx0, ry0, rx1, ry1 = region_rel
        x1 = x0 + int(w * rx1)
        y1 = y0 + int(h * ry1)
        x0 = x0 + int(w * rx0)
        y0 = y0 + int(h * ry0)
    else:
        x1 = x0 + w
        y1 = y0 + h

    print(f"  → Screenshot para OCR na região ({x0},{y0})–({x1},{y1})...")
    img = pyautogui.screenshot(region=(x0, y0, x1 - x0, y1 - y0))

    debug_path = BASE_DIR / f"ocr_debug_{texto_alvo.replace(' ', '_')}.png"
    img.save(debug_path)
    print(f"    ✔ Imagem salva em {debug_path}")

    data = pytesseract.image_to_data(img, lang=lang, output_type=pytesseract.Output.DICT)

    alvo_lower = texto_alvo.lower()
    for i, palavra in enumerate(data["text"]):
        if not palavra.strip():
            continue
        if alvo_lower in palavra.lower():
            bx = data["left"][i]
            by = data["top"][i]
            bw = data["width"][i]
            bh = data["height"][i]
            cx = x0 + bx + bw // 2
            cy = y0 + by + bh // 2
            print(f"    ✔ Encontrado '{palavra}' em ({cx},{cy}), clicando...")
            pyautogui.click(cx, cy)
            time.sleep(0.4)
            return True

    print(f"    ✗ Texto '{texto_alvo}' não encontrado via OCR.")
    return False

def detectar_texto_na_janela(win, texto_alvo, region_rel=None, lang="por+eng"):
    x0, y0, w, h = win.left, win.top, win.width, win.height

    if region_rel:
        rx0, ry0, rx1, ry1 = region_rel
        x1 = x0 + int(w * rx1)
        y1 = y0 + int(h * ry1)
        x0 = x0 + int(w * rx0)
        y0 = y0 + int(h * ry0)
    else:
        x1 = x0 + w
        y1 = y0 + h

    print(f"  → OCR (somente leitura) na região ({x0},{y0})–({x1},{y1}) para '{texto_alvo}'...")
    img = pyautogui.screenshot(region=(x0, y0, x1 - x0, y1 - y0))

    debug_path = BASE_DIR / f"ocr_debug_check_{texto_alvo.replace(' ', '_')}.png"
    img.save(debug_path)
    print(f"    ✔ Imagem salva em {debug_path}")

    data = pytesseract.image_to_data(img, lang=lang, output_type=pytesseract.Output.DICT)
    alvo_lower = texto_alvo.lower()

    for palavra in data["text"]:
        if not palavra.strip():
            continue
        if alvo_lower in palavra.lower():
            print(f"    ✔ Texto '{texto_alvo}' encontrado via OCR ('{palavra}').")
            return True

    print(f"    ✗ Texto '{texto_alvo}' NÃO encontrado via OCR.")
    return False

def detectar_aviso_bloqueio(win):
    print("  → Verificando se há aviso de conta bloqueada (OCR 'Entendi')...")
    region_aviso = (0.10, 0.10, 0.90, 0.90)
    if detectar_texto_na_janela(win, "Entendi", region_rel=region_aviso):
        print("  ❌ Aviso detectado na tela (botão 'Entendi' presente).")
        return True
    print("  ✔ Nenhum aviso detectado (botão 'Entendi' não encontrado).")
    return False

def fechar_janela_flow(win):
    try:
        print(f"  → Fechando janela passada (title='{win.title}')...")
        win.close()
        print(f"  ✔ Janela fechada: {win.title}")
    except Exception as e:
        print(f"  ⚠ Não consegui fechar a janela passada: {e}")

def fechar_todas_janelas_flow_ou_login():
    """Fecha todas as janelas relacionadas ao Flow ou login do Google."""
    padroes = ["labs.google/fx", "Fazer login nas Contas do Google"]
    for alvo in padroes:
        wins = gw.getWindowsWithTitle(alvo)
        for w in wins:
            try:
                print(f"  → Fechando janela residual: {w.title}")
                w.close()
                time.sleep(0.5)
            except Exception as e:
                print(f"  ⚠ Erro ao fechar janela residual '{w.title}': {e}")

# ─────────────────────────────────────────────
# FECHAMENTO VIA ALT+F4
# ─────────────────────────────────────────────
def finalizar_flow_alt_f4():
    print("\n[FINALIZAÇÃO] Fechando janelas do Flow com Alt+F4...")
    try:
        for _ in range(3):
            wins = gw.getWindowsWithTitle("labs.google/fx")
            wins = [w for w in wins if "Visual Studio Code" not in w.title]
            if not wins:
                break
            win = wins[0]
            try:
                win.activate()
                time.sleep(0.5)
            except Exception:
                pass
            pyautogui.hotkey("alt", "f4")
            time.sleep(1.5)
        print("  ✔ Tentativa de fechar Flow concluída.")
    except Exception as e:
        print(f"  ⚠ Erro ao tentar fechar Flow com Alt+F4: {e}")

def finalizar_guru_alt_f4():
    print("[FINALIZAÇÃO] Fechando Ferramentas Guru com Alt+F4...")
    try:
        wins = gw.getWindowsWithTitle("Ferramentas Guru")
        if wins:
            win = wins[0]
            try:
                win.activate()
                time.sleep(0.5)
            except Exception:
                pass
            pyautogui.hotkey("alt", "f4")
            time.sleep(1.5)
            print("  ✔ Janela principal do Guru fechada com Alt+F4.")
        else:
            print("  ℹ Nenhuma janela 'Ferramentas Guru' encontrada para fechar.")
    except Exception as e:
        print(f"  ⚠ Erro ao tentar fechar Guru com Alt+F4: {e}")

# ─────────────────────────────────────────────
# ETAPAS — FERRAMENTAS GURU (SELENIUM)
# ─────────────────────────────────────────────
def etapa1_abrir_guru():
    print("\n[ETAPA 1] Abrindo Ferramentas Guru com porta de debug...")
    subprocess.Popen([
        EXE_PATH,
        f"--remote-debugging-port={DEBUG_PORT_FG}",
        "--remote-allow-origins=*"
    ])
    time.sleep(8)
    print("  ✔ Guru iniciado.")

def etapa2_login(driver):
    print("\n[ETAPA 2] Login no Guru...")

    email_field = WebDriverWait(driver, WAIT).until(
        EC.presence_of_element_located((By.CSS_SELECTOR,
            "input[type='email'], input[placeholder*='email'], input[name='email']"))
    )
    email_field.clear()
    email_field.send_keys(EMAIL)

    senha_field = driver.find_element(By.CSS_SELECTOR,
        "input[type='password'], input[name='password'], input[name='senha']")
    senha_field.clear()
    senha_field.send_keys(SENHA)

    wait_and_click(driver,
        By.XPATH,
        "//button[contains(translate(text(),'entrar','ENTRAR'),'ENTRAR') "
        "or contains(text(),'Login')]",
        description="botão ENTRAR / Login")
    time.sleep(4)
    print("  ✔ Login enviado.")

def etapa3_fechar_popup(driver):
    print("\n[ETAPA 3] Verificando popup de atualização...")
    try:
        btn = WebDriverWait(driver, 8).until(
            EC.element_to_be_clickable((By.XPATH,
                "//button[contains(text(),'Atualizar Agora') "
                "or contains(text(),'Atualizar agora')]"))
        )
        btn.click()
        print("  ✔ Popup fechado.")
        time.sleep(2)
    except Exception:
        print("  ℹ Nenhum popup detectado.")

def etapa4_buscar_flow_e_abrir(driver):
    print("\n[ETAPA 4] Buscando 'google flow veo 3' e clicando em Abrir...")

    fechar_todas_janelas_flow_ou_login()

    search_box = WebDriverWait(driver, WAIT).until(
        EC.presence_of_element_located((By.CSS_SELECTOR,
            "input[type='search'], input[placeholder*='Buscar'], "
            "input[placeholder*='buscar'], input[placeholder*='Pesquisar']"))
    )
    search_box.clear()
    search_box.send_keys("google flow veo 3")
    search_box.send_keys(Keys.ENTER)
    time.sleep(4)

    wait_and_click(driver,
        By.CSS_SELECTOR, "button.btn.btn-primary",
        description="primeiro botão ▶ Abrir")
    print("  ✔ Clicado em Abrir; aguardando janela do Flow abrir...")
    time.sleep(8)

# ─────────────────────────────────────────────
# ETAPAS — FLOW (PYAUTOGUI + OCR)
# ─────────────────────────────────────────────
def etapa5_flow_trocar_url():
    print("\n[ETAPA 5] Focando janela do Flow (ou login) e trocando a URL...")

    try:
        win = focar_janela_flow(timeout=10)
        modo = "flow"
    except RuntimeError:
        print("  ℹ Janela do Flow não encontrada, tentando janela de login do Google...")
        win = focar_janela_login_google(timeout=15)
        if win is None:
            raise RuntimeError("Nenhuma janela do Flow nem de login do Google encontrada.")
        modo = "login"

    print(f"  ℹ Modo detectado na etapa 5: {modo}")

    center_x = win.left + win.width // 2
    center_y = win.top  + win.height // 8
    pyautogui.click(center_x, center_y)
    time.sleep(0.4)

    pyautogui.press("f6")
    time.sleep(0.5)
    pyautogui.hotkey("ctrl", "a")
    time.sleep(0.2)
    pyautogui.write("https://labs.google/fx/pt/tools/flow", interval=0.03)
    pyautogui.press("enter")
    print("  ✔ URL trocada para https://labs.google/fx/pt/tools/flow")
    time.sleep(6)

    return win

def etapa6_flow_novo_projeto(win):
    """
    Clica em '+ Novo projeto' e depois em 'Nano Banana 2'.
    """
    print("\n[ETAPA 6] '+ Novo projeto' e 'Nano Banana 2' via OCR...")

    click_relativo_na_janela(win, 0.50, 0.80, "+ Novo projeto")
    time.sleep(5)

    print("  → Procurando texto 'Nano' na parte inferior (botão Nano Banana 2)...")
    ok = ocr_click_in_window(
        win,
        "Nano",
        region_rel=(0.3, 0.82, 1.0, 1.0)
    )
    if ok:
        print("  ✔ Botão 'Nano Banana 2' clicado via OCR.")
        time.sleep(2)
        return True

    print("  ⚠ OCR não achou 'Nano'. Tentando clique aproximado na região do botão Nano...")
    x0, y0, w, h = win.left, win.top, win.width, win.height
    cx = x0 + int(w * 0.65)
    cy = y0 + int(h * 0.90)
    print(f"  → Clicando fallback em possível botão Nano em ({cx},{cy})...")
    pyautogui.click(cx, cy)
    time.sleep(2)

    print("  ✔ Clique fallback para 'Nano Banana 2' realizado. Seguindo fluxo.")
    return True

def etapa7_flow_configurar_opcoes(win):
    """
    Configura: Vídeo, 9:16, x1, Veo 3.1 Fast [Lower Priority].
    """
    print("\n[ETAPA 7] Configurando opções via OCR dentro do menu do Nano...")

    try:
        win = focar_janela_flow(timeout=5)
    except RuntimeError:
        print("  ⚠ Não consegui refocar a janela do Flow, tentarei assim mesmo.")

    region_menu = (0.25, 0.55, 0.75, 0.90)
    region_dropdown = (0.25, 0.40, 0.75, 0.75)

    sucesso = True

    print("  → Selecionando 'Vídeo'...")
    if not ocr_click_in_window(win, "Vídeo", region_rel=region_menu):
        if not ocr_click_in_window(win, "Video", region_rel=region_menu):
            print("  ❌ Não consegui selecionar 'Vídeo/Video'.")
            sucesso = False
    time.sleep(1)

    print("  → (Opcional) Selecionando 'Frames'...")
    if not ocr_click_in_window(win, "Frames", region_rel=region_menu):
        print("  ⚠ Não consegui selecionar 'Frames', seguindo assim mesmo.")
    time.sleep(1)

    print("  → Selecionando '9:16'...")
    if not ocr_click_in_window(win, "9:16", region_rel=region_menu):
        print("  ❌ Não consegui selecionar '9:16'.")
        sucesso = False
    time.sleep(1)

    print("  → Selecionando 'x1'...")
    if not ocr_click_in_window(win, "x1", region_rel=region_menu):
        print("  ❌ Não consegui selecionar 'x1'.")
        sucesso = False
    time.sleep(1)

    print("  → Abrindo dropdown 'Veo 3.1 - Fast'...")
    if not ocr_click_in_window(win, "Fast", region_rel=region_menu):
        print("  ❌ Não consegui clicar em 'Fast'.")
        sucesso = False
    time.sleep(1.5)

    print("  → Selecionando 'Veo 3.1 - Fast [Lower Priority]'...")
    if not ocr_click_in_window(win, "Priority", region_rel=region_dropdown):
        print("  ❌ Não consegui selecionar 'Priority'.")
        sucesso = False
    time.sleep(1)

    if sucesso:
        print("  ✔ Opções críticas configuradas via OCR (confira na interface).")
    else:
        print("  ❌ Alguma opção crítica não foi configurada corretamente.")

    return sucesso

def etapa8_flow_preencher_prompt(win, prompt, texto_ancora=None):
    print("\n[ETAPA 8] Preenchendo prompt e enviando via OCR...")

    region_prompt = (0.03, 0.70, 0.97, 0.98)

    if texto_ancora:
        print(f"  → Procurando o campo de prompt pelo texto_ancora: {texto_ancora!r}...")
        if not ocr_click_in_window(win, texto_ancora, region_rel=region_prompt):
            print("  ⚠ Não achei texto_ancora, vou cair no fluxo placeholder/fallback.")
            texto_ancora = None

    if not texto_ancora:
        candidatos = ["criar", "Criar", "O que você quer criar", "quer criar"]
        print("  → Procurando o campo de prompt pelo placeholder...")
        clicou = False
        for texto in candidatos:
            if ocr_click_in_window(win, texto, region_rel=region_prompt):
                clicou = True
                break

        if not clicou:
            print("  ⚠ OCR não achou o placeholder, usando fallback por área grande.")
            click_relativo_na_janela(win, 0.5, 0.88, "área ampla do campo de prompt")

    time.sleep(0.7)

    pyautogui.hotkey("ctrl", "a")
    time.sleep(0.2)
    try:
        pyperclip.copy(prompt)
        pyautogui.hotkey("ctrl", "v")
    except Exception:
        digitar_na_janela(prompt)

    time.sleep(0.5)
    pyautogui.press("enter")
    print(f"  ✔ Prompt enviado: {prompt!r}")
    print("  🎬 Geração de vídeo iniciada.")

    time.sleep(1.0)
    pyautogui.hotkey("ctrl", "a")
    time.sleep(0.2)
    pyautogui.press("backspace")
    print("  ✔ Campo de prompt limpo após envio (para próximas gerações).")

# ─────────────────────────────────────────────
# ACOMPANHAR GERAÇÃO
# ─────────────────────────────────────────────
def etapa9_aguardar_geracao_video(win, timeout_segundos=180):
    """
    Vídeos rápidos (~30s) com OCR instável:
      - Se nunca enxergar % em 15s => 'erro'.
      - Se já tiver visto alguma % >= 25% e ficar 7s seguidos sem ver
        nenhuma % nova => 'ok'.
      - Abaixo de 25%, não assume ok, só continua esperando até timeout.
    """
    print("\n[ETAPA 9] Aguardando a geração do vídeo terminar (player)...")

    try:
        win = focar_janela_flow(timeout=5)
    except RuntimeError:
        print("  ⚠ Não consegui refocar a janela do Flow, tentarei assim mesmo.")

    inicio = time.time()
    region_video = (0.05, 0.10, 0.95, 0.90)

    ultimo_percent_val = None
    instante_ultima_percent = None
    ja_teve_percent = False

    TEMPO_MAX_SEM_PERCENT_INICIAL = 15   # 15s sem nunca ver % => erro
    TEMPO_SEM_NOVA_PERCENT_PARA_OK = 7   # 7s sem % nova => ok (se >= limiar)
    LIMIAR_PERCENT_OK = 25               # só aceita "ok" se já passou de 25%

    ciclo = 0

    while True:
        agora = time.time()
        if agora - inicio > timeout_segundos:
            print("  ⚠ Tempo máximo de espera excedido, saindo da etapa 9.")
            return "timeout"

        x0, y0, w, h = win.left, win.top, win.width, win.height
        rx0, ry0, rx1, ry1 = region_video
        X0 = x0 + int(w * rx0)
        Y0 = y0 + int(h * ry0)
        X1 = x0 + int(w * rx1)
        Y1 = y0 + int(h * ry1)

        img = pyautogui.screenshot(region=(X0, Y0, X1 - X0, Y1 - Y0))

        if ciclo < 3:
            debug_path = BASE_DIR / f"ocr_debug_percent_region_ciclo_{ciclo}.png"
            img.save(debug_path)
            print(f"  ℹ Screenshot da região de % salvo em {debug_path}")
        ciclo += 1

        data = pytesseract.image_to_data(
            img, lang="por+eng", output_type=pytesseract.Output.DICT
        )
        palavras = [t for t in data["text"] if t.strip()]

        perc_values = []
        for t in palavras:
            t = t.strip()
            if t.endswith("%") and t[:-1].isdigit():
                perc_values.append(int(t[:-1]))

        if perc_values:
            max_perc = max(perc_values)

            if ultimo_percent_val is None or max_perc != ultimo_percent_val:
                print(f"  ⏳ Progresso: {max_perc}%")
                ultimo_percent_val = max_perc
                instante_ultima_percent = agora
                ja_teve_percent = True
        else:
            # nenhum % visível neste ciclo
            if not ja_teve_percent:
                if agora - inicio >= TEMPO_MAX_SEM_PERCENT_INICIAL:
                    print("  ❌ Nenhuma % apareceu em ~15s. Assumindo falha ou vídeo já pronto sem barra.")
                    return "erro"
            else:
                # já vimos alguma %, mas só podemos assumir ok se já passou do limiar
                if (
                    ultimo_percent_val is not None
                    and ultimo_percent_val >= LIMIAR_PERCENT_OK
                    and instante_ultima_percent is not None
                ):
                    tempo_desde_ultima = agora - instante_ultima_percent
                    if tempo_desde_ultima >= TEMPO_SEM_NOVA_PERCENT_PARA_OK:
                        print(f"  ✔ Mais de {TEMPO_SEM_NOVA_PERCENT_PARA_OK}s sem nova % (>= {LIMIAR_PERCENT_OK}%). Assumindo vídeo pronto.")
                        return "ok"

        time.sleep(1)

# ─────────────────────────────────────────────
# RETENTATIVAS DE GERAÇÃO
# ─────────────────────────────────────────────
def etapa10_tentar_gerar_video_com_retentativas(win, prompt, max_tentativas=5, texto_ancora=None):
    for tentativa in range(1, max_tentativas + 1):
        print(f"\n[ETAPA 10] Tentativa de geração #{tentativa}...")

        etapa8_flow_preencher_prompt(win, prompt, texto_ancora=texto_ancora)
        status = etapa9_aguardar_geracao_video(win)

        print(f"  ℹ etapa9 retornou '{status}'. Vou analisar os cards para decidir o próximo passo.")

        # 1) Se existir card de falha/erro/violação, NÃO segue adiante: reenvia depois de 5s
        if detectar_card_de_falha(win):
            print("  ❌ Card de falha/erro/violação encontrado. Vou aguardar 5s e tentar gerar novamente.")
            time.sleep(5)
            continue

        # 2) Se não há falha, verifica se os percentuais dos cards já sumiram
        if etapa11_aguardar_percentual_sumir(win):
            print("  ✔ Percentual sumiu dos cards e não há falha. Assumindo vídeo pronto.")
            return True

        # 3) Se chegou aqui, ainda tem % nos cards e não é falha explícita
        print("  ⚠ Ainda vejo percentual nos cards e não há falha clara. Vou tentar gerar novamente após 5s.")
        time.sleep(5)

    print("  ❌ Não consegui confirmar geração após várias tentativas (com possíveis falhas/erros).")
    return False

# ─────────────────────────────────────────────
# PÓS-GERAÇÃO: LISTA, PLAYER, DOWNLOAD
# ─────────────────────────────────────────────
def detectar_card_de_falha(win):
    """
    Verifica na coluna da esquerda se existe um card de erro:
    textos como 'Falha', 'Erro', 'Violação'.
    Retorna True se detectar.
    """
    print("  → Verificando se há card de FALHA/ERRO/VIOLAÇÃO na lista...")
    region_falha = (0.02, 0.20, 0.33, 0.95)

    x0, y0, w, h = win.left, win.top, win.width, win.height
    rx0, ry0, rx1, ry1 = region_falha
    X0 = x0 + int(w * rx0)
    Y0 = y0 + int(h * ry0)
    X1 = x0 + int(w * rx1)
    Y1 = y0 + int(h * ry1)

    img = pyautogui.screenshot(region=(X0, Y0, X1 - X0, Y1 - Y0))
    debug_path = BASE_DIR / "ocr_debug_card_falha.png"
    img.save(debug_path)
    print(f"    ✔ Screenshot do card de falha salvo em {debug_path}")

    data = pytesseract.image_to_data(
        img, lang="por+eng", output_type=pytesseract.Output.DICT
    )

    palavras = [t.lower() for t in data["text"] if t.strip()]
    gatilhos = ["falha", "erro", "violação", "violation"]

    for p in palavras:
        if any(g in p for g in gatilhos):
            print(f"    ❌ Card de falha/erro detectado pelo texto: '{p}'")
            return True

    print("    ✔ Nenhum card de falha/erro/violação detectado.")
    return False

def aguardar_percentual_sumir_nos_cards(win, timeout_segundos=300):
    inicio = time.time()
    region_cards = (0.30, 0.10, 0.95, 0.90)
    CICLOS_PARA_OK = 5   # ~15s (com sleep de 3s)
    ciclos_sem_percent = 0

    while True:
        agora = time.time()
        if agora - inicio > timeout_segundos:
            print("  ⚠ Tempo máximo de espera excedido (percentual nos cards).")
            return False

        x0, y0, w, h = win.left, win.top, win.width, win.height
        rx0, ry0, rx1, ry1 = region_cards
        X0 = x0 + int(w * rx0)
        Y0 = y0 + int(h * ry0)
        X1 = x0 + int(w * rx1)
        Y1 = y0 + int(h * ry1)

        img = pyautogui.screenshot(region=(X0, Y0, X1 - X0, Y1 - Y0))

        data = pytesseract.image_to_data(
            img, lang="por+eng", output_type=pytesseract.Output.DICT
        )
        palavras = [t for t in data["text"] if t.strip()]

        tem_percent = any(p.strip().endswith("%") and p[:-1].isdigit() for p in palavras)

        if tem_percent:
            ciclos_sem_percent = 0
        else:
            ciclos_sem_percent += 1

        if ciclos_sem_percent >= CICLOS_PARA_OK:
            print("  ✔ Percentual sumiu dos cards.")
            return True

        time.sleep(3)

def etapa11_aguardar_percentual_sumir(win):
    print("\n[ETAPA 11] Aguardando percentual sumir nos cards...")
    return aguardar_percentual_sumir_nos_cards(win)

def etapa12_abrir_player_do_video(win_lista):
    print("\n[ETAPA 12] Abrindo player do vídeo a partir da lista...")
    click_relativo_na_janela(win_lista, 0.15, 0.30, "card principal do vídeo")
    time.sleep(3)
    try:
        win_player = focar_janela_flow(timeout=5)
        return win_player
    except RuntimeError:
        print("  ⚠ Não achei nova janela específica do player; vou reutilizar a mesma janela da lista.")
        return win_lista

def etapa13_aguardar_baixar_720p(win):
    print("\n[ETAPA 13] Aguardando botão 'Baixar' e selecionando 720p...")

    x0, y0, w, h = win.left, win.top, win.width, win.height
    x_hover = x0 + int(w * 0.85)
    y_hover = y0 + int(h * 0.08)

    max_tentativas_baixar = 8   # ~8 * 2s = até ~16s esperando o botão
    max_tentativas_720p = 5

    for tentativa in range(1, max_tentativas_baixar + 1):
        print(f"  → Tentativa #{tentativa} de achar 'Baixar'...")

        print(f"  → Posicionando mouse perto do botão 'Baixar' em ({x_hover},{y_hover}) para forçar hover...")
        pyautogui.moveTo(x_hover, y_hover, duration=0.3)
        time.sleep(1.0)

        print("  → Procurando 'Baixar' na área superior direita...")
        region_baixar = (0.6, 0.0, 1.0, 0.25)
        ok_baixar = ocr_click_in_window(win, "Baixar", region_rel=region_baixar)
        if ok_baixar:
            print("  ✔ Botão 'Baixar' visível. Aguardando 2s...")
            time.sleep(2.0)
            break

        print("  ⚠ 'Baixar' ainda não apareceu. Aguardando 2s antes de tentar de novo...")
        time.sleep(2.0)

    else:
        print("  ❌ Não consegui localizar/clicar no botão 'Baixar' após várias tentativas.")
        return False, None

    for tentativa in range(1, max_tentativas_720p + 1):
        print(f"  → Tentativa #{tentativa} de achar '720p' no menu de download...")
        region_720p = (0.55, 0.15, 0.95, 0.70)
        ok_720 = ocr_click_in_window(win, "720p", region_rel=region_720p)
        if ok_720:
            t_inicio = time.time()
            print("  ✔ Resolução 720p selecionada. Download deve ter começado.")
            return True, t_inicio

        print("  ⚠ '720p' ainda não apareceu. Aguardando 2s antes de tentar de novo...")
        time.sleep(2.0)

    print("  ❌ Não consegui localizar/clicar em '720p' após várias tentativas.")
    return False, None

def etapa14_esperar_download_video(t_inicio_download, ext=".mp4", timeout=300):
    print("\n[ETAPA 14] Aguardando arquivo de vídeo na pasta de downloads...")

    pasta_downloads = os.path.join(os.path.expanduser("~"), "Downloads")
    limite = t_inicio_download - 10
    print(f"  ℹ t_inicio_download (epoch): {t_inicio_download}")
    print(f"  ℹ t_limite (t_inicio_download - margem): {limite}")
    print(f"  ℹ Monitorando pasta: {pasta_downloads}")

    fim = time.time() + timeout
    ultimo_arquivo = None

    while time.time() < fim:
        try:
            arquivos = [
                os.path.join(pasta_downloads, f)
                for f in os.listdir(pasta_downloads)
                if f.lower().endswith(ext)
            ]
        except Exception as e:
            print(f"  ⚠ Erro ao listar downloads: {e}")
            time.sleep(3)
            continue

        if arquivos:
            arquivo_mais_novo = max(arquivos, key=os.path.getmtime)
            mtime = os.path.getmtime(arquivo_mais_novo)
            if mtime >= limite:
                print(f"  ✔ Candidato encontrado: {os.path.basename(arquivo_mais_novo)}  |  mtime: {mtime}")
                ultimo_arquivo = arquivo_mais_novo
                break

        time.sleep(3)

    if not ultimo_arquivo:
        print("  ❌ Nenhum arquivo de vídeo recente encontrado no timeout.")
        return None

    return ultimo_arquivo

def etapa15_voltar_para_lista(win_player):
    print("\n[ETAPA 15] Voltando para a lista (botão 'Concluir')...")

    for tentativa in range(1, 4):
        print(f"  → Tentativa #{tentativa} de encontrar 'Concluir'...")

        try:
            click_relativo_na_janela(win_player, 0.10, 0.10, "área neutra para fechar popups/downloads")
            time.sleep(0.8)
        except Exception as e:
            print(f"  ⚠ Erro ao clicar em área neutra antes do 'Concluir': {e}")

        region_concluir = (0.72, 0.0, 1.0, 0.20)

        if ocr_click_in_window(win_player, "Concluir", region_rel=region_concluir):
            print("  ✔ Clicado em 'Concluir'. Voltando para a lista.")
            time.sleep(3)
            return True

        if ocr_click_in_window(win_player, "cluir", region_rel=region_concluir):
            print("  ✔ Clicado em 'Concluir' (via 'cluir'). Voltando para a lista.")
            time.sleep(3)
            return True

        print("  ⚠ 'Concluir' não encontrado nesta tentativa. Aguardando e tentando de novo...")
        time.sleep(3)

    print("  ❌ Não consegui clicar em 'Concluir' após várias tentativas.")
    return False

# ─────────────────────────────────────────────
# ORQUESTRAÇÃO POR CARD
# ─────────────────────────────────────────────
def rodar_fluxo_em_um_card(driver_fg, indice_card, prompt, primeiro_video, win_flow_existente=None):
    """
    primeiro_video=True: fluxo completo.
    primeiro_video=False: reaproveita a mesma tela do Flow.
    """
    print(f"\n[FLOW CARD #{indice_card}] Iniciando fluxo neste card (primeiro_video={primeiro_video})...")

    if primeiro_video:
        fechar_todas_janelas_flow_ou_login()

        try:
            driver_fg.switch_to.window(driver_fg.window_handles[0])
        except Exception as e:
            print(f"  ⚠ Não consegui focar a aba do Guru: {e}")

        time.sleep(2)

        if indice_card == 1:
            etapa4_buscar_flow_e_abrir(driver_fg)
        else:
            try:
                print("  → Buscando todos os botões 'Abrir' na lista de cards...")
                botoes = WebDriverWait(driver_fg, WAIT).until(
                    EC.presence_of_all_elements_located(
                        (By.XPATH, "//button[contains(., 'Abrir')]")
                    )
                )
                print(f"  ℹ Encontrados {len(botoes)} botões 'Abrir'.")
                idx = indice_card - 1
                if idx < 0 or idx >= len(botoes):
                    print(f"  ❌ Não existe botão 'Abrir' para o card #{indice_card} (len={len(botoes)}).")
                    return False, None

                botao = botoes[idx]
                print(f"  → Clicando no botão 'Abrir' do card #{indice_card}...")
                botao.click()
                print("  ✔ Clicado em Abrir; aguardando janela do Flow abrir...")
                time.sleep(8)

            except Exception as e:
                print(f"  ❌ Não consegui clicar no card #{indice_card}: {e}")
                return False, None

        try:
            win_flow = etapa5_flow_trocar_url()
        except RuntimeError as e:
            print(f"  ❌ Não consegui focar/trocar URL neste card: {e}")
            print("  → Tentando fechar a janela ativa com Alt+F4...")
            try:
                pyautogui.hotkey("alt", "f4")
                time.sleep(2)
            except Exception as e_hotkey:
                print(f"  ⚠ Erro ao enviar Alt+F4: {e_hotkey}")
            fechar_todas_janelas_flow_ou_login()
            try:
                driver_fg.switch_to.window(driver_fg.window_handles[0])
            except Exception as e2:
                print(f"  ⚠ Não consegui voltar o foco para o Guru: {e2}")
            return False, None

        time.sleep(4)

        if detectar_aviso_bloqueio(win_flow):
            print("  ❌ Aviso de bloqueio neste card.")
            fechar_janela_flow(win_flow)
            return False, None

        if not etapa6_flow_novo_projeto(win_flow):
            print("  ❌ Falha ao clicar em '+ Novo projeto / Nano'.")
            fechar_janela_flow(win_flow)
            return False, None

        if not etapa7_flow_configurar_opcoes(win_flow):
            print("  ❌ Falha ao configurar opções de vídeo.")
            fechar_janela_flow(win_flow)
            return False, None

        if not etapa10_tentar_gerar_video_com_retentativas(win_flow, prompt, max_tentativas=10, texto_ancora=None):
            print("  ❌ Falha na geração de vídeo neste card.")
            fechar_janela_flow(win_flow)
            return False, None

        if not etapa11_aguardar_percentual_sumir(win_flow):
            print("  ❌ Percentual não sumiu nos cards neste card.")
            fechar_janela_flow(win_flow)
            return False, None

        win_player = etapa12_abrir_player_do_video(win_flow)
        ok_download, t_clique = etapa13_aguardar_baixar_720p(win_player)
        if not ok_download or t_clique is None:
            print("  ❌ Não consegui acionar download neste card.")
            fechar_janela_flow(win_player)
            return False, None

        arquivo = etapa14_esperar_download_video(t_clique, ext=".mp4", timeout=300)
        if not arquivo:
            print("  ❌ Download não detectado neste card.")
            fechar_janela_flow(win_player)
            return False, None

        if not etapa15_voltar_para_lista(win_player):
            print("  ⚠ Não consegui voltar para a tela principal (botão 'Concluir').")
            print("  ⚠ Mas o vídeo já foi gerado e baixado com sucesso; mantendo este card como sucesso.")
            print(f"  ✅ Primeiro vídeo finalizado com sucesso no card #{indice_card}. Arquivo: {arquivo}")
            return True, win_flow

        print(f"  ✅ Primeiro vídeo finalizado com sucesso no card #{indice_card}. Arquivo: {arquivo}")
        return True, win_flow

    # ---------- VÍDEOS SEGUINTES ----------
    if win_flow_existente is None:
        print("  ❌ win_flow_existente não informado para vídeos seguintes.")
        return False, None

    win_flow = win_flow_existente
    try:
        win_flow.activate()
        time.sleep(0.7)
    except Exception:
        pass

    print("  ℹ Reutilizando mesma tela do Flow: apenas novo prompt e nova geração.")

    if not etapa10_tentar_gerar_video_com_retentativas(win_flow, prompt, max_tentativas=10, texto_ancora=None):
        print("  ❌ Falha na geração de vídeo reaproveitando a mesma tela do Flow.")
        fechar_janela_flow(win_flow)
        return False, None

    if not etapa11_aguardar_percentual_sumir(win_flow):
        print("  ❌ Percentual não sumiu nos cards após nova geração.")
        fechar_janela_flow(win_flow)
        return False, None

    win_player = etapa12_abrir_player_do_video(win_flow)
    ok_download, t_clique = etapa13_aguardar_baixar_720p(win_player)
    if not ok_download or t_clique is None:
        print("  ❌ Não consegui acionar download do novo vídeo.")
        fechar_janela_flow(win_player)
        return False, None

    arquivo = etapa14_esperar_download_video(t_clique, ext=".mp4", timeout=300)
    if not arquivo:
        print("  ❌ Download do novo vídeo não detectado.")
        fechar_janela_flow(win_player)
        return False, None

    if not etapa15_voltar_para_lista(win_player):
        print("  ⚠ Não consegui voltar para a tela principal (botão 'Concluir') após novo vídeo.")
        print("  ⚠ Mas o vídeo já foi gerado e baixado com sucesso; mantendo este vídeo como sucesso.")
        print(f"  ✅ Novo vídeo finalizado com sucesso. Arquivo: {arquivo}")
        return True, win_flow

    print(f"  ✅ Novo vídeo finalizado com sucesso. Arquivo: {arquivo}")
    return True, win_flow

# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    print("=" * 55)
    print("  AUTOMAÇÃO FERRAMENTAS GURU → FLOW (VEO 3.1)")
    print("=" * 55)

    if not EMAIL or not SENHA:
        raise ValueError("FG_EMAIL e FG_SENHA devem estar definidos no arquivo .env")

    etapa1_abrir_guru()
    print("\n[CONEXÃO] Anexando Selenium ao Guru (porta 9222)...")
    driver_fg = attach_to_chrome(DEBUG_PORT_FG, CHROMEDRIVER_PATH)

    etapa2_login(driver_fg)
    etapa3_fechar_popup(driver_fg)

    # AGORA SÓ 2 PROMPTS
    prompts = [
        "Um pôr do sol incrível na praia com ondas suaves",
        "Uma cidade futurista cheia de luzes de neon à noite",
    ]

    card_ok = None
    win_flow_atual = None

    for indice_card in range(1, 4):
        print(f"\n======================== TESTE CARD #{indice_card} ========================")
        sucesso, win_flow = rodar_fluxo_em_um_card(
            driver_fg,
            indice_card,
            prompts[0],
            primeiro_video=True,
            win_flow_existente=None,
        )
        if sucesso:
            card_ok = indice_card
            win_flow_atual = win_flow
            print(f"\n✅ Card #{indice_card} validado com sucesso para o Flow.")
            break
        else:
            print(f"\n⚠ Card #{indice_card} falhou. Tentando próximo card...")

    if card_ok is None or win_flow_atual is None:
        print("\n❌ Nenhum card do Flow funcionou (após testar 3). Encerrando.")
        return

    # SEGUNDO VÍDEO (APENAS 1 SEGUINTE)
    for i, prompt in enumerate(prompts[1:], start=2):
        print(f"\n======================== VÍDEO #{i} (CARD #{card_ok}) ========================")

        sucesso, win_flow_atual = rodar_fluxo_em_um_card(
            driver_fg,
            card_ok,
            prompt,
            primeiro_video=False,
            win_flow_existente=win_flow_atual,
        )

        if not sucesso:
            print(f"\n❌ Falha ao gerar o vídeo #{i}. Interrompendo sequência.")
            break

    # --- FINALIZAÇÃO: FECHAR FLOW E GURU ---
    print("\n[FINALIZAÇÃO] Fechando Flow e Ferramentas Guru...")

    try:
        finalizar_flow_alt_f4()
    except Exception as e:
        print(f"  ⚠ Erro na finalização do Flow via Alt+F4: {e}")

    try:
        finalizar_guru_alt_f4()
    except Exception as e:
        print(f"  ⚠ Erro na finalização do Guru via Alt+F4: {e}")

    try:
        driver_fg.quit()
    except Exception:
        pass

    print("\n✅ Fim da rotina de geração em sequência (com ou sem falhas).")

if __name__ == "__main__":
    main()