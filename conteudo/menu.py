"""
Menu interativo de configuração da sessão de geração.
"""

from .temas import temas_disponiveis, TEMAS_POR_PERSONAGEM

# Personagens disponíveis (expandir conforme novos personagens forem criados)
PERSONAGENS_DISPONIVEIS = list(TEMAS_POR_PERSONAGEM.keys())

NOMES_EXIBICAO = {
    "AnaCartomante": "Ana Cartomante 🔮",
}


def _linha(char="─", largura=52):
    print(char * largura)


def _cabecalho(titulo: str):
    _linha("═")
    print(f"  {titulo}")
    _linha("═")


def _perguntar_int(mensagem: str, minimo: int, maximo: int, padrao: int) -> int:
    while True:
        try:
            entrada = input(f"{mensagem} [{padrao}]: ").strip()
            if not entrada:
                return padrao
            valor = int(entrada)
            if minimo <= valor <= maximo:
                return valor
            print(f"  ⚠ Digite um número entre {minimo} e {maximo}.")
        except ValueError:
            print("  ⚠ Entrada inválida. Digite um número.")


def _perguntar_sim_nao(mensagem: str, padrao: bool = True) -> bool:
    opcoes = "S/n" if padrao else "s/N"
    while True:
        entrada = input(f"{mensagem} [{opcoes}]: ").strip().lower()
        if not entrada:
            return padrao
        if entrada in ("s", "sim", "y", "yes"):
            return True
        if entrada in ("n", "nao", "não", "no"):
            return False
        print("  ⚠ Digite S para sim ou N para não.")


def _selecionar_personagens() -> list[str]:
    """Multi-seleção de personagens via números separados por vírgula."""
    _cabecalho("PERSONAGENS")
    print("  Personagens disponíveis:\n")
    for i, p in enumerate(PERSONAGENS_DISPONIVEIS, 1):
        nome = NOMES_EXIBICAO.get(p, p)
        print(f"    {i}. {nome}")

    print("\n  Digite os números separados por vírgula (ex: 1,2)")
    print("  Pressione Enter para selecionar todos.")

    while True:
        entrada = input("\n  Personagens: ").strip()

        if not entrada:
            print("  ✔ Todos os personagens selecionados.")
            return PERSONAGENS_DISPONIVEIS.copy()

        try:
            indices = [int(x.strip()) for x in entrada.split(",")]
            selecionados = []
            for idx in indices:
                if 1 <= idx <= len(PERSONAGENS_DISPONIVEIS):
                    selecionados.append(PERSONAGENS_DISPONIVEIS[idx - 1])
                else:
                    print(f"  ⚠ Número {idx} inválido. Tente novamente.")
                    selecionados = []
                    break
            if selecionados:
                nomes = [NOMES_EXIBICAO.get(p, p) for p in selecionados]
                print(f"  ✔ Selecionados: {', '.join(nomes)}")
                return selecionados
        except ValueError:
            print("  ⚠ Formato inválido. Use números separados por vírgula.")


def _selecionar_tema(personagem: str) -> str:
    """Seleção de tema para um personagem."""
    nome_exib = NOMES_EXIBICAO.get(personagem, personagem)
    _cabecalho(f"TEMA — {nome_exib}")

    temas = temas_disponiveis(personagem)
    print("  Temas disponíveis:\n")
    for i, tema in enumerate(temas, 1):
        sufixo = "  ← sorteia a cada vídeo" if tema == "aleatorio" else ""
        print(f"    {i}. {tema.capitalize()}{sufixo}")

    while True:
        try:
            entrada = input(f"\n  Tema (1-{len(temas)}): ").strip()
            idx = int(entrada) - 1
            if 0 <= idx < len(temas):
                tema = temas[idx]
                print(f"  ✔ Tema selecionado: {tema.capitalize()}")
                return tema
            print(f"  ⚠ Digite um número entre 1 e {len(temas)}.")
        except ValueError:
            print("  ⚠ Entrada inválida.")


def _selecionar_signo(personagem: str) -> str:
    SIGNOS = [
        "Áries", "Touro", "Gêmeos", "Câncer", "Leão", "Virgem",
        "Libra", "Escorpião", "Sagitário", "Capricórnio", "Aquário", "Peixes",
        "aleatorio",   # sorteia a cada vídeo
    ]

    NOMES_EXIBICAO_SIGNO = {
        "aleatorio": "Aleatório  ← sorteia um signo a cada vídeo",
    }

    nome_exib = NOMES_EXIBICAO.get(personagem, personagem)
    _cabecalho(f"SIGNO — {nome_exib}")
    print("  Signos disponíveis:\n")
    for i, s in enumerate(SIGNOS, 1):
        label = NOMES_EXIBICAO_SIGNO.get(s, s)
        print(f"    {i:2}. {label}")

    while True:
        try:
            entrada = input(f"\n  Signo (1-{len(SIGNOS)}): ").strip()
            idx = int(entrada) - 1
            if 0 <= idx < len(SIGNOS):
                signo = SIGNOS[idx]
                label = NOMES_EXIBICAO_SIGNO.get(signo, signo)
                print(f"  ✔ Signo selecionado: {label}")
                return signo
            print(f"  ⚠ Digite um número entre 1 e {len(SIGNOS)}.")
        except ValueError:
            print("  ⚠ Entrada inválida.")


def exibir_menu() -> dict:
    """
    Exibe o menu completo e retorna a configuração da sessão.

    Returns:
        {
            "modo":                  "continuo" | "unico"
            "videos_por_personagem": int
            "personagens": [
                {
                    "id":              str,
                    "nome":            str,
                    "signo":           str | None,
                    "tema":            str,
                    "cenas_por_video": int,
                }
            ]
        }
    """
    print("\n")
    _cabecalho("AUTOMAÇÃO DE VÍDEOS — CONFIGURAÇÃO DA SESSÃO")
    print()

    # ── Modo de execução ─────────────────────────────────────
    _linha()
    print("  MODO DE EXECUÇÃO\n")
    print("    1. Contínuo — gera em loop até ser encerrado  (padrão)")
    print("    2. Único    — gera um ciclo e encerra")

    while True:
        entrada = input("\n  Modo (1/2) [1]: ").strip()
        if not entrada or entrada == "1":
            modo = "continuo"
            print("  ✔ Modo: Contínuo")
            break
        if entrada == "2":
            modo = "unico"
            print("  ✔ Modo: Único")
            break
        print("  ⚠ Digite 1 ou 2.")

    # ── Quantidade de vídeos ─────────────────────────────────
    _linha()
    print("  QUANTIDADE DE VÍDEOS\n")
    videos_por_personagem = _perguntar_int(
        "  Vídeos por personagem por ciclo (ao longo de 24h)",
        minimo=1,
        maximo=24,
        padrao=6,
    )
    print(f"  ✔ {videos_por_personagem} vídeos por personagem.")

    # ── Personagens ──────────────────────────────────────────
    _linha()
    personagens_ids = _selecionar_personagens()

    # ── Tema, signo (condicional) e cenas por personagem ─────
    personagens_config = []
    for pid in personagens_ids:
        tema = _selecionar_tema(pid)

        # Só pergunta signo se o tema for "signos" ou "aleatorio"
        if tema in ("signos", "aleatorio"):
            signo = _selecionar_signo(pid)
        else:
            signo = None  # não será usado

        print()
        cenas_por_video = _perguntar_int(
            mensagem=f"  Quantas cenas por vídeo para {NOMES_EXIBICAO.get(pid, pid)}",
            minimo=1,
            maximo=10,
            padrao=5,
        )

        personagens_config.append({
            "id":              pid,
            "nome":            NOMES_EXIBICAO.get(pid, pid),
            "signo":           signo,
            "tema":            tema,
            "cenas_por_video": cenas_por_video,
        })

    # ── Resumo ───────────────────────────────────────────────
    _cabecalho("RESUMO DA SESSÃO")
    print(f"  Modo:          {modo.capitalize()}")
    print(f"  Vídeos/ciclo:  {videos_por_personagem} por personagem")
    print(f"  Personagens:   {len(personagens_config)}")
    for p in personagens_config:
        signo_str = p["signo"] if p["signo"] else "—"
        print(
            f"    • {p['nome']} — {signo_str} — Tema: {p['tema'].capitalize()} "
            f"— {p['cenas_por_video']} cenas/vídeo"
        )

    total = len(personagens_config) * videos_por_personagem
    print(f"\n  Total por ciclo: {total} vídeos")
    print()

    if not _perguntar_sim_nao("  Confirmar e iniciar?", padrao=True):
        print("\n  Configuração cancelada. Reiniciando menu...\n")
        return exibir_menu()

    return {
        "modo":                  modo,
        "videos_por_personagem": videos_por_personagem,
        "personagens":           personagens_config,
    }