"""
Persona: Peão de Propósito
Arquivo único com tudo que define o Peão: identidade, visual Veo3, temas e gerador.
Roteiros focados em fé, salmos, motivação e superação em contexto de fazenda.
"""
from automation_flow.flows.content.roteiro_core import gerar_roteiro_generico, _contar_palavras


# ── Identidade ────────────────────────────────────────────────────────────────
ID           = "PeaoDeProposito"
NOME         = "Peão de Propósito"
CENAS_PADRAO = 3               # valor padrão
USA_SIGNOS   = False
SIGNOS       = []
TEMA_PADRAO  = "aleatorio"     # para o menu usar como padrão


# ── Temas ─────────────────────────────────────────────────────────────────────
TEMAS = {
    "fe":        "mensagens de fé e confiança em Deus no meio da rotina do campo",
    "salmos":    "reflexões e consolo baseados em salmos e textos bíblicos",
    "superacao": "motivação para quem está cansado, lutando e quase desistindo",
    "aleatorio": None,
}


def tema_exige_signo(tema: str) -> bool:
    return False


def fallback_mensagem(tema: str) -> str:
    return f"mensagem de fé, salmos e superação em ambiente de fazenda ({tema})"


# ── Blocos fixos do prompt Veo3 ───────────────────────────────────────────────
CHARACTER_BLOCK = (
    "Character: Handsome 30-year-old Brazilian farmer, strong masculine presence, natural athletic build from hard farm work, "
    "square jaw, sun-kissed tanned skin. CRITICAL: He has a short, rugged stubble beard, deep light-brown eyes, and a subtle, "
    "knowing but welcoming half-smile. He wears his signature weathered straw hat (always on his head), a faded plaid flannel "
    "shirt with rolled-up sleeves and slightly open collar revealing a subtle silver crucifix chain, and well-worn rugged denim jeans."
)

BACKGROUND_AMANHECER = (
    "Background: Early morning at a real Brazilian farm, low mist over the green pasture, "
    "soft light from the rising sun in the background, wooden fences and distant trees. "
    "The scene conveys peace, new beginnings and God's presence in nature."
)

BACKGROUND_SALMOS = (
    "Background: Morning at the farm with an open Bible resting on a wooden fence or wooden post, "
    "green pasture and trees in the background, soft sunlight touching the pages. "
    "Atmosphere of devotion, reflection and intimacy with God."
)

BACKGROUND_SUPERACAO = (
    "Background: Late afternoon at the farm after a hard work day, slightly dusty ground, "
    "tools or equipment in soft focus, sky in warm orange tones. "
    "Atmosphere of tiredness but also strength, resilience and hope."
)

BACKGROUND_GENERIC = (
    "Background: Authentic Brazilian rural setting (farm), with pasture, wooden fences, "
    "trees and either morning mist or warm sunset light, always conveying peace and God's presence."
)

LIGHTING_BLOCK = (
    "Lighting: Natural warm sunlight (sunrise or sunset), creating soft highlights on his face, hat and shirt, "
    "with gentle shadows that emphasize depth and realism."
)
STYLE_BLOCK = (
    "Style: Hyper-realistic cinematic video, 9:16 vertical, minimal camera movement, "
    "framed from waist up or chest up, focusing on subtle emotional expressions and eye contact."
)
AUDIO_BLOCK = (
    "Background sounds: Very subtle rural ambience — distant birds, soft wind, maybe faint animal sounds.\n"
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
    "Voice: deep Brazilian male voice, calm and gentle, with rural accent, speaking with spiritual, encouraging and peaceful tone."
)


# ── Cenas base dinâmicas ──────────────────────────────────────────────────────
CENA_INICIAL = {
    "nome": "Semente na Madrugada",
    "subject_suffix": "delivering an opening reflection about pain and planted seeds in life's early hours.",
    "action": (
        "The farmer is leaning on a rustic wooden fence, holding an enamel coffee mug. "
        "He takes a small sip, lowers the mug and looks directly at the camera with a serene, mature and understanding gaze."
    ),
    "tone": "gentle and spiritual tone",
    "objetivo": (
        "Gancho inicial reconhecendo o peso, a luta e o choro de quem está plantando no silêncio."
    ),
}

CENAS_MEIO = [
    {
        "nome": "A Luta do Campo",
        "subject_suffix": "connecting farm work struggles to the viewer's inner battles.",
        "action": (
            "He walks slowly along the fence, passing his hand over the wood or barbed wire, "
            "sometimes looking at the ground, sometimes at the horizon, breathing deeply."
        ),
        "tone": "honest and empathetic tone",
        "objetivo": (
            "Mostrar que a rotina dura do campo simboliza as batalhas diárias de quem está cansado e quase desistindo."
        ),
    },
    {
        "nome": "A Palavra que Sustenta",
        "subject_suffix": "sharing a Bible-based encouragement about harvest and God's timing.",
        "action": (
            "He stops, rests one arm on the fence, opens or points to a Bible or simply closes his eyes for a brief moment, "
            "then looks to the camera with conviction."
        ),
        "tone": "firm and comforting tone",
        "objetivo": (
            "Trazer uma verdade bíblica simples sobre colheita, promessa e tempo de Deus que sustenta o coração."
        ),
    },
]

CENA_FINAL = {
    "nome": "A Colheita Vai Chegar",
    "subject_suffix": "delivering a direct word of faith and a CTA to agree and trust.",
    "action": (
        "He steps closer to the camera, places one hand on his chest and slightly extends the other hand forward, "
        "as if blessing or supporting the viewer, with a soft but confident smile."
    ),
    "tone": "encouraging and hopeful tone",
    "objetivo": (
        "Fechar com uma declaração de fé forte e CTA pedindo para comentar, escrever 'Amém' ou compartilhar a mensagem."
    ),
}


# ── Instrução do sistema Gemini ───────────────────────────────────────────────
_INSTRUCAO_SISTEMA = (
    "Você é um especialista em criação de roteiros curtos de fé, salmos, motivação e superação "
    "para o personagem Peão de Propósito.\n"
    "Peão de Propósito é um fazendeiro brasileiro de 30 anos, bonito e marcado pelo trabalho no campo, "
    "que passa mensagens de Deus, salmos e encorajamento para quem está cansado.\n"
    "Os roteiros são usados em vídeos verticais curtos, gerados com IA.\n"
    "Responda SEMPRE em JSON válido, sem markdown, sem explicações fora do JSON."
)


def _gerar_estrutura_cenas(n_cenas: int) -> list[dict]:
    """Gera estrutura com n_cenas dinâmico: 1 = gancho, última = CTA. Para o Peão, mínimo 3 funciona melhor."""
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
    if tema == "fe":
        return BACKGROUND_AMANHECER
    if tema == "salmos":
        return BACKGROUND_SALMOS
    if tema == "superacao":
        return BACKGROUND_SUPERACAO
    return BACKGROUND_GENERIC


def _montar_prompt(cena: dict, dialogo: str, tema: str) -> str:
    d = dialogo.replace('"', "'")
    background = _escolher_background(tema)
    return (
        f"Subject: A hyper-realistic cinematic video of a Brazilian farmer called Peão de Propósito on his farm, "
        f"{cena['subject_suffix']}\n\n"
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
            f'"texto_tela": "TEXTO CURTO", "dialogo": "frase de fé com 19 palavras"}}'
            for c in estrutura_cenas
        ]
    )

    mensagem_usuario = (
        f"Crie um roteiro de {n_cenas} cenas para o personagem Peão de Propósito:\n"
        f"- Tema: {tema}\n"
        f"- Mensagem central: {mensagem_central}\n\n"
        "REGRAS OBRIGATÓRIAS:\n"
        f"1. Gere EXATAMENTE {n_cenas} cenas\n"
        "2. A cena 1 DEVE ser um gancho emocional forte, reconhecendo a dor e a luta de quem assiste\n"
        f"3. A cena {n_cenas} DEVE ser um CTA claro pedindo para comentar, escrever 'Amém' ou compartilhar\n"
        "4. As cenas do meio devem conectar o cenário da fazenda com as lutas internas e a esperança em Deus\n"
        "5. A fala (dialogo) de CADA cena deve ter EXATAMENTE 19 palavras em português brasileiro\n"
        "6. texto_tela: frase curta impactante (máx 6 palavras), em MAIÚSCULAS, pode ter 1 emoji de fé ou força\n"
        "7. Linguagem simples, rural, espiritual, trazendo consolo, fé e motivação, sem sensacionalismo\n\n"
        f"ESTRUTURA DAS CENAS:\n{descricao_cenas}\n\n"
        "Retorne EXATAMENTE este JSON (sem markdown):\n"
        "{\n"
        '  "cenas": [\n'
        f"{exemplos_json}\n"
        "  ],\n"
        '  "descricao": "caption — resumo de fé e encorajamento em máx 2 frases",\n'
        '  "hashtags": ["#fe", "#superacao", "#deusnocampo"]\n'
        "}"
    )

    print(f"\n[ROTEIRO] Gerando roteiro — Peão de Propósito | Tema: {tema} | Cenas: {n_cenas}")
    return gerar_roteiro_generico(
        instrucao_sistema=_INSTRUCAO_SISTEMA,
        mensagem_usuario=mensagem_usuario,
        estrutura_cenas=estrutura_cenas,
        n_cenas=n_cenas,
        builder_prompt_veo3=lambda cena, dialogo: _montar_prompt(cena, dialogo, tema),
        validar_dialogos=_validar_dialogos,
    )