"""
arquivo: personas/ana_cartomante.py
descrição: Arquivo de identidade da Ana Cartomante. Define visual Veo3, temas, regras de áudio Carioca e lógica de geração de roteiros sem repetição.
"""

import random

# Import atualizado para a nova estrutura unificada do core
from conteudo.core import (
    gerar_roteiro_generico,
    contar_palavras,
)

# ── Identidade ────────────────────────────────────────────────────────────────
ID = "AnaCartomante"
NOME = "Ana Cartomante"
CENAS_PADRAO = 5
USA_SIGNOS = True
SIGNOS = [
    "Áries", "Touro", "Gêmeos", "Câncer", "Leão", "Virgem",
    "Libra", "Escorpião", "Sagitário", "Capricórnio", "Aquário", "Peixes",
]
SIGNO_PADRAO = "aleatorio"
TEMA_PADRAO = "aleatorio"

HISTORICO_MAX = 100
MIN_PALAVRAS = 15
MAX_PALAVRAS = 25

# ── Temas ─────────────────────────────────────────────────────────────────────
TEMAS = {
    "sorte": "como atrair sorte e boas energias no dia a dia",
    "amor": "encontrar ou fortalecer o amor verdadeiro",
    "dinheiro": "atrair prosperidade e abundância financeira",
    "signos": "as características e poderes únicos do signo",
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

STYLE_BLOCK = (
    "Style: Hyper-realistic cinematic selfie, 9:16 vertical, gentle handheld movement."
)

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
        f"Subject: A hyper-realistic cinematic selfie video of a Brazilian fortune teller "
        f"named Ana walking through an open city square with colorful trees and a central "
        f"fountain during golden hour, {cena['subject_suffix']}\n\n"
        f"{CHARACTER_BLOCK}\n\n"
        f"{BACKGROUND_BLOCK}\n\n"
        f"{LIGHTING_BLOCK}\n\n"
        f"Action: {cena['action']}\n\n"
        f"{STYLE_BLOCK}\n\n"
        f"Dialogue rules:\n"
        f"- Spoken in Brazilian Portuguese.\n"
        f"- Single continuous sentence per scene.\n"
        f"- STRICT length: around 20 words per scene (one single sentence).\n"
        f"- Natural, easy to speak within an 8-second clip.\n\n"
        f"Dialogue: spoken in Brazilian Portuguese [{VOICE_STYLE}, {cena['tone']}]\n"
        f'"{d}"\n\n'
        f"{AUDIO_BLOCK}\n"
        f"{TECH_BLOCK}"
    )

# ── Validação de diálogos ─────────────────────────────────────────────────────
def _validar_dialogos(cenas_json: list,
                     tema: str,
                     mensagem_central: str,
                     signo_label: str,
                     estrutura_cenas: list) -> list[str]:
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
    exemplos_falas = []

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
        "- Mantenha o mesmo estilo da personagem, mas sempre com falas inéditas, "
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
    signo_label = signo or "Todos os signos"

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
        f"Crie um roteiro de {n_cenas} cenas para Ana Cartomante:\n"
        f"- Signo: {signo_label}\n"
        f"- Tema: {tema_escolhido}\n"
        f"- Mensagem central: {mensagem_central}\n\n"
        "REGRAS OBRIGATÓRIAS GERAIS:\n"
        f"1. Gere EXATAMENTE {n_cenas} cenas\n"
        "2. A cena 1 DEVE ser um gancho forte para prender a atenção imediatamente\n"
        f"3. A cena {n_cenas} DEVE ser um CTA claro pedindo comentário, interação ou engajamento\n"
        "4. As cenas do meio devem criar progressão emocional e narrativa, sem repetição mecânica\n"
        "5. Linguagem em português brasileiro, natural, energética, carismática e espiritual\n"
        "6. texto_tela: máximo 5 palavras + 1 emoji, tudo MAIÚSCULAS\n"
        "7. Use APENAS aspas simples nos diálogos se precisar citar algo — nunca aspas duplas\n"
        "8. Adapte o ritmo do roteiro à quantidade de cenas solicitada, sem travar em estrutura fixa\n\n"
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
        f"\n[ROTEIRO] Gerando roteiro — Ana | Signo: {signo_label} | "
        f"Tema: {tema_escolhido} | Cenas: {n_cenas}"
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
            signo_label,
            estrutura_cenas,
        ),
        min_palavras=MIN_PALAVRAS,
        max_palavras=MAX_PALAVRAS,
    )

    resultado["tema_efetivo"] = tema_escolhido
    resultado["signo_efetivo"] = signo_label
    return resultado