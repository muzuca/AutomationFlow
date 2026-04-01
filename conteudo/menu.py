# conteudo/menu.py
# Menu interativo de configuração da sessão de geração.

from .temas import temas_disponiveis, TEMAS_POR_PERSONAGEM

PERSONAGENS_DISPONIVEIS = list(TEMAS_POR_PERSONAGEM.keys())
NOMES_EXIBICAO = {
    "AnaCartomante": "Ana Cartomante",
}


def linha(char="=", largura=52):
    print(char * largura)


def cabecalho(titulo: str):
    linha()
    print(f"  {titulo}")
    linha()


def perguntar_int(mensagem: str, minimo: int, maximo: int, padrao: int) -> int:
    while True:
        try:
            entrada = input(f"{mensagem} [{padrao}]: ").strip()
            if not entrada:
                return padrao
            valor = int(entrada)
            if minimo <= valor <= maximo:
                return valor
            print(f"  Digite um número entre {minimo} e {maximo}.")
        except ValueError:
            print("  Entrada inválida. Digite um número.")


def perguntar_sim_nao(mensagem: str, padrao: bool = True) -> bool:
    opcoes = "S/n" if padrao else "s/N"
    while True:
        entrada = input(f"{mensagem} [{opcoes}]: ").strip().lower()
        if not entrada:
            return padrao
        if entrada in ("s", "sim", "y", "yes"):
            return True
        if entrada in ("n", "nao", "não", "no"):
            return False
        print("  Digite S para sim ou N para não.")


def selecionar_personagens() -> list[str]:
    cabecalho("PERSONAGENS")
    print("  Personagens disponíveis:")
    for i, p in enumerate(PERSONAGENS_DISPONIVEIS, 1):
        nome = NOMES_EXIBICAO.get(p, p)
        print(f"  {i}. {nome}")
    print("  Digite os números separados por vírgula (ex: 1,2)")
    print("  Pressione Enter para selecionar todos.")
    while True:
        entrada = input("  Personagens: ").strip()
        if not entrada:
            print("  Todos os personagens selecionados.")
            return PERSONAGENS_DISPONIVEIS.copy()
        try:
            indices = [int(x.strip()) for x in entrada.split(",")]
            selecionados = []
            for idx in indices:
                if 1 <= idx <= len(PERSONAGENS_DISPONIVEIS):
                    selecionados.append(PERSONAGENS_DISPONIVEIS[idx - 1])
                else:
                    print(f"  Número {idx} inválido. Tente novamente.")
                    selecionados = []
                    break
            if selecionados:
                nomes = [NOMES_EXIBICAO.get(p, p) for p in selecionados]
                print(f"  Selecionados: {', '.join(nomes)}")
                return selecionados
        except ValueError:
            print("  Formato inválido. Use números separados por vírgula.")


def selecionar_tema(personagem: str) -> str:
    nome_exib = NOMES_EXIBICAO.get(personagem, personagem)
    cabecalho(f"TEMA — {nome_exib}")
    temas = temas_disponiveis(personagem)
    print("  Temas disponíveis:")
    for i, tema in enumerate(temas, 1):
        sufixo = " (sorteia a cada vídeo)" if tema == "aleatorio" else ""
        print(f"  {i}. {tema.capitalize()}{sufixo}")
    while True:
        try:
            entrada = input(f"  Tema [1-{len(temas)}]: ").strip()
            idx = int(entrada) - 1
            if 0 <= idx < len(temas):
                tema = temas[idx]
                print(f"  Tema selecionado: {tema.capitalize()}")
                return tema
            print(f"  Digite um número entre 1 e {len(temas)}.")
        except ValueError:
            print("  Entrada inválida.")


def selecionar_signo(personagem: str) -> str:
    SIGNOS = [
        "Áries", "Touro", "Gêmeos", "Câncer", "Leão", "Virgem",
        "Libra", "Escorpião", "Sagitário", "Capricórnio", "Aquário", "Peixes",
        "aleatorio",
    ]
    NOMES_EXIBICAO_SIGNO = {
        "aleatorio": "Aleatório (sorteia um signo a cada vídeo)",
    }
    nome_exib = NOMES_EXIBICAO.get(personagem, personagem)
    cabecalho(f"SIGNO — {nome_exib}")
    print("  Signos disponíveis:")
    for i, s in enumerate(SIGNOS, 1):
        label = NOMES_EXIBICAO_SIGNO.get(s, s)
        print(f"  {i:2}. {label}")
    while True:
        try:
            entrada = input(f"  Signo [1-{len(SIGNOS)}]: ").strip()
            idx = int(entrada) - 1
            if 0 <= idx < len(SIGNOS):
                signo = SIGNOS[idx]
                label = NOMES_EXIBICAO_SIGNO.get(signo, signo)
                print(f"  Signo selecionado: {label}")
                return signo
            print(f"  Digite um número entre 1 e {len(SIGNOS)}.")
        except ValueError:
            print("  Entrada inválida.")


def selecionar_motor() -> str:
    """Pergunta qual motor de geração usar: Guru ou Humble."""
    cabecalho("MOTOR DE GERAÇÃO")
    print("  1. Guru  (Ferramentas Guru + OCR — padrão)")
    print("  2. Humble (Flow Web direto via Selenium)")
    while True:
        entrada = input("  Motor [1/2] [1]: ").strip()
        if not entrada or entrada == "1":
            print("  Motor selecionado: Guru")
            return "guru"
        if entrada == "2":
            print("  Motor selecionado: Humble")
            return "humble"
        print("  Digite 1 ou 2.")


def exibir_menu() -> dict:
    cabecalho("AUTOMAÇÃO DE VÍDEOS — CONFIGURAÇÃO DA SESSÃO")

    # ── 1. Motor de geração ───────────────────────────────────  ← PRIMEIRO
    linha("-", 52)
    motor = selecionar_motor()

    # ── 2. Modo de execução ───────────────────────────────────
    linha("-", 52)
    print("  MODO DE EXECUÇÃO")
    print("  1. Contínuo — gera em loop até ser encerrado (padrão)")
    print("  2. Único    — gera um ciclo e encerra")
    while True:
        entrada = input("  Modo [1/2] [1]: ").strip()
        if not entrada or entrada == "1":
            modo = "continuo"
            print("  Modo Contínuo")
            break
        if entrada == "2":
            modo = "unico"
            print("  Modo Único")
            break
        print("  Digite 1 ou 2.")

    # ── 3. Quantidade de vídeos ───────────────────────────────
    linha("-", 52)
    print("  QUANTIDADE DE VÍDEOS")
    videos_por_personagem = perguntar_int(
        "  Vídeos por personagem por ciclo (ao longo de 24h)",
        minimo=1, maximo=24, padrao=6,
    )
    print(f"  {videos_por_personagem} vídeos por personagem.")

    # ── 4. Personagens ────────────────────────────────────────
    linha("-", 52)
    personagens_ids = selecionar_personagens()

    personagens_config = []
    for pid in personagens_ids:
        tema = selecionar_tema(pid)
        if tema in ("signos", "aleatorio"):
            signo = selecionar_signo(pid)
        else:
            signo = None
        cenas_por_video = perguntar_int(
            f"  Quantas cenas por vídeo para {NOMES_EXIBICAO.get(pid, pid)}",
            minimo=1, maximo=10, padrao=5,
        )
        personagens_config.append({
            "id":              pid,
            "nome":            NOMES_EXIBICAO.get(pid, pid),
            "signo":           signo,
            "tema":            tema,
            "cenas_por_video": cenas_por_video,
        })

    # ── Resumo ────────────────────────────────────────────────
    cabecalho("RESUMO DA SESSÃO")
    print(f"  Motor:        {'Guru' if motor == 'guru' else 'Humble'}")
    print(f"  Modo:         {modo.capitalize()}")
    print(f"  Vídeos/ciclo: {videos_por_personagem} por personagem")
    print(f"  Personagens:  {len(personagens_config)}")
    for p in personagens_config:
        signo_str = p["signo"] if p["signo"] else "—"
        print(f"    {p['nome']} | {signo_str} | {p['tema'].capitalize()} | {p['cenas_por_video']} cenas/vídeo")
    total = len(personagens_config) * videos_por_personagem
    print(f"  Total por ciclo: {total} vídeos")
    print()

    if not perguntar_sim_nao("  Confirmar e iniciar?", padrao=True):
        print("  Configuração cancelada. Reiniciando menu...")
        return exibir_menu()

    return {
        "modo":                  modo,
        "motor":                 motor,
        "videos_por_personagem": videos_por_personagem,
        "personagens":           personagens_config,
    }