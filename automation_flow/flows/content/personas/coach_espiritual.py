"""
Persona: Coach Espiritual
Arquivo único com tudo que define o Coach: identidade, visual Veo3, temas e gerador.
Para adicionar temas, edite TEMAS. Para mudar o visual, edite os blocos Veo3.
"""
from automation_flow.flows.content.roteiro_core import gerar_roteiro_generico, _contar_palavras

# ── Identidade ────────────────────────────────────────────────────────────────
ID            = "CoachEspiritual"
NOME          = "Coach Espiritual"
CENAS_PADRAO  = 3              # valor padrão, mas quantidade de cenas é dinâmica
USA_SIGNOS    = False
SIGNOS        = []
TEMA_PADRAO   = "aleatorio"    # para o menu usar como padrão

# ── Temas ─────────────────────────────────────────────────────────────────────
TEMAS = {
    "superacao": "superar a dor com fé, coragem e presença de Deus",
    "amor":      "curar o coração e aprender a amar com paz e propósito",
    "fe":        "fortalecer a fé mesmo em dias difíceis e silenciosos",
    "deus":      "confiar em Deus e descansar no tempo dEle",
    "salmos":    "buscar força, consolo e direção espiritual através dos salmos",
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
    "Length: 6 seconds\n"
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

def _gerar_estrutura_cenas(n_cenas: int) -> list[dict]:
    """Gera estrutura com n_cenas dinâmico: 1 = gancho, última = CTA."""
    n_cenas = max(2, int(n_cenas))
    cenas: list[dict] = []

    # cena 1: gancho
    cenas.append({"numero": 1, **CENA_INICIAL})

    # cenas do meio
    total_meio = n_cenas - 2
    for i in range(total_meio):
        base = CENAS_MEIO[i % len(CENAS_MEIO)].copy()
        base["numero"] = i + 2
        cenas.append(base)

    # última: CTA
    cenas.append({"numero": n_cenas, **CENA_FINAL})
    return cenas

# ── Montador de prompt Veo3 ───────────────────────────────────────────────────
def _montar_prompt(cena: dict, dialogo: str) -> str:
    d = dialogo.replace('"', "'")
    return (
        f"Subject: A hyper-realistic cinematic video of a serene Brazilian spiritual life coach "
        f"standing in a small cozy apartment kitchen in the early morning, "
        f"{cena['subject_suffix']}\n\n"
        f"{CHARACTER_BLOCK}\n\n"
        f"{BACKGROUND_BLOCK}\n\n"
        f"{LIGHTING_BLOCK}\n\n"
        f"Action: {cena['action']}\n\n"
        f"{STYLE_BLOCK}\n\n"
        f"Dialogue: spoken in Brazilian Portuguese [{VOICE_STYLE}, {cena['tone']}]\n"
        f'"{d}"\n\n'
        f"{AUDIO_BLOCK}\n"
        f"{TECH_BLOCK}"
    )

# ── Validação de diálogos ─────────────────────────────────────────────────────
def _validar_dialogos(cenas_json: list) -> list[str]:
    avisos = []
    for c in cenas_json:
        n = _contar_palavras(c.get("dialogo", ""))
        if not (12 <= n <= 24):
            avisos.append(
                f"  ⚠ Cena {c['numero']} ({c['nome']}): {n} palavras "
                f"(faixa esperada: 12–24) — '{c.get('dialogo', '')[:60]}...'"
            )
    return avisos

# ── Gerador principal ─────────────────────────────────────────────────────────
def gerar_roteiro(
    tema: str,
    mensagem_central: str,
    signo: str | None,
    n_cenas: int = CENAS_PADRAO,
) -> dict:
    n_cenas = max(2, int(n_cenas))
    estrutura_cenas = _gerar_estrutura_cenas(n_cenas)

    descricao_cenas = "\n".join(
        [f"Cena {c['numero']} — {c['nome']}: {c['objetivo']}" for c in estrutura_cenas]
    )
    exemplos_json = ",\n".join(
        [
            f'    {{"numero\": {c["numero"]}, "nome": "{c["nome"]}", '
            f'"texto_tela": "TEXTO + EMOJI", "dialogo": "fala natural"}}'
            for c in estrutura_cenas
        ]
    )

    mensagem_usuario = (
        f"Crie um roteiro de {n_cenas} cenas para o Coach Espiritual:\n"
        f"- Tema geral: {tema}\n"
        f"- Mensagem central: {mensagem_central}\n\n"
        "REGRAS OBRIGATÓRIAS:\n"
        f"1. Gere EXATAMENTE {n_cenas} cenas\n"
        "2. A cena 1 DEVE ser um gancho forte, emocional e imediato\n"
        f"3. A cena {n_cenas} DEVE ser um CTA claro pedindo comentário, 'Amém', concordância ou interação\n"
        "4. As cenas do meio devem aprofundar a mensagem com progressão emocional e espiritual\n"
        "5. Linguagem simples, acolhedora, humana e espiritual, em português brasileiro\n"
        "6. texto_tela: máximo 6 palavras, pode ter 1 emoji relevante\n"
        "7. Adapte o ritmo do roteiro à quantidade de cenas pedida, sem depender de estrutura fixa\n"
        "8. Pode citar Deus, fé, oração e versículos de forma natural\n\n"
        f"ESTRUTURA DAS CENAS:\n{descricao_cenas}\n\n"
        "Retorne EXATAMENTE este JSON (sem markdown):\n"
        "{\n"
        '  "cenas": [\n'
        f"{exemplos_json}\n"
        "  ],\n"
        '  "descricao": "caption — máx 2 frases",\n'
        '  "hashtags": ["#hashtag1", "#hashtag2", "#hashtag3"]\n'
        "}"
    )

    print(f"\n[ROTEIRO] Gerando roteiro — Coach Espiritual | Tema: {tema} | Cenas: {n_cenas}")
    return gerar_roteiro_generico(
        instrucao_sistema=_INSTRUCAO_SISTEMA,
        mensagem_usuario=mensagem_usuario,
        estrutura_cenas=estrutura_cenas,
        n_cenas=n_cenas,
        builder_prompt_veo3=_montar_prompt,
        validar_dialogos=_validar_dialogos,
    )