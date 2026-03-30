import time
import pyautogui
import pygetwindow as gw

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.2


def focar_janela_por_titulo(parte_titulo: str, timeout: int = 25):
    print(f"  → Procurando janela contendo: {parte_titulo!r}")
    for _ in range(timeout):
        wins = gw.getWindowsWithTitle(parte_titulo)
        wins = [w for w in wins if "Visual Studio Code" not in w.title]
        if wins:
            win = wins[0]
            try:
                win.activate()
            except Exception:
                pass
            time.sleep(0.7)
            print(f"  ✔ Janela focada: {win.title}")
            return win
        time.sleep(1)
    raise RuntimeError(f"Janela contendo '{parte_titulo}' não encontrada em {timeout}s.")


def focar_janela_flow(timeout: int = 25):
    return focar_janela_por_titulo("labs.google/fx", timeout=timeout)


def focar_janela_login_google(timeout: int = 25):
    try:
        return focar_janela_por_titulo("Fazer login nas Contas do Google", timeout=timeout)
    except RuntimeError:
        print(f"  ✗ Janela de login do Google não encontrada em {timeout}s.")
        return None


def click_relativo_na_janela(win, x_pct: float, y_pct: float, descricao: str = ""):
    x = win.left + int(win.width * x_pct)
    y = win.top + int(win.height * y_pct)
    print(f"  → Clicando em {descricao} na janela ({x},{y}) [{x_pct*100:.1f}%, {y_pct*100:.1f}%]")
    pyautogui.click(x, y)
    time.sleep(0.3)


def digitar_na_janela(texto: str):
    pyautogui.write(texto, interval=0.03)


def fechar_todas_janelas_flow_ou_login():
    padroes = ["labs.google/fx", "Fazer login nas Contas do Google"]
    for alvo in padroes:
        for w in gw.getWindowsWithTitle(alvo):
            try:
                print(f"  → Fechando janela residual: {w.title}")
                w.close()
                time.sleep(0.5)
            except Exception as e:
                print(f"  ⚠ Erro ao fechar '{w.title}': {e}")


def fechar_janela_flow(win):
    try:
        print(f"  → Fechando janela (title='{win.title}')...")
        win.close()
        print(f"  ✔ Janela fechada: {win.title}")
    except Exception as e:
        print(f"  ⚠ Não consegui fechar a janela: {e}")


def finalizar_flow_alt_f4():
    print("\n[FINALIZAÇÃO] Fechando janelas do Flow com Alt+F4...")
    for _ in range(3):
        wins = [w for w in gw.getWindowsWithTitle("labs.google/fx")
                if "Visual Studio Code" not in w.title]
        if not wins:
            break
        try:
            wins[0].activate()
            time.sleep(0.5)
        except Exception:
            pass
        pyautogui.hotkey("alt", "f4")
        time.sleep(1.5)
    print("  ✔ Flow fechado.")


def finalizar_guru_alt_f4():
    print("[FINALIZAÇÃO] Fechando Ferramentas Guru com Alt+F4...")
    wins = gw.getWindowsWithTitle("Ferramentas Guru")
    if not wins:
        print("  ℹ Nenhuma janela do Guru encontrada.")
        return
    try:
        wins[0].activate()
        time.sleep(0.5)
    except Exception:
        pass
    pyautogui.hotkey("alt", "f4")
    time.sleep(1.5)
    print("  ✔ Guru fechado.")