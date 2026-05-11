# content/menu.py — Menu interativo de configuração da sessão de conteúdo orgânico
from pathlib import Path
from content import personas


SIGNOS_LISTA = [
    "Áries", "Touro", "Gêmeos", "Câncer", "Leão", "Virgem",
    "Libra", "Escorpião", "Sagitário", "Capricórnio", "Aquário", "Peixes",
    "aleatorio",
]
SIGNOS_LABEL = {"aleatorio": "Aleatório (sorteia um signo a cada vídeo)"}


def linha(char="=", largura=52):
    print(char * largura)


def cabecalho(titulo):
    linha()
    print(f"  {titulo}")
    linha()


def perguntar_int(mensagem, minimo, maximo, padrao):
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
            print("  Entrada inválida.")


def perguntar_sim_nao(mensagem, padrao=True):
    opcoes = "S/n" if padrao else "s/N"
    while True:
        entrada = input(f"{mensagem} [{opcoes}]: ").strip().lower()
        if not entrada:
            return padrao
        if entrada in ("s", "sim", "y", "yes"):
            return True
        if entrada in ("n", "nao", "não", "no"):
            return False
        print("  Digite S ou N.")


def selecionar_personagens() -> list[str]:
    ids = personas.listar()
    nms = personas.nomes()
    cabecalho("PERSONAGENS")
    print("  Personagens disponíveis:")
    for i, pid in enumerate(ids, 1):
        print(f"  {i}. {nms[pid]}")
    print("  Digite os números separados por vírgula (ex: 1,2)")
    print("  Pressione Enter para selecionar todos.")
    while True:
        entrada = input("  Personagens: ").strip()
        if not entrada:
            print("  Todos os personagens selecionados.")
            return ids.copy()
        try:
            indices = [int(x.strip()) for x in entrada.split(",")]
            selecionados = []
            ok = True
            for idx in indices:
                if 1 <= idx <= len(ids):
                    selecionados.append(ids[idx - 1])
                else:
                    print(f"  Número {idx} inválido.")
                    ok = False
                    break
            if ok and selecionados:
                print(f"  Selecionados: {', '.join(nms[p] for p in selecionados)}")
                return selecionados
        except ValueError:
            print("  Formato inválido.")


def selecionar_tema(pid: str) -> str:
    persona = personas.obter(pid)
    cabecalho(f"TEMA — {persona.NOME}")
    temas = list(persona.TEMAS.keys())
    tema_padrao = getattr(persona, "TEMA_PADRAO", "aleatorio")
    print("  Temas disponíveis:")
    for i, t in enumerate(temas, 1):
        sufixo = " (sorteia a cada vídeo)" if t == "aleatorio" else ""
        marcador = " [padrão]" if t == tema_padrao else ""
        print(f"  {i}. {t.capitalize()}{sufixo}{marcador}")
    padrao_idx = temas.index(tema_padrao) + 1 if tema_padrao in temas else 1
    while True:
        try:
            entrada = input(f"  Tema [1-{len(temas)}] [{padrao_idx}]: ").strip()
            if not entrada:
                idx = padrao_idx - 1
            else:
                idx = int(entrada) - 1
            if 0 <= idx < len(temas):
                tema = temas[idx]
                print(f"  Tema selecionado: {tema.capitalize()}")
                return tema
            print(f"  Digite entre 1 e {len(temas)}.")
        except ValueError:
            print("  Entrada inválida.")


def selecionar_signo(pid: str) -> str | None:
    persona = personas.obter(pid)
    if not getattr(persona, "USA_SIGNOS", False):
        return None
    cabecalho(f"SIGNO — {persona.NOME}")
    signo_padrao = getattr(persona, "SIGNO_PADRAO", "aleatorio")
    print("  Signos disponíveis:")
    for i, s in enumerate(SIGNOS_LISTA, 1):
        label = SIGNOS_LABEL.get(s, s)
        marcador = " [padrão]" if s == signo_padrao else ""
        print(f"  {i:2}. {label}{marcador}")
    padrao_idx = (
        SIGNOS_LISTA.index(signo_padrao) + 1
        if signo_padrao in SIGNOS_LISTA
        else len(SIGNOS_LISTA)
    )
    while True:
        try:
            entrada = input(f"  Signo [1-{len(SIGNOS_LISTA)}] [{padrao_idx}]: ").strip()
            if not entrada:
                idx = padrao_idx - 1
            else:
                idx = int(entrada) - 1
            if 0 <= idx < len(SIGNOS_LISTA):
                signo = SIGNOS_LISTA[idx]
                label = SIGNOS_LABEL.get(signo, signo)
                print(f"  Signo selecionado: {label}")
                return signo
            print(f"  Digite entre 1 e {len(SIGNOS_LISTA)}.")
        except ValueError:
            print("  Entrada inválida.")


def exibir_menu(settings=None) -> dict:
    """Menu interativo para configuração da sessão de conteúdo orgânico."""
    cabecalho("AUTOMAÇÃO DE VÍDEOS — CONFIGURAÇÃO DA SESSÃO")

    # Modo de execução
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

    # Quantidade de vídeos é FIXA: 1 por personagem por ciclo
    # O scheduler controla quantos ciclos rodam por dia (baseado em HORARIOS_PUBLICACAO)
    videos_por_personagem = 1

    # Personagens
    linha("-", 52)
    personagens_ids = selecionar_personagens()
    personagens_config = []

    padrao_cenas = 5
    for pid in personagens_ids:
        persona = personas.obter(pid)
        tema = selecionar_tema(pid)
        signo = selecionar_signo(pid)
        cenas_padrao = getattr(persona, "CENAS_PADRAO", padrao_cenas)
        cenas_por_video = perguntar_int(
            f"  Quantas cenas por vídeo para {persona.NOME}",
            minimo=2, maximo=50, padrao=cenas_padrao,
        )

        # Opções de variação visual entre cenas
        variar_cenario = perguntar_sim_nao(
            f"  Variar cenário entre cenas? ({persona.NOME})", padrao=False,
        )
        variar_roupa = perguntar_sim_nao(
            f"  Variar roupa entre cenas? ({persona.NOME})", padrao=False,
        )

        personagens_config.append({
            "id": pid,
            "nome": persona.NOME,
            "signo": signo,
            "tema": tema,
            "cenas_por_video": cenas_por_video,
            "variar_cenario": variar_cenario,
            "variar_roupa": variar_roupa,
        })

    # Resumo
    import os as _os
    _max_videos = int(_os.getenv("MAX_VIDEOS_POR_PERSONAGEM", "15"))
    _poll_min = int(_os.getenv("WATCHER_POLL_MINUTOS", "2"))
    _videos_base = _os.getenv("VIDEOS_BASE_DIR", "G:/Meu Drive/Videos")
    
    cabecalho("RESUMO DA SESSÃO")
    print(f"  Modo:             {modo.capitalize()}")
    print(f"  Alvo por persona: {_max_videos} vídeos (MAX_VIDEOS_POR_PERSONAGEM)")
    print(f"  Poll quando cheio: {_poll_min} min")
    print(f"  Personagens:      {len(personagens_config)}")
    for p in personagens_config:
        signo_str = p["signo"] if p["signo"] else "—"
        cenario_str = "variável" if p.get("variar_cenario") else "fixo"
        roupa_str = "variável" if p.get("variar_roupa") else "fixa"
        # Conta vídeos existentes no diretório
        pasta_persona = Path(_videos_base) / p["id"]
        n_existentes = len(list(pasta_persona.glob("*.mp4"))) if pasta_persona.exists() else 0
        faltam = max(0, _max_videos - n_existentes)
        status = f"✅ cheio" if faltam == 0 else f"faltam {faltam}"
        print(
            f"    {p['nome']} | {signo_str} | "
            f"{p['tema'].capitalize()} | {p['cenas_por_video']} cenas | "
            f"cenário {cenario_str} | roupa {roupa_str} | "
            f"{n_existentes}/{_max_videos} ({status})"
        )
    print()

    if not perguntar_sim_nao("  Confirmar e iniciar?", padrao=True):
        print("  Configuração cancelada. Reiniciando...")
        return exibir_menu(settings)

    return {
        "modo": modo,
        "videos_por_personagem": videos_por_personagem,
        "personagens": personagens_config,
    }
