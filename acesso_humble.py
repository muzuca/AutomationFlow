# acesso_humble.py
import re
from pathlib import Path

import requests


DOC_ID = "1CxZmaI1Cxrgg3iyDkLxW68bA0jV63CNNrabNk4yNBLg"
EXPORT_URL = f"https://docs.google.com/document/d/{DOC_ID}/export?format=txt"
ENV_PATH = Path(".env")


def _extrair_credenciais_do_documento(texto: str) -> list[tuple[str, str]]:
    """
    Varre o documento inteiro procurando por blocos LOGIN: ... SENHA: ...
    e captura apenas o primeiro token válido após cada marcador.

    Regras:
    - LOGIN: pega apenas o primeiro token sem espaços (email)
    - SENHA: pega apenas o primeiro token sem espaços (senha)
    - ignora qualquer texto extra após o token principal
    - remove duplicados preservando ordem
    """
    credenciais: list[tuple[str, str]] = []
    login_atual: str | None = None

    for linha in texto.splitlines():
        linha_limpa = linha.strip()
        if not linha_limpa:
            continue

        match_login = re.match(r"^\s*LOGIN\s*:\s*(\S+)", linha_limpa, flags=re.IGNORECASE)
        if match_login:
            login_bruto = match_login.group(1).strip()

            # limpeza extra para casos de markdown/mailto ou pontuação acidental
            login_bruto = login_bruto.replace("[", "").replace("]", "")
            if "(mailto:" in login_bruto:
                login_bruto = login_bruto.split("(mailto:", 1)[0].strip()

            login_atual = login_bruto
            continue

        match_senha = re.match(r"^\s*SENHA\s*:\s*(\S+)", linha_limpa, flags=re.IGNORECASE)
        if match_senha and login_atual:
            senha = match_senha.group(1).strip()
            credenciais.append((login_atual, senha))
            login_atual = None

    # remove duplicados preservando ordem
    vistos = set()
    resultado = []
    for email, senha in credenciais:
        chave = (email, senha)
        if chave not in vistos:
            vistos.add(chave)
            resultado.append((email, senha))

    return resultado


def _remover_bloco_humble_env(conteudo: str) -> str:
    """
    Remove todas as linhas relacionadas ao bloco Humble do .env:
    - cabeçalho do bloco sincronizado
    - HUMBLE_EMAIL_N
    - HUMBLE_PASSWORD_N

    Preserva todo o restante do arquivo.
    """
    linhas_filtradas = []

    for linha in conteudo.splitlines():
        linha_strip = linha.strip()

        if linha_strip == "# --- CREDENCIAIS HUMBLE (SINCRONIZADO DO GOOGLE DOC) ---":
            continue

        if re.match(r"^\s*HUMBLE_EMAIL_\d+\s*=", linha):
            continue

        if re.match(r"^\s*HUMBLE_PASSWORD_\d+\s*=", linha):
            continue

        linhas_filtradas.append(linha)

    # remove excesso de linhas em branco repetidas
    conteudo_limpo = "\n".join(linhas_filtradas)
    conteudo_limpo = re.sub(r"\n{3,}", "\n\n", conteudo_limpo).strip()

    return conteudo_limpo


def sincronizar_credenciais_humble():
    try:
        print("Lendo dados do Google Doc...")
        response = requests.get(EXPORT_URL, timeout=30)
        response.raise_for_status()

        texto_doc = response.text
        credenciais = _extrair_credenciais_do_documento(texto_doc)

        if not credenciais:
            print("❌ Nenhum dado encontrado no formato LOGIN: / SENHA: no documento inteiro.")
            return

        print(f"ℹ {len(credenciais)} par(es) LOGIN/SENHA encontrados no documento.")

        conteudo_atual = ""
        if ENV_PATH.exists():
            conteudo_atual = ENV_PATH.read_text(encoding="utf-8")

        conteudo_sem_humble = _remover_bloco_humble_env(conteudo_atual)

        novo_bloco = ["# --- CREDENCIAIS HUMBLE (SINCRONIZADO DO GOOGLE DOC) ---"]
        for i, (email, senha) in enumerate(credenciais, start=1):
            novo_bloco.append(f"HUMBLE_EMAIL_{i}={email}")
            novo_bloco.append(f"HUMBLE_PASSWORD_{i}={senha}")
            print(f"Atualizando: HUMBLE_EMAIL_{i}")

        partes_finais = []
        if conteudo_sem_humble:
            partes_finais.append(conteudo_sem_humble)
        partes_finais.append("\n".join(novo_bloco))

        conteudo_final = "\n\n".join(partes_finais).strip() + "\n"
        ENV_PATH.write_text(conteudo_final, encoding="utf-8")

        print(f"\n✅ Concluído! .env sincronizado com o Google Doc.")
        print(f"✅ {len(credenciais)} par(es) de credenciais Humble gravados no arquivo.")

    except Exception as e:
        print(f"Erro: {e}")


if __name__ == "__main__":
    sincronizar_credenciais_humble()