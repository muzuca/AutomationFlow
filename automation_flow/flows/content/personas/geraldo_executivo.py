"""
Persona: Geraldo Executivo
Arquivo único com tudo que define o Geraldo: identidade, visual Veo3, temas e gerador.
Roteiros focados em amor, galanteio de mulheres e viagens românticas de luxo.
"""
from automation_flow.flows.content.roteiro_core import gerar_roteiro_generico, _contar_palavras


# ── Identidade ────────────────────────────────────────────────────────────────
ID           = "GeraldoExecutivo"
NOME         = "Geraldo Executivo"
CENAS_PADRAO = 3               # ele sempre trabalha bem com 3 cenas
USA_SIGNOS   = False
SIGNOS       = []
TEMA_PADRAO  = "aleatorio"     # para o menu usar como padrão


# ── Temas ─────────────────────────────────────────────────────────────────────
TEMAS = {
    "roma":      "viagens românticas em Roma, fontes e noites europeias",
    "praias":    "paraísos tropicais, resorts de luxo e ilhas exclusivas",
    "luxo":      "hotéis cinco estrelas, jantares elegantes e experiências premium",
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
    "Length: 6 seconds\n"
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


def _gerar_estrutura_cenas(n_cenas: int) -> list[dict]:
    """Gera estrutura com n_cenas dinâmico: 1 = gancho, última = CTA. Para Geraldo, mínimo 3 funciona melhor."""
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
        f"Subject: A hyper-realistic cinematic video of a confident Brazilian executive named Geraldo "
        f"in an exclusive romantic setting, {cena['subject_suffix']}\n\n"
        f"{CHARACTER_BLOCK}\n\n"
        f"{background}\n\n"
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
        if n != 19:
            avisos.append(
                f"  ⚠ Cena {c['numero']} ({c['nome']}): {n} palavras "
                f"(esperado: 19) — '{c.get('dialogo', '')[:60]}...'"
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
            f'"texto_tela": "TEXTO CURTO", "dialogo": "fala romântica com 19 palavras"}}'
            for c in estrutura_cenas
        ]
    )

    mensagem_usuario = (
        f"Crie um roteiro de {n_cenas} cenas para o Geraldo Executivo:\n"
        f"- Tema: {tema}\n"
        f"- Mensagem central: {mensagem_central}\n\n"
        "REGRAS OBRIGATÓRIAS:\n"
        f"1. Gere EXATAMENTE {n_cenas} cenas\n"
        "2. A cena 1 DEVE ser um gancho romântico forte, mostrando que o desejo dele é a presença dela\n"
        f"3. A cena {n_cenas} DEVE ser um CTA claro pedindo para curtir, seguir e aceitar o convite para a viagem\n"
        "4. As cenas do meio devem explorar o cenário romântico e a exclusividade de viver isso ao lado dele\n"
        "5. A fala (dialogo) de CADA cena deve ter EXATAMENTE 19 palavras em português brasileiro\n"
        "6. texto_tela: frase curta impactante (máx 6 palavras), em MAIÚSCULAS, pode ter 1 emoji\n"
        "7. Linguagem sedutora, elegante, sem vulgaridade; foco em romance, viagem, luxo e conexão emocional\n\n"
        f"ESTRUTURA DAS CENAS:\n{descricao_cenas}\n\n"
        "Retorne EXATAMENTE este JSON (sem markdown):\n"
        "{\n"
        '  "cenas": [\n'
        f"{exemplos_json}\n"
        "  ],\n"
        '  "descricao": "caption — resumo romântico em máx 2 frases",\n'
        '  "hashtags": ["#viagemromantica", "#amor", "#luxo"]\n'
        "}"
    )

    print(f"\n[ROTEIRO] Gerando roteiro — Geraldo Executivo | Tema: {tema} | Cenas: {n_cenas}")
    return gerar_roteiro_generico(
        instrucao_sistema=_INSTRUCAO_SISTEMA,
        mensagem_usuario=mensagem_usuario,
        estrutura_cenas=estrutura_cenas,
        n_cenas=n_cenas,
        builder_prompt_veo3=lambda cena, dialogo: _montar_prompt(cena, dialogo, tema),
        validar_dialogos=_validar_dialogos,
    )