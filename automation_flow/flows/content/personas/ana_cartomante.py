"""
Persona: Ana Cartomante
Arquivo único com tudo que define a Ana: identidade, visual Veo3, temas, signos e gerador.
Para adicionar temas, edite TEMAS. Para mudar o visual, edite os blocos Veo3.
"""
from automation_flow.flows.content.roteiro_core import gerar_roteiro_generico, _contar_palavras

# ── Identidade ────────────────────────────────────────────────────────────────
ID            = "AnaCartomante"
NOME          = "Ana Cartomante"
CENAS_PADRAO  = 5              # valor padrão, mas quantidade de cenas é dinâmica
USA_SIGNOS    = True
SIGNOS        = [
    "Áries", "Touro", "Gêmeos", "Câncer", "Leão", "Virgem",
    "Libra", "Escorpião", "Sagitário", "Capricórnio", "Aquário", "Peixes",
]
SIGNO_PADRAO  = "aleatorio"    # para o menu usar como padrão
TEMA_PADRAO   = "aleatorio"    # para o menu usar como padrão

# ── Temas ─────────────────────────────────────────────────────────────────────
TEMAS = {
    "sorte":     "como atrair sorte e boas energias no dia a dia",
    "amor":      "encontrar ou fortalecer o amor verdadeiro",
    "dinheiro":  "atrair prosperidade e abundância financeira",
    "signos":    "as características e poderes únicos do signo",
    "aleatorio": None,
}

def tema_exige_signo(tema: str) -> bool:
    return tema == "signos"

def fallback_mensagem(tema: str) -> str:
    return f"mensagem poderosa e positiva sobre {tema}"

# ── Blocos fixos do prompt Veo3 ───────────────────────────────────────────────
CHARACTER_BLOCK = (
    "Character: Brazilian woman around 28 years old with light brown skin and golden "
    "undertones. Face: oval shape with soft cheekbones, straight nose, full lips with "
    "soft pink lipstick, long natural lashes, subtle brown eyeliner, thick softly arched "
    "brows, light-brown eyes with tiny amber flecks, a faint beauty mark below the right "
    "cheekbone. Hair: long wavy chestnut hair parted to the side, a few strands tucked "
    "behind the left ear. Outfit: sleeveless deep sapphire-blue dress, pink-quartz pendant "
    "necklace, matching earrings. Nails: almond-shaped, soft blush pink. Presence: warm, "
    "confident, magnetic, energetic Carioca vibes."
)
BACKGROUND_BLOCK = (
    "Background: A real open public square with mosaic paving, a stone fountain, benches, "
    "kiosks, and colorful trees (jacaranda and bougainvillea). People move in soft focus "
    "behind her; no readable signs or logos."
)
LIGHTING_BLOCK = (
    "Lighting: Golden-hour sunlight with warm flares and natural highlights on hair, "
    "skin, jewelry, and water."
)
STYLE_BLOCK = "Style: Hyper-realistic cinematic selfie, 9:16 vertical, gentle handheld movement."
AUDIO_BLOCK = (
    "Background sounds: Fountain water, soft city chatter, footsteps on stone, distant birds.\n"
    "Music: None"
)
TECH_BLOCK = (
    "Model: veo-3\n"
    "Length: 8 seconds\n"
    "Resolution: 1080p (9:16)\n"
    "Framerate: 24fps\n"
    "Negative prompt: No branding, no readable text, no fantasy effects, no facial change, "
    "no outfit inconsistency, no visual distortion."
)
VOICE_STYLE = "Voice: female, highly cheerful, authentic Carioca accent from Rio de Janeiro"

# ── Cenas base dinâmicas ──────────────────────────────────────────────────────
CENA_INICIAL = {
    "nome": "A Revelação",
    "subject_suffix": "delivering an upbeat and energetic hook.",
    "action": (
        "Ana records in selfie mode while walking slowly past the fountain, "
        "bringing the phone slightly closer, smiling with explosive energetic "
        "Carioca vibes, looking directly into the lens."
    ),
    "tone": "enthusiastic tone",
    "objetivo": (
        "Gancho inicial que prende a atenção com identificação imediata, curiosidade e impacto emocional."
    ),
}

CENAS_MEIO = [
    {
        "nome": "O Desafio",
        "subject_suffix": "delivering an empathetic but direct message.",
        "action": (
            "Ana continues walking, tilting her head with a playful, understanding look, "
            "keeping the selfie angle steady while moving past the colorful trees."
        ),
        "tone": "energetic tone",
        "objetivo": (
            "Explorar a dor, o bloqueio ou o desafio central do tema de forma empática e altamente identificável."
        ),
    },
    {
        "nome": "A Transformação",
        "subject_suffix": "delivering a powerful revelation.",
        "action": (
            "Ana stops briefly, her eyes lighting up with vibrant excitement. "
            "The golden sun illuminates her chestnut hair as she smiles widely, "
            "radiating confidence."
        ),
        "tone": "exciting tone",
        "objetivo": (
            "Revelar o dom, a força, a virada ou a mensagem principal com energia alta e sensação de descoberta."
        ),
    },
    {
        "nome": "O Conselho",
        "subject_suffix": "sharing an exciting secret.",
        "action": (
            "Ana leans in close to the camera as if sharing a special secret, "
            "her sapphire-blue dress catching the warm light, while she resumes her slow walk."
        ),
        "tone": "magnetic tone",
        "objetivo": (
            "Trazer orientação prática, conselho espiritual ou passo de ação que aprofunda a conexão com o espectador."
        ),
    },
    {
        "nome": "O Sinal",
        "subject_suffix": "delivering a mystical confirmation.",
        "action": (
            "Ana pauses for a second, lifts one hand softly as if sensing an invisible sign, "
            "and smiles with certainty before looking deeply into the lens."
        ),
        "tone": "intense tone",
        "objetivo": (
            "Reforçar confirmação, pressentimento, alerta ou sincronicidade ligada ao tema, elevando a curiosidade."
        ),
    },
    {
        "nome": "A Direção",
        "subject_suffix": "guiding the viewer with confidence.",
        "action": (
            "Ana keeps walking calmly, gesturing with one hand as if pointing the right path, "
            "with a confident smile and direct eye contact."
        ),
        "tone": "confident tone",
        "objetivo": (
            "Conduzir o espectador para uma decisão, postura ou energia correta dentro do tema abordado."
        ),
    },
]

CENA_FINAL = {
    "nome": "O Chamado (CTA)",
    "subject_suffix": "delivering an energetic call to action.",
    "action": (
        "Ana gives a huge, animated smile, gesturing excitedly downwards towards "
        "the comments area with a blush-pink manicured hand, maintaining her vibrant vibe."
    ),
    "tone": "motivating tone",
    "objetivo": (
        "CTA direto e enérgico pedindo para comentar e interagir. "
        "Deve ativar o engajamento e terminar com energia alta."
    ),
}

# ── Instrução do sistema Gemini ───────────────────────────────────────────────
_INSTRUCAO_SISTEMA = (
    "Você é um especialista em criação de roteiros para vídeos virais de cartomantes "
    "no Instagram e TikTok.\n"
    "Você conhece profundamente o estilo da Ana Cartomante: energética, Carioca, "
    "carismática, direta e espiritual.\n"
    "Seus roteiros combinam identificação emocional, revelação, progressão narrativa e CTA forte.\n"
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
        f"Subject: A hyper-realistic cinematic selfie video of a Brazilian fortune teller "
        f"named Ana walking through an open city square with colorful trees and a central "
        f"fountain during golden hour, {cena['subject_suffix']}\n\n"
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
        if not (18 <= n <= 28):
            avisos.append(
                f"  ⚠ Cena {c['numero']} ({c['nome']}): {n} palavras "
                f"(faixa esperada: 18–28) — '{c.get('dialogo', '')[:60]}...'"
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
    signo_label = signo or "Todos os signos"

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
        f"Crie um roteiro de {n_cenas} cenas para Ana Cartomante:\n"
        f"- Signo: {signo_label}\n"
        f"- Tema: {tema}\n"
        f"- Mensagem central: {mensagem_central}\n\n"
        "REGRAS OBRIGATÓRIAS:\n"
        f"1. Gere EXATAMENTE {n_cenas} cenas\n"
        "2. A cena 1 DEVE ser um gancho forte para prender a atenção imediatamente\n"
        f"3. A cena {n_cenas} DEVE ser um CTA claro pedindo comentário, interação ou engajamento\n"
        "4. As cenas do meio devem criar progressão emocional e narrativa, sem repetição mecânica\n"
        "5. Linguagem em português brasileiro, natural, energética, carismática e espiritual\n"
        "6. texto_tela: máximo 5 palavras + 1 emoji, tudo MAIÚSCULAS\n"
        "7. Use APENAS aspas simples nos diálogos se precisar citar algo — nunca aspas duplas\n"
        "8. Adapte o ritmo do roteiro à quantidade de cenas solicitada, sem travar em estrutura fixa\n\n"
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

    print(f"\n[ROTEIRO] Gerando roteiro — Ana | Signo: {signo_label} | Tema: {tema} | Cenas: {n_cenas}")
    return gerar_roteiro_generico(
        instrucao_sistema=_INSTRUCAO_SISTEMA,
        mensagem_usuario=mensagem_usuario,
        estrutura_cenas=estrutura_cenas,
        n_cenas=n_cenas,
        builder_prompt_veo3=_montar_prompt,
        validar_dialogos=_validar_dialogos,
    )