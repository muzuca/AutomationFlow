import time
import pyautogui
import pytesseract
from PIL import Image  # noqa: F401

from .config import OCR_DEBUG_DIR, TESSERACT_PATH

pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH


def ocr_click_in_window(win, texto_alvo: str, region_rel=None, lang: str = "por+eng") -> bool:
    x0, y0, w, h = win.left, win.top, win.width, win.height
    if region_rel:
        rx0, ry0, rx1, ry1 = region_rel
        x1 = x0 + int(w * rx1)
        y1 = y0 + int(h * ry1)
        x0 = x0 + int(w * rx0)
        y0 = y0 + int(h * ry0)
    else:
        x1, y1 = x0 + w, y0 + h

    print(f"  → Screenshot para OCR na região ({x0},{y0})–({x1},{y1})...")
    img = pyautogui.screenshot(region=(x0, y0, x1 - x0, y1 - y0))
    debug_path = OCR_DEBUG_DIR / f"ocr_debug_{texto_alvo.replace(' ', '_')}.png"
    img.save(debug_path)
    print(f"    ✔ Imagem salva em {debug_path}")

    data = pytesseract.image_to_data(img, lang=lang, output_type=pytesseract.Output.DICT)
    alvo_lower = texto_alvo.lower()
    for i, palavra in enumerate(data["text"]):
        if not palavra.strip():
            continue
        if alvo_lower in palavra.lower():
            cx = x0 + data["left"][i] + data["width"][i] // 2
            cy = y0 + data["top"][i] + data["height"][i] // 2
            print(f"    ✔ Encontrado '{palavra}' em ({cx},{cy}), clicando...")
            pyautogui.click(cx, cy)
            time.sleep(0.4)
            return True

    print(f"    ✗ Texto '{texto_alvo}' não encontrado via OCR.")
    return False


def detectar_texto_na_janela(win, texto_alvo: str, region_rel=None, lang: str = "por+eng") -> bool:
    x0, y0, w, h = win.left, win.top, win.width, win.height
    if region_rel:
        rx0, ry0, rx1, ry1 = region_rel
        x1 = x0 + int(w * rx1)
        y1 = y0 + int(h * ry1)
        x0 = x0 + int(w * rx0)
        y0 = y0 + int(h * ry0)
    else:
        x1, y1 = x0 + w, y0 + h

    print(f"  → OCR (leitura) na região ({x0},{y0})–({x1},{y1}) para '{texto_alvo}'...")
    img = pyautogui.screenshot(region=(x0, y0, x1 - x0, y1 - y0))
    debug_path = OCR_DEBUG_DIR / f"ocr_debug_check_{texto_alvo.replace(' ', '_')}.png"
    img.save(debug_path)
    print(f"    ✔ Imagem salva em {debug_path}")

    data = pytesseract.image_to_data(img, lang=lang, output_type=pytesseract.Output.DICT)
    for palavra in data["text"]:
        if palavra.strip() and texto_alvo.lower() in palavra.lower():
            print(f"    ✔ Texto '{texto_alvo}' encontrado (via '{palavra}').")
            return True

    print(f"    ✗ Texto '{texto_alvo}' NÃO encontrado via OCR.")
    return False


def detectar_aviso_bloqueio(win) -> bool:
    print("  → Verificando aviso de conta bloqueada (OCR 'Entendi')...")
    if detectar_texto_na_janela(win, "Entendi", region_rel=(0.10, 0.10, 0.90, 0.90)):
        print("  ❌ Aviso detectado.")
        return True
    print("  ✔ Nenhum aviso detectado.")
    return False