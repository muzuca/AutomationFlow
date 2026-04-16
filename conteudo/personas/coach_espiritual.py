"""
arquivo: personas/coach_espiritual.py
descrição: Arquivo de identidade do Coach Espiritual. Define visual Veo3, temas acolhedores e bíblicos, e lógica de geração de roteiros profundos com foco em fé e superação.
"""

import random

# Import atualizado para a nova estrutura unificada do core
from conteudo.core import (
    gerar_roteiro_generico,
    contar_palavras,
)

# ── Identidade ────────────────────────────────────────────────────────────────
ID = "CoachEspiritual"
NOME = "Coach Espiritual"
CENAS_PADRAO = 3  # valor padrão, mas quantidade de cenas é dinâmica
USA_SIGNOS = False
SIGNOS: list[str] = []
TEMA_PADRAO = "aleatorio"

HISTORICO_MAX = 100
MIN_PALAVRAS = 15
MAX_PALAVRAS = 25

# ── Temas ─────────────────────────────────────────────────────────────────────
TEMAS = {
    "superacao": "superar a dor com fé, coragem e presença de Deus",
    "amor": "curar o coração e aprender a amar com paz e propósito",
    "fe": "fortalecer a fé mesmo em dias difíceis e silenciosos",
    "deus": "confiar em Deus e descansar no tempo dEle",
    "salmos": "buscar força, consolo e direção espiritual através dos salmos",
    "aleatorio": None,
}


def tema_exige_signo(tema: str) -> bool:
    return False


def fallback_mensagem(tema: str) -> str:
    return f"mensagem espiritual, acolhedora e poderosa sobre {tema}"

# ── Blocos fixos do prompt Veo3 ───────────────────────────────────────────────
CHARACTER_BLOCK = (
    "Character: Serene Brazilian life coach, around 42 years old, composed presence. "
    "Face: calm steady eyes, soft features, short neatly styled gray hair, "
    "salt-and-pepper beard, gentle and empathetic expression. "
    "Outfit: beige knit sweater, dark casual pants, simple and elegant look."
)
BACKGROUND_BLOCK = (
    "Background: Small cozy apartment kitchen in the early morning, with a counter, "
    "a coffee mug, simple cabinets, and a window where soft sunlight enters. "
    "Sometimes an open Bible rests on the table near the coffee cup. "
    "The environment feels quiet, peaceful, and intimate, with no readable signs or logos."
)
LIGHTING_BLOCK = (
    "Lighting: Soft warm early-morning sunlight entering through the window, creating "
    "gentle highlights and a sense of calm hope in the room."
)
STYLE_BLOCK = (
    "Style: Hyper-realistic cinematic video, 9:16 vertical, minimal camera movement, "
    "framed chest-up, focusing on subtle emotional expressions and eye contact."
)
AUDIO_BLOCK = (
    "Background sounds: Very subtle household ambience, faint room tone.\n"
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
    "Voice: calm Brazilian male voice, warm and empathetic, speaking with a soothing, "
    "spiritual and encouraging tone."
)

# ── Cenas base dinâmicas ──────────────────────────────────────────────────────
CENA_INICIAL = {
    "nome": "O Peso da Manhã",
    "subject_suffix": "delivering a compassionate opening reflection.",
    "action": (
        "The coach stands still in the kitchen, holding a mug with both hands at chest level. "
        "He takes a slow deep breath, briefly lowers his eyes as if feeling the weight of the day, "
        "and then looks directly into the camera with empathy."
    ),
    "tone": "gentle and understanding tone",
    "objetivo": (
        "Gancho inicial que reconhece a dor, o cansaço ou o peso emocional do espectador de forma imediata."
    ),
}

CENAS_MEIO = [
    {
        "nome": "Um Dia de Cada Vez",
        "subject_suffix": "sharing a faith-centered reassurance.",
        "action": (
            "The coach is now near the table with an open Bible beside the coffee cup. "
            "He gently touches the open page and nods with peaceful certainty."
        ),
        "tone": "reassuring and spiritual tone",
        "objetivo": (
            "Trazer perspectiva em Deus, calma e acolhimento para diminuir a ansiedade do espectador."
        ),
    },
    {
        "nome": "A Verdade que Sustenta",
        "subject_suffix": "delivering a calm spiritual truth.",
        "action": (
            "The coach speaks with a steady gaze, one hand relaxed over the table, "
            "as soft morning light brightens the kitchen."
        ),
        "tone": "firm and calm tone",
        "objetivo": (
            "Reforçar uma verdade espiritual simples, prática e reconfortante ligada ao tema."
        ),
    },
    {
        "nome": "A Direção",
        "subject_suffix": "guiding the viewer with peaceful certainty.",
        "action": (
            "The coach makes a subtle forward gesture, inviting the viewer to continue with hope and trust."
        ),
        "tone": "encouraging tone",
        "objetivo": (
            "Apontar o próximo passo emocional ou espiritual que o espectador pode tomar hoje."
        ),
    },
    {
        "nome": "O Alívio",
        "subject_suffix": "offering relief and hope.",
        "action": (
            "The coach smiles softly, places one hand on his chest, then breathes slowly "
            "as the room feels calmer."
        ),
        "tone": "hopeful tone",
        "objetivo": (
            "Criar sensação de alívio, consolo e esperança antes do fechamento final."
        ),
    },
]

CENA_FINAL = {
    "nome": "Respira e Entrega",
    "subject_suffix": "delivering an encouraging call to surrender to God.",
    "action": (
        "The coach smiles softly, places one hand on his chest, then slowly gestures forward "
        "as if inviting the viewer to follow in peace. The room feels a little brighter, "
        "conveying relief and hope."
    ),
    "tone": "encouraging and hopeful tone",
    "objetivo": (
        "Fechar com CTA obrigatório pedindo comentário, concordância, 'Amém' ou interação relacionada ao tema."
    ),
}

# ── Instrução do sistema Gemini ───────────────────────────────────────────────
_INSTRUCAO_SISTEMA = (
    "Você é um especialista em criação de roteiros curtos e profundos para um Coach "
    "Espiritual brasileiro.\n"
    "O Coach fala sobre superação, amor, fé e Deus, sempre com mensagens acolhedoras e bíblicas.\n"
    "Os roteiros são usados em vídeos verticais curtos.\n"
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
def _montar_prompt(cena: dict, dialogo: str) -> str:
    d = dialogo.replace('"', "'")
    return (
        "Subject: A hyper-realistic cinematic video of a serene Brazilian spiritual life coach "
        "standing in a small cozy apartment kitchen in the early morning, "
        f"{cena['subject_suffix']}\n\n"
        f"{CHARACTER_BLOCK}\n\n"
        f"{BACKGROUND_BLOCK}\n\n"
        f"{LIGHTING_BLOCK}\n\n"
        f"Action: {cena['action']}\n\n"
        f"{STYLE_BLOCK}\n\n"
        "Dialogue rules:\n"
        "- Spoken in Brazilian Portuguese.\n"
        "- Single continuous sentence per scene.\n"
        f"- STRICT length: around 20 words per scene (one single sentence).\n"
        "- Natural, easy to speak within an 8-second clip.\n\n"
        f"Dialogue: spoken in Brazilian Portuguese [{VOICE_STYLE}, {cena['tone']}]\n"
        f'"{d}"\n\n'
        f"{AUDIO_BLOCK}\n"
        f"{TECH_BLOCK}"
    )

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
    if tema != "aleatorio":
        return tema

    temas_fixos = [t for t in TEMAS.keys() if t != "aleatorio"]
    usados_recentemente = {item.get("tema") for item in (historico or [])[-HISTORICO_MAX:]}
    candidatos = [t for t in temas_fixos if t not in usados_recentemente]

    if candidatos:
        return random.choice(candidatos)

    return random.choice(temas_fixos)


def _montar_regras_nao_repeticao(historico: list[dict]) -> str:
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
            + ". Use abordagens novas, metáforas e exemplos diferentes.\n"
        )

    if exemplos_falas:
        regras += (
            "- NÃO repita frases, ganchos ou histórias muito parecidas com estes exemplos já usados antes. "
            "Crie novas metáforas, novas imagens e novos ganchos:\n"
        )
        for ex in exemplos_falas:
            regras += f'  • "{ex[:80]}..."\n'

    regras += (
        "- Mantenha o mesmo estilo do Coach, mas sempre com falas inéditas, "
        "sem copiar a estrutura exata ou as mesmas imagens de vídeos anteriores.\n"
    )

    return regras

# ── Gerador principal ─────────────────────────────────────────────────────────
def gerar_roteiro(
    tema: str,
    mensagem_central: str,
    signo: str | None,
    n_cenas: int = CENAS_PADRAO,
    historico: list[dict] | None = None,
) -> dict:
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
            f'"texto_tela": "TEXTO + EMOJI", "dialogo": "fala natural"}}'
            for c in estrutura_cenas
        ]
    )

    regras_nao_repeticao = _montar_regras_nao_repeticao(historico)

    mensagem_usuario = (
        f"Crie um roteiro de {n_cenas} cenas para o Coach Espiritual:\n"
        f"- Tema geral: {tema_escolhido}\n"
        f"- Mensagem central: {mensagem_central}\n\n"
        "REGRAS OBRIGATÓRIAS GERAIS:\n"
        f"1. Gere EXATAMENTE {n_cenas} cenas\n"
        "2. A cena 1 DEVE ser um gancho forte, emocional e imediato\n"
        f"3. A cena {n_cenas} DEVE ser um CTA claro pedindo comentário, 'Amém', concordância ou interação\n"
        "4. As cenas do meio devem aprofundar a mensagem com progressão emocional e espiritual\n"
        "5. Linguagem simples, acolhedora, humana e espiritual, em português brasileiro\n"
        "6. texto_tela: máximo 6 palavras, pode ter 1 emoji relevante\n"
        "7. Adapte o ritmo do roteiro à quantidade de cenas pedida, sem depender de estrutura fixa\n"
        "8. Pode citar Deus, fé, oração e versículos de forma natural\n\n"
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
        '  "descricao": "caption — máx 2 frases",\n'
        '  "hashtags": ["#hashtag1", "#hashtag2", "#hashtag3"]\n'
        "}"
    )

    print(
        f"\n[ROTEIRO] Gerando roteiro — Coach Espiritual | Tema: {tema_escolhido} | Cenas: {n_cenas}"
    )

    resultado = gerar_roteiro_generico(
        instrucao_sistema=_INSTRUCAO_SISTEMA,
        mensagem_usuario=mensagem_usuario,
        estrutura_cenas=estrutura_cenas,
        n_cenas=n_cenas,
        builder_prompt_veo3=_montar_prompt,
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