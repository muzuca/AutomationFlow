#acesso_humble.py
import requests
import os

DOC_ID = "1kQPzcMvN6DAUJdIXQm6u2hydExyBJn2xBSHuPiht8gg"
EXPORT_URL = f"https://docs.google.com/document/d/{DOC_ID}/export?format=txt"

def sincronizar_credenciais_humble():
    try:
        print(f"Lendo dados do Google Doc...")
        response = requests.get(EXPORT_URL)
        response.raise_for_status()
        lines = response.text.splitlines()

        # 1. Extrai logins e senhas do documento
        novos_dados = []
        temp_email = None
        
        for line in lines:
            line = line.strip()
            if line.upper().startswith("LOGIN:"):
                temp_email = line.split(":", 1)[1].strip()
            elif line.upper().startswith("SENHA:") and temp_email:
                pwd = line.split(":", 1)[1].strip()
                novos_dados.append((temp_email, pwd))
                temp_email = None

        if not novos_dados:
            print("❌ Nenhum dado novo encontrado no formato LOGIN/SENHA.")
            return

        # 2. Verifica o que já existe no seu .env para evitar duplicados
        conteudo_atual = ""
        if os.path.exists(".env"):
            with open(".env", "r", encoding="utf-8") as f:
                conteudo_atual = f.read()

        # 3. Filtra apenas o que é realmente novo
        dados_para_adicionar = []
        for email, pwd in novos_dados:
            if email not in conteudo_atual:
                dados_para_adicionar.append((email, pwd))

        if not dados_para_adicionar:
            print("> Todos os logins do documento já estão no seu .env.")
            return

        # 4. Descobre qual é o último índice (N) para continuar a numeração
        # Procura pelo maior número em "HUMBLE_EMAIL_X"
        import re
        numeros = re.findall(r'HUMBLE_EMAIL_(\+d)', conteudo_atual)
        proximo_indice = max([int(n) for n in numeros]) + 1 if numeros else 1

        # 5. Anexa ao final do arquivo sem apagar nada
        with open(".env", "a", encoding="utf-8") as f:
            f.write("\n\n# --- NOVAS CREDENCIAIS ADICIONADAS AUTOMATICAMENTE ---\n")
            for email, pwd in dados_para_adicionar:
                f.write(f"HUMBLE_EMAIL_{proximo_indice}={email}\n")
                f.write(f"HUMBLE_PASSWORD_{proximo_indice}={pwd}\n")
                print(f"Adicionando: HUMBLE_EMAIL_{proximo_indice}")
                proximo_indice += 1
        
        print(f"\n✅ Concluído! {len(dados_para_adicionar)} novos pares adicionados ao final do seu .env.")

    except Exception as e:
        print(f"Erro: {e}")

if __name__ == "__main__":
    sincronizar_credenciais_humble()