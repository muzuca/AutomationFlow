import os
import time
import pyautogui
import pyperclip
import pytesseract

from .config import TESSERACT_PATH, OCR_DEBUG_DIR
from .window_utils import (
    focar_janela_flow,
    focar_janela_login_google,
    click_relativo_na_janela,
    digitar_na_janela,
    fechar_janela_flow,
)
from .ocr_utils import (
    ocr_click_in_window,
    detectar_texto_na_janela,
    detectar_aviso_bloqueio,
)

pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH


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
    center_y = win.top + win.height // 8
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
    print("\n[ETAPA 6] '+ Novo projeto' e 'Nano Banana 2' via OCR...")
    click_relativo_na_janela(win, 0.50, 0.80, "+ Novo projeto")
    time.sleep(5)
    print("  → Procurando texto 'Nano' na parte inferior (botão Nano Banana 2)...")
    ok = ocr_click_in_window(win, "Nano", region_rel=(0.3, 0.82, 1.0, 1.0))
    if ok:
        print("  ✔ Botão 'Nano Banana 2' clicado via OCR.")
        time.sleep(2)
        return True
    print("  ⚠ OCR não achou 'Nano'. Tentando clique aproximado...")
    x0, y0, w, h = win.left, win.top, win.width, win.height
    pyautogui.click(x0 + int(w * 0.65), y0 + int(h * 0.90))
    time.sleep(2)
    print("  ✔ Clique fallback para 'Nano Banana 2' realizado.")
    return True


def etapa7_flow_configurar_opcoes(win):
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
        print("  ✔ Opções críticas configuradas via OCR.")
    else:
        print("  ❌ Alguma opção crítica não foi configurada corretamente.")
    return sucesso


def etapa8_flow_preencher_prompt(win, prompt: str, texto_ancora: str | None = None):
    print("\n[ETAPA 8] Preenchendo prompt e enviando via OCR...")
    region_prompt = (0.03, 0.70, 0.97, 0.98)

    if texto_ancora:
        print(f"  → Procurando campo de prompt pelo texto_ancora: {texto_ancora!r}...")
        if not ocr_click_in_window(win, texto_ancora, region_rel=region_prompt):
            print("  ⚠ Não achei texto_ancora, caindo no fluxo placeholder/fallback.")
            texto_ancora = None

    if not texto_ancora:
        candidatos = ["criar", "Criar", "O que você quer criar", "quer criar"]
        print("  → Procurando campo de prompt pelo placeholder...")
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
    print("  ✔ Campo de prompt limpo após envio.")


def etapa9_aguardar_geracao_video(win, timeout_segundos: int = 180) -> str:
    print("\n[ETAPA 9] Aguardando a geração do vídeo terminar...")
    try:
        win = focar_janela_flow(timeout=5)
    except RuntimeError:
        print("  ⚠ Não consegui refocar a janela do Flow, tentarei assim mesmo.")

    inicio = time.time()
    region_video = (0.05, 0.10, 0.95, 0.90)
    ultimo_percent_val = None
    instante_ultima_percent = None
    ja_teve_percent = False
    TEMPO_MAX_SEM_PERCENT_INICIAL = 15
    TEMPO_SEM_NOVA_PERCENT_PARA_OK = 7
    LIMIAR_PERCENT_OK = 25
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
            debug_path = OCR_DEBUG_DIR / f"ocr_debug_percent_region_ciclo_{ciclo}.png"
            img.save(debug_path)
            print(f"  ℹ Screenshot da região de % salvo em {debug_path}")
        ciclo += 1

        data = pytesseract.image_to_data(img, lang="por+eng", output_type=pytesseract.Output.DICT)
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
            if not ja_teve_percent:
                if agora - inicio >= TEMPO_MAX_SEM_PERCENT_INICIAL:
                    print("  ❌ Nenhuma % apareceu em ~15s. Assumindo falha.")
                    return "erro"
            else:
                if (
                    ultimo_percent_val is not None
                    and ultimo_percent_val >= LIMIAR_PERCENT_OK
                    and instante_ultima_percent is not None
                ):
                    if agora - instante_ultima_percent >= TEMPO_SEM_NOVA_PERCENT_PARA_OK:
                        print(f"  ✔ Mais de {TEMPO_SEM_NOVA_PERCENT_PARA_OK}s sem nova % "
                              f"(>= {LIMIAR_PERCENT_OK}%). Assumindo vídeo pronto.")
                        return "ok"
        time.sleep(1)


def detectar_card_de_falha(win) -> bool:
    """
    Verifica APENAS o card mais recente (primeiro card da lista, canto superior esquerdo).
    Região restrita ao primeiro card para não confundir com falhas anteriores.
    """
    print("  → Verificando se o card MAIS RECENTE tem FALHA/ERRO/VIOLAÇÃO...")

    # Região restrita ao primeiro card (canto superior esquerdo da lista)
    # Ajustada para pegar apenas o card do topo, não os cards anteriores
    region_primeiro_card = (0.02, 0.15, 0.30, 0.45)

    x0, y0, w, h = win.left, win.top, win.width, win.height
    rx0, ry0, rx1, ry1 = region_primeiro_card
    X0 = x0 + int(w * rx0)
    Y0 = y0 + int(h * ry0)
    X1 = x0 + int(w * rx1)
    Y1 = y0 + int(h * ry1)

    img = pyautogui.screenshot(region=(X0, Y0, X1 - X0, Y1 - Y0))
    debug_path = OCR_DEBUG_DIR / "ocr_debug_card_falha.png"
    img.save(debug_path)
    print(f"    ✔ Screenshot do card mais recente salvo em {debug_path}")

    data = pytesseract.image_to_data(
        img, lang="por+eng", output_type=pytesseract.Output.DICT
    )
    palavras = [t.lower() for t in data["text"] if t.strip()]
    gatilhos = ["falha", "erro", "violação", "violation"]

    for p in palavras:
        if any(g in p for g in gatilhos):
            print(f"    ❌ Falha detectada no card mais recente: '{p}'")
            return True

    print("    ✔ Card mais recente sem falha/erro/violação.")
    return False


def aguardar_percentual_sumir_nos_cards(win, timeout_segundos: int = 300) -> bool:
    inicio = time.time()
    # Região do card mais recente (onde fica o % do vídeo atual)
    region_cards = (0.02, 0.15, 0.30, 0.50)
    CICLOS_PARA_OK = 5
    ciclos_sem_percent = 0

    while True:
        if time.time() - inicio > timeout_segundos:
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


def etapa11_aguardar_percentual_sumir(win) -> bool:
    print("\n[ETAPA 11] Aguardando percentual sumir nos cards...")
    return aguardar_percentual_sumir_nos_cards(win)


def etapa12_abrir_player_do_video(win_lista):
    print("\n[ETAPA 12] Abrindo player do vídeo a partir da lista...")
    click_relativo_na_janela(win_lista, 0.15, 0.30, "card principal do vídeo")
    time.sleep(3)
    try:
        return focar_janela_flow(timeout=5)
    except RuntimeError:
        print("  ⚠ Não achei nova janela do player; reutilizando mesma janela da lista.")
        return win_lista


def etapa13_aguardar_baixar_720p(win):
    print("\n[ETAPA 13] Aguardando botão 'Baixar' e selecionando 720p...")
    x0, y0, w, h = win.left, win.top, win.width, win.height
    x_hover = x0 + int(w * 0.85)
    y_hover = y0 + int(h * 0.08)

    for tentativa in range(1, 9):
        print(f"  → Tentativa #{tentativa} de achar 'Baixar'...")
        pyautogui.moveTo(x_hover, y_hover, duration=0.3)
        time.sleep(1.0)
        if ocr_click_in_window(win, "Baixar", region_rel=(0.6, 0.0, 1.0, 0.25)):
            print("  ✔ Botão 'Baixar' visível. Aguardando 2s...")
            time.sleep(2.0)
            break
        print("  ⚠ 'Baixar' ainda não apareceu. Aguardando 2s...")
        time.sleep(2.0)
    else:
        print("  ❌ Não consegui localizar/clicar no botão 'Baixar'.")
        return False, None

    for tentativa in range(1, 6):
        print(f"  → Tentativa #{tentativa} de achar '720p'...")
        if ocr_click_in_window(win, "720p", region_rel=(0.55, 0.15, 0.95, 0.70)):
            t_inicio = time.time()
            print("  ✔ Resolução 720p selecionada. Download iniciado.")
            return True, t_inicio
        print("  ⚠ '720p' ainda não apareceu. Aguardando 2s...")
        time.sleep(2.0)

    print("  ❌ Não consegui localizar/clicar em '720p'.")
    return False, None


def etapa14_esperar_download_video(t_inicio_download: float, ext: str = ".mp4", timeout: int = 300):
    print("\n[ETAPA 14] Aguardando arquivo de vídeo na pasta de downloads...")
    pasta_downloads = os.path.join(os.path.expanduser("~"), "Downloads")
    limite = t_inicio_download - 10
    print(f"  ℹ t_inicio_download (epoch): {t_inicio_download}")
    print(f"  ℹ t_limite: {limite}")
    print(f"  ℹ Monitorando pasta: {pasta_downloads}")

    fim = time.time() + timeout
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
            mais_novo = max(arquivos, key=os.path.getmtime)
            if os.path.getmtime(mais_novo) >= limite:
                print(f"  ✔ Candidato encontrado: {os.path.basename(mais_novo)}")
                return mais_novo
        time.sleep(3)

    print("  ❌ Nenhum arquivo de vídeo recente encontrado no timeout.")
    return None


def etapa15_voltar_para_lista(win_player) -> bool:
    print("\n[ETAPA 15] Voltando para a lista (botão 'Concluir')...")
    for tentativa in range(1, 4):
        print(f"  → Tentativa #{tentativa} de encontrar 'Concluir'...")
        try:
            click_relativo_na_janela(win_player, 0.10, 0.10, "área neutra")
            time.sleep(0.8)
        except Exception as e:
            print(f"  ⚠ Erro ao clicar em área neutra: {e}")

        region_concluir = (0.72, 0.0, 1.0, 0.20)
        if ocr_click_in_window(win_player, "Concluir", region_rel=region_concluir):
            print("  ✔ Clicado em 'Concluir'. Voltando para a lista.")
            time.sleep(3)
            return True
        if ocr_click_in_window(win_player, "cluir", region_rel=region_concluir):
            print("  ✔ Clicado em 'Concluir' (via 'cluir'). Voltando para a lista.")
            time.sleep(3)
            return True
        print("  ⚠ 'Concluir' não encontrado. Aguardando e tentando de novo...")
        time.sleep(3)

    print("  ❌ Não consegui clicar em 'Concluir'.")
    return False