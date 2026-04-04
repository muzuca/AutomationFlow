"""
Persona: Geraldo Executivo
Arquivo único com tudo que define o Geraldo: identidade, visual Veo3, temas e gerador.
Roteiros focados em amor, galanteio de mulheres e viagens românticas de luxo.

Regras extras:
- Cada diálogo de cena (áudio) DEVE ter entre 20 e 22 palavras.
- Evitar repetição de temas aleatórios recentes (quando houver histórico).
- Evitar repetição de falas/contexts muito parecidos com os últimos roteiros (via regras no prompt).
"""

import random

from automation_flow.flows.content.roteiro_core import (
    gerar_roteiro_generico,
    contar_palavras,
)

# ── Identidade ────────────────────────────────────────────────────────────────
ID = "GeraldoExecutivo"
NOME = "Geraldo Executivo"
CENAS_PADRAO = 3  # ele sempre trabalha bem com 3 cenas
USA_SIGNOS = False
SIGNOS: list[str] = []
TEMA_PADRAO = "aleatorio"

HISTORICO_MAX = 100
MIN_PALAVRAS = 15
MAX_PALAVRAS = 25

# ── Temas ─────────────────────────────────────────────────────────────────────
TEMAS = {
    "roma": "viagens românticas em Roma, fontes e noites europeias",
    "praias": "paraísos tropicais, resorts de luxo e ilhas exclusivas",
    "luxo": "hotéis cinco estrelas, jantares elegantes e experiências premium",
    "aleatorio": None,
}


def tema_exige_signo(tema: str) -> bool:
    return False


def fallback_mensagem(tema: str) -> str:
    return f"mensagem romântica, sedutora e elegante sobre viagens inesquecíveis ({tema})"

# ── Blocos fixos do prompt Veo3 ───────────────────────────────────────────────
CHARACTER_BLOCK = (
    "Character: Confident Brazilian executive around 42 years old, strong leader physique. "
    "Face: tanned olive skin, neatly trimmed black beard with gray temples, "
    "piercing brown eyes, short wavy dark hair perfectly styled, magnetic and seductive gaze. "
    "Outfit: camel wool overcoat, black silk shirt slightly unbuttoned showing part of his chest, "
    "tailored dress pants and Italian leather shoes."
)

BACKGROUND_ROMA = (
    "Background: Fontana di Trevi in Rome at night or early dawn, completely empty and silent, "
    "golden lights illuminating the water and baroque architecture, wet cobblestone floor, "
    "romantic European atmosphere."
)

BACKGROUND_PRAIAS = (
    "Background: Empty luxury tropical beach at sunset, calm turquoise sea, light sand, "
    "wooden deck or cabana with warm ambient lights, intimate and exclusive romantic setting."
)

BACKGROUND_LUXO = (
    "Background: Rooftop terrace of a five-star hotel at night, panoramic view of the illuminated city, "
    "elegant table with wine glasses and candles, warm lights and luxurious intimate atmosphere."
)

BACKGROUND_GENERIC = (
    "Background: Cinematic romantic location (European city at night, tropical beach or luxury hotel terrace), "
    "always empty and exclusive, with warm lighting and intimate atmosphere."
)

LIGHTING_BLOCK = (
    "Lighting: Warm cinematic lighting with golden highlights on his face, coat and shirt, "
    "creating depth, romance and exclusivity."
)
STYLE_BLOCK = (
    "Style: Hyper-realistic cinematic video, 9:16 vertical, smooth camera movement, "
    "medium to chest-up framing depending on the scene, focusing on subtle seductive expressions and eye contact."
)
AUDIO_BLOCK = (
    "Background sounds: Very subtle city or ambient noise depending on the location.\n"
    "Music: None."
)
TECH_BLOCK = (
    "Model: veo-3\n"
    "Length: 8 seconds\n"
    "Resolution: 1080p (9:16)\n"
    "Framerate: 24fps\n"
    "Negative prompt: No branding, no readable text, no fantasy effects, no facial change, "
    "no outfit inconsistency, no visual distortion."
)
VOICE_STYLE = (
    "Voice: deep Brazilian male voice, seductive and confident, speaking with smooth, romantic and inviting tone."
)

# ── Cenas base dinâmicas ──────────────────────────────────────────────────────
CENA_INICIAL = {
    "nome": "O Desejo",
    "subject_suffix": "delivering an intimate and romantic opening line to the camera.",
    "action": (
        "Geraldo is turned sideways to the scenery, then slowly turns his body and gaze towards the camera, "
        "with a subtle half-smile, as if sharing a secret romantic thought."
    ),
    "tone": "seductive and soft tone",
    "objetivo": (
        "Gancho inicial revelando que o maior desejo dele não é o lugar, mas a presença dela ao lado dele."
    ),
}

CENAS_MEIO = [
    {
        "nome": "A Cidade Vazia",
        "subject_suffix": "showing the grand romantic scenery as if it exists only for her.",
        "action": (
            "Geraldo walks slowly towards the camera, opening one arm towards the empty scenery, "
            "as if presenting the city or beach as a stage waiting for her."
        ),
        "tone": "romantic and confident tone",
        "objetivo": (
            "Mostrar que toda a grandiosidade do lugar está vazia e esperando apenas pela mulher que ele deseja."
        ),
    },
    {
        "nome": "O Convite Romântico",
        "subject_suffix": "inviting the viewer into an unforgettable romantic night or trip.",
        "action": (
            "Geraldo stands close to the camera, extends his hand in a subtle inviting gesture, "
            "keeping intense eye contact and a soft smile."
        ),
        "tone": "intimate and inviting tone",
        "objetivo": (
            "Criar um convite direto para viver uma noite ou viagem romântica inesquecível ao lado dele."
        ),
    },
]

CENA_FINAL = {
    "nome": "Clica e Vem",
    "subject_suffix": "delivering a direct romantic CTA, asking her to engage and join him.",
    "action": (
        "Geraldo slightly leans in towards the camera, one hand extended as if taking her hand, "
        "and then lightly points to the screen or heart button with a playful confident smile."
    ),
    "tone": "playful and seductive tone",
    "objetivo": (
        "Fechar com CTA pedindo para curtir, seguir e aceitar o convite para viver essa viagem com ele."
    ),
}

# ── Instrução do sistema Gemini ───────────────────────────────────────────────
_INSTRUCAO_SISTEMA = (
    "Você é um especialista em criação de roteiros românticos curtos para o personagem Geraldo Executivo.\n"
    "Geraldo é um executivo brasileiro confiante, sedutor, que convida mulheres para viagens inesquecíveis "
    "em cenários românticos de luxo (Roma, praias paradisíacas, hotéis cinco estrelas).\n"
    "Os roteiros são usados em vídeos verticais curtos, gerados com IA.\n"
    "Responda SEMPRE em JSON válido, sem markdown, sem explicações fora do JSON."
)

# ── Estrutura dinâmica de cenas ───────────────────────────────────────────────
def _gerar_estrutura_cenas(n_cenas: int) -> list[dict]:
    """Gera estrutura com n_cenas dinâmico: 1 = gancho, última = CTA."""
    n_cenas = max(2, int(n_cenas))
    cenas: list[dict] = []

    cenas.append({"numero": 1, **CENA_INICIAL})

    total_meio = n_cenas - 2
    for i in range(total_meio):
        base = CENAS_MEIO[i % len(CENAS_MEIO)].copy()
        base["numero"] = i + 2
        cenas.append(base)

    cenas.append({"numero": n_cenas, **CENA_FINAL})
    return cenas

# ── Montador de prompt Veo3 ───────────────────────────────────────────────────
def _escolher_background(tema: str) -> str:
    if tema == "roma":
        return BACKGROUND_ROMA
    if tema == "praias":
        return BACKGROUND_PRAIAS
    if tema == "luxo":
        return BACKGROUND_LUXO
    return BACKGROUND_GENERIC


def _montar_prompt(cena: dict, dialogo: str, tema: str) -> str:
    d = dialogo.replace('"', "'")
    background = _escolher_background(tema)
    return (
        "Subject: A hyper-realistic cinematic video of a confident Brazilian executive named Geraldo "
        "in an exclusive romantic setting, "
        f"{cena['subject_suffix']}\n\n"
        f"{CHARACTER_BLOCK}\n\n"
        f"{background}\n\n"
        f"{LIGHTING_BLOCK}\n\n"
        f"Action: {cena['action']}\n\n"
        f"{STYLE_BLOCK}\n\n"
        "Dialogue rules:\n"
        "- Spoken in Brazilian Portuguese.\n"
        "- Single continuous sentence per scene.\n"
        f"- STRICT length: around 20 words per scene (one single sentence).\n"
        "- Natural, seductive and easy to speak within an 8-second clip.\n\n"
        f"Dialogue: spoken in Brazilian Portuguese [{VOICE_STYLE}, {cena['tone']}]\n"
        f'"{d}"\n\n'
        f"{AUDIO_BLOCK}\n"
        f"{TECH_BLOCK}"
    )

# ── Ajuste automático de diálogo (desativado) ────────────────────────────────
def _ajustar_dialogo(dialogo: str) -> str:
    """
    Stub mantido apenas por compatibilidade.
    NÃO deve cortar ou alterar o diálogo.
    O ajuste agora é responsabilidade do core via tentativas extras.
    """
    return dialogo

# ── Validação de diálogos ─────────────────────────────────────────────────────
def _validar_dialogos(
    cenas_json: list,
    tema: str,
    mensagem_central: str,
    estrutura_cenas: list,
) -> list[str]:
    avisos: list[str] = []
    erro_grave = False

    for c in cenas_json:
        dialogo = c.get("dialogo", "") or ""
        n = contar_palavras(dialogo)

        if not (MIN_PALAVRAS <= n <= MAX_PALAVRAS):
            avisos.append(
                f"  ⚠ Cena {c.get('numero','?')} ({c.get('nome','?')}): "
                f"{n} palavras relevantes (faixa esperada {MIN_PALAVRAS}–{MAX_PALAVRAS}) — "
                f"'{dialogo[:60]}...'"
            )

        if n < MIN_PALAVRAS or n > MAX_PALAVRAS:
            erro_grave = True

    if erro_grave:
        raise ValueError(
            f"Diálogos fora da margem aceitável "
            f"(precisam estar entre {MIN_PALAVRAS} e {MAX_PALAVRAS} palavras)."
        )

    return avisos

# ── Utilitários de histórico / não repetição ─────────────────────────────────
def _escolher_tema(tema: str, historico: list[dict]) -> str:
    """
    - Se tema != 'aleatorio', retorna o próprio tema.
    - Se tema == 'aleatorio', escolhe um tema que NÃO esteja entre os mais recentes do histórico,
      se possível.
    """
    if tema != "aleatorio":
        return tema

    temas_fixos = [t for t in TEMAS.keys() if t != "aleatorio"]
    usados_recentemente = {item.get("tema") for item in historico[-HISTORICO_MAX:]}
    candidatos = [t for t in temas_fixos if t not in usados_recentemente]

    if candidatos:
        return random.choice(candidatos)

    return random.choice(temas_fixos)


def _montar_regras_nao_repeticao(historico: list[dict]) -> str:
    """
    Gera instruções para o modelo evitando repetição de falas/temas recentes.
    """
    if not historico:
        return ""

    recentes = historico[-HISTORICO_MAX:]
    temas_recent = {item.get("tema") for item in recentes if item.get("tema")}
    exemplos_falas: list[str] = []

    for item in recentes:
        for fala in item.get("falas", [])[:1]:
            exemplos_falas.append(fala)
            if len(exemplos_falas) >= 10:
                break
        if len(exemplos_falas) >= 10:
            break

    regras = "REGRAS DE NÃO REPETIÇÃO:\n"

    if temas_recent:
        regras += (
            "- Evite repetir roteiros idênticos aos últimos temas já usados recentemente: "
            + ", ".join(sorted(list(temas_recent)))
            + ". Use abordagens novas, metáforas e imagens diferentes.\n"
        )

    if exemplos_falas:
        regras += (
            "- NÃO repita frases, ganchos ou descrições muito parecidas com estes exemplos já usados antes. "
            "Crie novas imagens, novos convites e novas formas de falar do mesmo cenário:\n"
        )
        for ex in exemplos_falas:
            regras += f'  • "{ex[:80]}..."\n'

    regras += (
        "- Mantenha o mesmo estilo sedutor e elegante do Geraldo, mas sempre com falas inéditas, "
        "sem copiar a estrutura exata ou as mesmas imagens de vídeos anteriores.\n"
    )

    return regras

# ── Helper para atualizar histórico (usado fora) ─────────────────────────────
def atualizar_historico_geraldo(
    historico: list[dict],
    novo_roteiro: dict,
    tema: str,
    mensagem_central: str,
) -> list[dict]:
    """
    Recebe o histórico anterior + o dict retornado por gerar_roteiro
    e devolve um novo histórico já truncado nos últimos HISTORICO_MAX.
    """
    cenas = novo_roteiro.get("cenas", [])
    falas = [c.get("dialogo", "") for c in cenas if c.get("dialogo")]

    item = {
        "tema": tema,
        "mensagem_central": mensagem_central,
        "falas": falas,
    }

    historico_novo = (historico or []) + [item]
    return historico_novo[-HISTORICO_MAX:]

# ── Gerador principal ─────────────────────────────────────────────────────────
def gerar_roteiro(
    tema: str,
    mensagem_central: str,
    signo: str | None,
    n_cenas: int = CENAS_PADRAO,
    historico: list[dict] | None = None,
) -> dict:
    """
    historico: lista com os últimos roteiros dessa persona.
      Cada item sugerido:
      {
        "tema": "roma",
        "mensagem_central": "...",
        "falas": ["fala cena1", "fala cena2", ...],
        "hash_contexto": "string-opcional"
      }
    """
    historico = historico or []
    n_cenas = max(2, int(n_cenas))
    tema_escolhido = _escolher_tema(tema, historico)
    estrutura_cenas = _gerar_estrutura_cenas(n_cenas)

    descricao_cenas = "\n".join(
        [f"Cena {c['numero']} — {c['nome']}: {c['objetivo']}" for c in estrutura_cenas]
    )
    exemplos_json = ",\n".join(
        [
            f'    {{"numero": {c["numero"]}, "nome": "{c["nome"]}", '
            f'"texto_tela": "TEXTO CURTO", "dialogo": "fala romântica natural"}}'
            for c in estrutura_cenas
        ]
    )

    regras_nao_repeticao = _montar_regras_nao_repeticao(historico)

    mensagem_usuario = (
        f"Crie um roteiro de {n_cenas} cenas para o Geraldo Executivo:\n"
        f"- Tema: {tema_escolhido}\n"
        f"- Mensagem central: {mensagem_central}\n\n"
        "REGRAS OBRIGATÓRIAS GERAIS:\n"
        f"1. Gere EXATAMENTE {n_cenas} cenas\n"
        "2. A cena 1 DEVE ser um gancho romântico forte, mostrando que o maior desejo dele é a presença dela\n"
        f"3. A cena {n_cenas} DEVE ser um CTA claro pedindo para curtir, seguir e aceitar o convite para a viagem\n"
        "4. As cenas do meio devem explorar o cenário romântico, o luxo e a exclusividade de viver isso ao lado dele\n"
        "5. Linguagem sedutora, elegante, sem vulgaridade; foco em romance, viagem, luxo e conexão emocional\n"
        "6. texto_tela: frase curta impactante (máx 6 palavras), em MAIÚSCULAS, pode ter 1 emoji\n"
        "7. Adapte o ritmo do roteiro à quantidade de cenas pedida, sem depender de estrutura fixa\n\n"
        "REGRAS ESPECÍFICAS PARA O DIÁLOGO (ÁUDIO):\n"
        " - Cada cena deve ter UM ÚNICO diálogo contínuo.\n"
        " - O diálogo de cada cena DEVE ter EXATAMENTE 20 palavras.\n"
        " - Pense como um áudio de até 8 segundos: se passar disso, fica corrido e ruim.\n"
        " - Nunca quebre o diálogo em duas falas; é sempre uma fala única por cena.\n"
        f"{regras_nao_repeticao}\n"
        "ESTRUTURA DAS CENAS:\n"
        f"{descricao_cenas}\n\n"
        "Retorne EXATAMENTE este JSON (sem markdown):\n"
        "{\n"
        '  "cenas": [\n'
        f"{exemplos_json}\n"
        "  ],\n"
        '  "descricao": "caption — resumo romântico em máx 2 frases",\n'
        '  "hashtags": ["#viagemromantica", "#amor", "#luxo"]\n'
        "}"
    )

    print(
        f"\n[ROTEIRO] Gerando roteiro — Geraldo Executivo | Tema: {tema_escolhido} | Cenas: {n_cenas}"
    )

    resultado = gerar_roteiro_generico(
        instrucao_sistema=_INSTRUCAO_SISTEMA,
        mensagem_usuario=mensagem_usuario,
        estrutura_cenas=estrutura_cenas,
        n_cenas=n_cenas,
        builder_prompt_veo3=lambda cena, dialogo: _montar_prompt(
            cena, dialogo, tema_escolhido
        ),
        validar_dialogos=lambda cenas_json: _validar_dialogos(
            cenas_json,
            tema_escolhido,
            mensagem_central,
            estrutura_cenas,
        ),
        min_palavras=MIN_PALAVRAS,
        max_palavras=MAX_PALAVRAS,
    )

    resultado["tema_efetivo"] = tema_escolhido
    return resultado