import time
import subprocess
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    ElementClickInterceptedException,
    TimeoutException,
    NoSuchElementException,
)

from automation_flow.core.config.settings import EXE_PATH, DEBUG_PORT_FG, CHROMEDRIVER_PATH, WAIT
from automation_flow.core.utils.window_utils import fechar_todas_janelas_flow_ou_login

def attach_to_chrome(port: int, chromedriver_path: str | None = None):
    opts = Options()
    opts.add_experimental_option("debuggerAddress", f"127.0.0.1:{port}")
    opts.add_argument("--no-sandbox")
    svc = Service(chromedriver_path) if chromedriver_path else Service()
    driver = webdriver.Chrome(service=svc, options=opts)
    print(f"  ✔ Conectado ao Chrome na porta {port} — título: {driver.title}")
    return driver


def wait_and_click(driver, by, value, timeout=WAIT, description="elemento"):
    print(f"  → Aguardando: {description}")
    el = WebDriverWait(driver, timeout).until(EC.element_to_be_clickable((by, value)))
    el.click()
    print(f"  ✔ Clicado: {description}")
    return el


def fechar_popup_guru(driver) -> bool:
    """
    Detecta e fecha APENAS modais reais do Guru (com overlay ativo).
    NÃO clica em botões fora de modal.
    """
    # Primeiro verifica se existe um modal/overlay visível
    try:
        overlay = driver.find_element(By.CSS_SELECTOR, "div.modal-overlay")
        if not overlay.is_displayed():
            return False
    except NoSuchElementException:
        # Tenta seletor alternativo
        try:
            overlay = driver.find_element(
                By.XPATH,
                "//div[contains(@class,'modal') and contains(@style,'z-index: 99999')]"
            )
            if not overlay.is_displayed():
                return False
        except NoSuchElementException:
            return False  # Nenhum overlay ativo — não faz nada

    print("  ℹ Modal overlay detectado. Procurando botão 'Fechar'...")

    # Só procura botão de fechar DENTRO do modal, nunca fora
    seletores_fechar = [
        (By.XPATH, "//div[contains(@class,'modal')]//button[contains(text(),'Fechar')]"),
        (By.XPATH, "//div[contains(@class,'modal')]//button[contains(text(),'fechar')]"),
        (By.XPATH, "//div[contains(@class,'modal')]//button[contains(@class,'btn-secondary')]"),
        (By.XPATH, "//div[contains(@class,'modal-content')]//button[1]"),
    ]

    for by, valor in seletores_fechar:
        try:
            el = WebDriverWait(driver, 2).until(EC.element_to_be_clickable((by, valor)))
            texto = el.text.strip()
            # Garante que não é um botão de ação principal (ex: 🚨, Atualizar Agora)
            if any(x in texto for x in ["Atualizar", "Confirmar", "Salvar"]):
                continue
            print(f"  ℹ Fechando modal via botão: '{texto}'...")
            try:
                el.click()
            except ElementClickInterceptedException:
                driver.execute_script("arguments[0].click();", el)
            time.sleep(1.5)
            print("  ✔ Modal fechado.")
            return True
        except (TimeoutException, NoSuchElementException):
            continue

    # Fallback: remove o overlay via JS se não achou botão adequado
    try:
        driver.execute_script("arguments[0].remove();", overlay)
        time.sleep(0.8)
        print("  ✔ Overlay removido via JS (fallback).")
        return True
    except Exception as e:
        print(f"  ⚠ Não consegui remover overlay: {e}")
        return False


def verificar_e_fechar_popup_guru(driver):
    """
    Chama fechar_popup_guru APENAS se overlay estiver ativo.
    """
    print("  → Verificando popup do Guru antes de continuar...")
    if fechar_popup_guru(driver):
        print("  ✔ Popup tratado.")
    else:
        print("  ℹ Nenhum popup ativo.")

        
def _clicar_botao_com_retry(driver, by, value, description="elemento", max_tentativas=3):
    """
    Tenta clicar em um elemento, fechando popups se houver interceptação.
    """
    for tentativa in range(1, max_tentativas + 1):
        try:
            verificar_e_fechar_popup_guru(driver)
            el = WebDriverWait(driver, WAIT).until(EC.element_to_be_clickable((by, value)))
            el.click()
            print(f"  ✔ Clicado em: {description} (tentativa {tentativa})")
            return True
        except ElementClickInterceptedException:
            print(f"  ⚠ Clique interceptado em '{description}' (tentativa {tentativa}/{max_tentativas}). "
                  f"Fechando popup e tentando novamente...")
            fechar_popup_guru(driver)
            time.sleep(2)
        except Exception as e:
            print(f"  ❌ Erro ao clicar em '{description}': {e}")
            return False
    print(f"  ❌ Não consegui clicar em '{description}' após {max_tentativas} tentativas.")
    return False


def etapa1_abrir_guru():
    print("\n[ETAPA 1] Abrindo Ferramentas Guru com porta de debug...")
    subprocess.Popen([
        EXE_PATH,
        f"--remote-debugging-port={DEBUG_PORT_FG}",
        "--remote-allow-origins=*",
    ])
    time.sleep(8)
    print("  ✔ Guru iniciado.")


def etapa2_login(driver, email: str, senha: str):
    print("\n[ETAPA 2] Login no Guru...")
    email_field = WebDriverWait(driver, WAIT).until(
        EC.presence_of_element_located((By.CSS_SELECTOR,
            "input[type='email'], input[placeholder*='email'], input[name='email']"))
    )
    email_field.clear()
    email_field.send_keys(email)
    senha_field = driver.find_element(By.CSS_SELECTOR,
        "input[type='password'], input[name='password'], input[name='senha']")
    senha_field.clear()
    senha_field.send_keys(senha)
    wait_and_click(
        driver,
        By.XPATH,
        "//button[contains(translate(text(),'entrar','ENTRAR'),'ENTRAR') or contains(text(),'Login')]",
        description="botão ENTRAR / Login",
    )
    time.sleep(4)
    print("  ✔ Login enviado.")


def etapa3_fechar_popup(driver):
    print("\n[ETAPA 3] Verificando popup de atualização...")
    try:
        btn = WebDriverWait(driver, 8).until(
            EC.element_to_be_clickable((By.XPATH,
                "//button[contains(text(),'Atualizar Agora') or contains(text(),'Atualizar agora')]"))
        )
        btn.click()
        print("  ✔ Popup fechado.")
        time.sleep(2)
    except Exception:
        print("  ℹ Nenhum popup detectado.")


def etapa4_buscar_flow_e_abrir(driver):
    print("\n[ETAPA 4] Buscando 'google flow veo 3' e clicando em Abrir...")
    fechar_todas_janelas_flow_ou_login()

    # Fecha popup antes de qualquer interação
    verificar_e_fechar_popup_guru(driver)

    search_box = WebDriverWait(driver, WAIT).until(
        EC.presence_of_element_located((By.CSS_SELECTOR,
            "input[type='search'], input[placeholder*='Buscar'], "
            "input[placeholder*='buscar'], input[placeholder*='Pesquisar']"))
    )
    search_box.clear()
    search_box.send_keys("google flow veo 3")
    search_box.send_keys(Keys.ENTER)
    time.sleep(4)

    sucesso = _clicar_botao_com_retry(
        driver,
        By.CSS_SELECTOR,
        "button.btn.btn-primary",
        description="primeiro botão ▶ Abrir",
    )
    if not sucesso:
        raise RuntimeError("Não consegui clicar em 'Abrir' na etapa 4.")

    print("  ✔ Clicado em Abrir; aguardando janela do Flow abrir...")
    time.sleep(10)


def abrir_card_pelo_indice(driver, indice_card: int) -> bool:
    """
    Clica no botão 'Abrir' correspondente ao índice do card (1-based).
    Fecha popup se necessário antes e durante o clique.
    """
    print("  → Buscando todos os botões 'Abrir' na lista de cards...")

    # Fecha popup antes de buscar os botões
    verificar_e_fechar_popup_guru(driver)

    try:
        botoes = WebDriverWait(driver, WAIT).until(
            EC.presence_of_all_elements_located(
                (By.XPATH, "//button[contains(., 'Abrir')]")
            )
        )
        print(f"  ℹ Encontrados {len(botoes)} botões 'Abrir'.")
        idx = indice_card - 1
        if idx < 0 or idx >= len(botoes):
            print(f"  ❌ Não existe botão 'Abrir' para o card #{indice_card}.")
            return False

        # Tenta clicar com retry e tratamento de popup
        for tentativa in range(1, 4):
            verificar_e_fechar_popup_guru(driver)
            try:
                # Re-busca os botões a cada tentativa (DOM pode ter mudado)
                botoes = driver.find_elements(By.XPATH, "//button[contains(., 'Abrir')]")
                if idx >= len(botoes):
                    print(f"  ❌ Botão #{indice_card} desapareceu do DOM.")
                    return False
                botoes[idx].click()
                print(f"  ✔ Clicado em Abrir (card #{indice_card}); aguardando janela abrir...")
                time.sleep(10)
                return True
            except ElementClickInterceptedException:
                print(f"  ⚠ Clique interceptado (tentativa {tentativa}/3). "
                      f"Fechando popup...")
                fechar_popup_guru(driver)
                time.sleep(2)
            except Exception as e:
                print(f"  ❌ Erro ao clicar no card #{indice_card}: {e}")
                return False

        print(f"  ❌ Não consegui clicar no card #{indice_card} após 3 tentativas.")
        return False

    except Exception as e:
        print(f"  ❌ Erro ao buscar botões 'Abrir': {e}")
        return False