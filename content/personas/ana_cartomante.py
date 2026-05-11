"""
Persona: Ana Cartomante
Identidade fixa (rosto/voz) + liberdade criativa total para cenarios, roupas e acoes.
O Gemini decide onde, como e o que vestir. Nos rastreamos tudo pra nao repetir.
"""

import random

from content.roteiro_core import gerar_roteiro_generico, contar_palavras
from content.historico_persona import (
    montar_contexto_anti_repeticao,
    registrar_video,
)

# ── Identidade ────────────────────────────────────────────────────────────────
ID = "AnaCartomante"
NOME = "Ana Cartomante"
CENAS_PADRAO = 5
USA_SIGNOS = True
SIGNOS = [
    "Aries", "Touro", "Gemeos", "Cancer", "Leao", "Virgem",
    "Libra", "Escorpiao", "Sagitario", "Capricornio", "Aquario", "Peixes",
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
    "dinheiro": "atrair prosperidade e abundancia financeira",
    "signos": "as caracteristicas e poderes unicos do signo",
    "aleatorio": None,
}


def tema_exige_signo(tema: str) -> bool:
    return tema == "signos"


def fallback_mensagem(tema: str) -> str:
    return f"mensagem poderosa e positiva sobre {tema}"


# ── Blocos FIXOS (identidade do personagem — nao muda) ───────────────────────
CHARACTER_BLOCK = (
    "Character: Brazilian woman around 28 years old with light brown skin and golden "
    "undertones. Face: oval shape with soft cheekbones, straight nose, full lips with "
    "soft pink lipstick, long natural lashes, subtle brown eyeliner, thick softly arched "
    "brows, light-brown eyes with tiny amber flecks, a faint beauty mark below the right "
    "cheekbone. Hair: long wavy chestnut hair parted to the side, a few strands tucked "
    "behind the left ear. Presence: warm, confident, magnetic, energetic Carioca vibes."
)

VOICE_STYLE = "Voice: female, highly cheerful, authentic Carioca accent from Rio de Janeiro"

STYLE_BLOCK = (
    "Style: Hyper-realistic cinematic selfie video, 9:16 vertical, gentle handheld sway."
)

TECH_BLOCK = (
    "Model: veo-3\n"
    "Length: 8 seconds\n"
    "Resolution: 1080p (9:16)\n"
    "Framerate: 24fps\n"
    "Negative prompt: No branding, no readable text, no fantasy effects, no facial change, "
    "no visual distortion."
)

# ── Instrucao do sistema Gemini ───────────────────────────────────────────────
_INSTRUCAO_SISTEMA = (
    "Voce e um diretor criativo especialista em videos virais de cartomantes no Instagram e TikTok.\n"
    "Voce cria roteiros para a Ana Cartomante: energetica, Carioca, carismatica, espiritual.\n"
    "Voce tem LIBERDADE TOTAL para escolher cenarios, roupas, acoes e atmosfera.\n"
    "Cada video deve ser visualmente UNICO — local diferente, roupa diferente, humor diferente.\n"
    "A unica coisa FIXA e o rosto e a voz da Ana (descricao facial nunca muda).\n\n"
    "REGRA CRITICA — PRESENCA OBRIGATORIA DO PERSONAGEM:\n"
    "Ana DEVE aparecer VISIVEL e FALANDO PARA A CAMERA em TODAS as cenas.\n"
    "NUNCA gere cenas de paisagem, cortes externos, outras pessoas ou cenas sem a Ana.\n"
    "A mensagem do video deve ser DISTRIBUIDA por TODAS as cenas igualmente.\n"
    "NAO concentre o conteudo em poucas cenas — CADA cena tem uma fala propria e unica.\n\n"
    "VARIEDADE DE CAMERA — FUNDAMENTAL para engajamento:\n"
    "Cada cena DEVE ter um angulo de camera DIFERENTE. Varie entre:\n"
    "- 'selfie close-up': rosto proximo, estilo selfie de celular, enquadramento de peito pra cima\n"
    "- 'medium shot': enquadramento da cintura pra cima, mostrando gestos com as maos\n"
    "- 'full body': corpo inteiro visivel, mostrando roupa e postura completa\n"
    "- 'walking towards camera': personagem andando em direcao a camera, dinamico\n"
    "- 'over the shoulder': camera atras do ombro olhando pra frente, depois vira pra camera\n"
    "- 'seated talking': sentada em cadeira/sofa/banco, enquadramento medio\n"
    "NUNCA repita o mesmo angulo em cenas consecutivas. Alterne para manter o video dinamico.\n\n"
    "REGRA CRITICA — CADA CENA E AUTONOMA:\n"
    "A IA que gera os videos processa CADA CENA de forma INDEPENDENTE.\n"
    "Ela NAO tem acesso as outras cenas. Por isso:\n"
    "- NUNCA use 'same as before', 'same outfit', 'same location', 'continues from' etc.\n"
    "- Cada cena DEVE repetir a descricao COMPLETA do cenario, roupa, iluminacao e acao.\n"
    "- Se o cenario e o mesmo em todas as cenas, REPITA a descricao identica em cada cena.\n"
    "- Se a roupa e a mesma, REPITA a descricao identica em cada cena.\n"
    "- Pense em cada cena como um prompt ISOLADO que precisa funcionar sozinho.\n\n"
    "REGRAS DE FORMATO:\n"
    "- Responda SEMPRE em JSON valido, sem markdown, sem explicacoes fora do JSON.\n"
    "- O JSON deve conter: marcadores, cenas, descricao, hashtags.\n"
    "- Os marcadores servem para rastrear o que ja foi usado e evitar repeticao.\n"
)

# ── Montador de prompt Veo3 (agora usa campos do Gemini) ─────────────────────
def _montar_prompt(cena: dict, dialogo: str) -> str:
    """
    Monta o prompt Veo3 usando os campos criativos que o Gemini gerou
    (background, action, camera, lighting) combinados com os blocos fixos de identidade.
    
    IMPORTANTE: Cada cena é gerada independentemente pelo Flow, então TODOS os
    dados do personagem, cenário e roupa devem estar presentes em cada prompt.
    Nunca usar referências como 'same as before' — cada prompt é autônomo.
    """
    d = dialogo.replace('"', "'")

    # Metadados de posição (injetados pelo roteiro_core)
    cena_idx = cena.get("_cena_idx", 1)
    total_cenas = cena.get("_total_cenas", 5)

    # Campos criativos do Gemini (com fallbacks seguros)
    background = cena.get("background", "Background: A vibrant Brazilian urban setting during golden hour.")
    action = cena.get("action", "Ana speaks to camera with energy and gestures.")
    lighting = cena.get("lighting", "Lighting: Warm golden-hour sunlight with natural highlights.")
    outfit = cena.get("outfit", "")
    audio = cena.get("audio", "Background sounds: Subtle ambient noise.\nMusic: None.")
    camera = cena.get("camera", "selfie close-up")

    # Monta outfit como parte do character se fornecido
    char_block = CHARACTER_BLOCK
    if outfit:
        char_block += f"\nOutfit: {outfit}"

    # Gera Subject dinâmico baseado no campo camera
    camera_lower = camera.lower()
    if "full body" in camera_lower:
        subject = (
            "Full body video of a Brazilian fortune teller named Ana speaking directly "
            "to camera. She is standing, her entire body visible from head to toe. "
            "The woman MUST be clearly visible and centered in frame throughout the entire clip."
        )
        framing = (
            "MANDATORY: The character must be fully visible from head to toe, centered in frame. "
            "Her face must be clearly recognizable. Show her full outfit and posture."
        )
    elif "walking" in camera_lower:
        subject = (
            "Dynamic video of a Brazilian fortune teller named Ana walking towards camera "
            "while speaking. She moves with confidence. "
            "The woman MUST be clearly visible throughout the entire clip."
        )
        framing = (
            "MANDATORY: The character must be clearly visible, walking toward the camera. "
            "Her face, body and outfit must be fully shown as she approaches."
        )
    elif "medium" in camera_lower:
        subject = (
            "Medium shot video of a Brazilian fortune teller named Ana speaking to camera. "
            "Framed from waist up, showing her hand gestures. "
            "The woman MUST be visible and centered in frame throughout the entire clip."
        )
        framing = (
            "MANDATORY: The character must be visible from waist up, centered in frame. "
            "Her face and hand gestures must be clearly visible."
        )
    elif "seated" in camera_lower or "sitting" in camera_lower:
        subject = (
            "Video of a Brazilian fortune teller named Ana seated and speaking to camera. "
            "She is sitting comfortably, framed from chest up. "
            "The woman MUST be visible and centered in frame throughout the entire clip."
        )
        framing = (
            "MANDATORY: The character must be seated and clearly visible, centered in frame. "
            "Her face and upper body must occupy most of the frame."
        )
    else:  # selfie close-up (default)
        subject = (
            "Close-up selfie video of a Brazilian fortune teller named Ana speaking directly "
            "to camera. The woman MUST be visible and centered in frame throughout the entire clip."
        )
        framing = (
            "MANDATORY: The character's face and upper body must be clearly visible "
            "and occupy at least 60% of the frame."
        )

    # Nota: NÃO adicionamos instrução de "continuidade" porque cada cena é
    # gerada de forma INDEPENDENTE pela IA. Referências como "same as scene 1"
    # não funcionam. Em vez disso, o character block, outfit e background
    # são repetidos integralmente em cada prompt.

    return (
        f"Subject: {subject}\n\n"
        f"{char_block}\n\n"
        f"Action: {action}\n\n"
        f"{background}\n\n"
        f"{lighting}\n\n"
        f"{STYLE_BLOCK}\n"
        f"\n"
        f"{framing}\n"
        "The character's physical appearance "
        "(face, hair, skin tone, eye color, beauty mark) must be IDENTICAL in every "
        "scene. Never show only scenery.\n"
        "CRITICAL: The character is a YOUNG WOMAN (28 years old). "
        "NEVER generate a male character, an elderly person, a child, or anyone who does not match "
        "the exact description above. If in doubt, prioritize the face description.\n\n"
        "Dialogue rules:\n"
        "- Spoken in Brazilian Portuguese.\n"
        "- Single continuous sentence per scene.\n"
        "- STRICT length: around 20 words per scene (one single sentence).\n"
        "- Natural, easy to speak within an 8-second clip.\n\n"
        f"Dialogue: spoken in Brazilian Portuguese [{VOICE_STYLE}]\n"
        f'"{d}"\n\n'
        f"{audio}\n"
        f"{TECH_BLOCK}"
    )


# ── Validacao de dialogos ─────────────────────────────────────────────────────
def _validar_dialogos(cenas_json: list, **kwargs) -> list[str]:
    avisos = []
    erro_grave = False
    for c in cenas_json:
        dialogo = c.get("dialogo", "") or ""
        n = contar_palavras(dialogo)
        if not (MIN_PALAVRAS <= n <= MAX_PALAVRAS):
            avisos.append(
                f"  Cena {c.get('numero','?')} ({c.get('nome','?')}): "
                f"{n} palavras (esperado {MIN_PALAVRAS}-{MAX_PALAVRAS})"
            )
        if n < MIN_PALAVRAS or n > MAX_PALAVRAS:
            erro_grave = True
    if erro_grave:
        raise ValueError(
            f"Dialogos fora da faixa ({MIN_PALAVRAS}-{MAX_PALAVRAS} palavras)."
        )
    return avisos


# ── Escolha de tema (evita repeticao) ─────────────────────────────────────────
def _escolher_tema(tema: str, historico: list[dict]) -> str:
    if tema != "aleatorio":
        return tema
    temas_fixos = [t for t in TEMAS.keys() if t != "aleatorio"]
    usados = {item.get("tema") for item in historico[-HISTORICO_MAX:]}
    candidatos = [t for t in temas_fixos if t not in usados]
    if candidatos:
        return random.choice(candidatos)
    return random.choice(temas_fixos)


# ── Gerador principal ─────────────────────────────────────────────────────────
def gerar_roteiro(
    tema: str,
    mensagem_central: str,
    signo: str | None,
    n_cenas: int = CENAS_PADRAO,
    historico: list[dict] | None = None,
    fn_gerar_texto=None,
    variar_cenario: bool = False,
    variar_roupa: bool = False,
) -> dict:
    historico = historico or []
    n_cenas = max(2, int(n_cenas))
    tema_escolhido = _escolher_tema(tema, historico)
    signo_label = signo or "Todos os signos"

    # Carrega contexto anti-repeticao dos ultimos 30 videos
    contexto_anti_rep = montar_contexto_anti_repeticao(ID)

    # Estrutura de cenas minima (so define numero, funcao narrativa e objetivo)
    estrutura_cenas = []
    estrutura_cenas.append({
        "numero": 1,
        "nome": "Gancho",
        "objetivo": "Prender atencao IMEDIATA com curiosidade, identificacao ou impacto emocional.",
    })
    for i in range(2, n_cenas):
        estrutura_cenas.append({
            "numero": i,
            "nome": f"Desenvolvimento {i-1}",
            "objetivo": "Aprofundar a mensagem com revelacao, conselho ou transformacao emocional.",
        })
    estrutura_cenas.append({
        "numero": n_cenas,
        "nome": "CTA",
        "objetivo": "Call-to-action energetico pedindo comentario, curtida ou compartilhamento.",
    })

    descricao_cenas = "\n".join(
        [f"Cena {c['numero']} - {c['nome']}: {c['objetivo']}" for c in estrutura_cenas]
    )

    # Monta campos por cena no JSON de exemplo (action e camera são sempre por cena)
    campos_por_cena = '\"camera\": \"selfie close-up ou medium shot ou full body ou walking towards camera ou seated talking\", \"action\": \"descricao da acao/gesto nesta cena especifica\"'
    if variar_cenario:
        campos_por_cena = '"background": "Background: cenario desta cena", ' + campos_por_cena
    if variar_roupa:
        campos_por_cena = '"outfit": "roupa/acessorios desta cena", ' + campos_por_cena

    exemplos_json = ",\n".join(
        [
            f'    {{"numero": {c["numero"]}, "nome": "{c["nome"]}", '
            f'"texto_tela": "TEXTO CURTO", "dialogo": "fala natural de ~20 palavras", '
            f'{campos_por_cena}}}'
            for c in estrutura_cenas
        ]
    )

    # Regra de continuidade dinâmica
    if not variar_cenario and not variar_roupa:
        regra_continuidade = (
            "\u26a0\ufe0f REGRA CRITICA DE CONTINUIDADE:\n"
            f"O video e UMA SEQUENCIA CONTINUA de {n_cenas} cenas.\n"
            "TODAS as cenas acontecem NO MESMO LOCAL, com a MESMA ROUPA, MESMA ILUMINACAO.\n"
            "O cenario, a roupa e a luz sao GLOBAIS (definidos UMA VEZ no JSON raiz).\n"
            "Cada cena so varia: a FALA (dialogo) e o GESTO/ACAO sutil.\n"
            "A camera fica na MESMA POSICAO \u2014 e um video selfie continuo.\n"
            "Imagine que e UMA UNICA GRAVACAO dividida em partes.\n\n"
        )
    else:
        partes_variaveis = []
        if variar_cenario:
            partes_variaveis.append("CENARIO DIFERENTE em cada cena")
        if variar_roupa:
            partes_variaveis.append("ROUPA DIFERENTE em cada cena")
        partes_fixas = []
        if not variar_cenario:
            partes_fixas.append("MESMO CENARIO")
        if not variar_roupa:
            partes_fixas.append("MESMA ROUPA")
        regra_continuidade = (
            f"\u26a0\ufe0f REGRA DE VARIACAO VISUAL:\n"
            f"O video tem {n_cenas} cenas com {', '.join(partes_variaveis)}.\n"
        )
        if partes_fixas:
            regra_continuidade += f"MANTER: {', '.join(partes_fixas)} em todas as cenas.\n"
        regra_continuidade += (
            "Cada cena tem sua propria fala COMPLETA (nao corta entre cenas).\n"
            "A iluminacao e o audio sao GLOBAIS (definidos UMA VEZ no JSON raiz).\n\n"
        )

    # Instruções de campos por escopo (global vs por cena)
    campos_instrucao = ""
    campos_json_global = ""
    bg_label = "(GLOBAL)" if not variar_cenario else "(POR CENA)"
    outfit_label = "(GLOBAL)" if not variar_roupa else "(POR CENA)"
    campos_instrucao += f"7. background {bg_label}: descricao detalhada em ingles do cenario para Veo3\n"
    campos_instrucao += f"8. outfit {outfit_label}: descricao da roupa/acessorios em ingles\n"
    campos_instrucao += "9. lighting (GLOBAL): descricao da iluminacao em ingles\n"
    campos_instrucao += "10. audio (GLOBAL): sons ambientes em ingles (sem musica)\n"
    campos_instrucao += "11. camera (POR CENA): angulo de camera — VARIE entre: 'selfie close-up', 'medium shot', 'full body', 'walking towards camera', 'seated talking'. NUNCA repita o mesmo em cenas consecutivas.\n"
    campos_instrucao += "12. action (POR CENA): gesto/movimento que COMBINA com o angulo de camera escolhido\n\n"

    # Campos globais no JSON raiz
    if not variar_cenario:
        campos_json_global += '  "background": "Background: descricao UNICA do cenario em ingles para TODAS as cenas",\n'
    if not variar_roupa:
        campos_json_global += '  "outfit": "descricao UNICA da roupa em ingles para TODAS as cenas",\n'
    campos_json_global += '  "lighting": "Lighting: descricao UNICA da iluminacao em ingles",\n'
    campos_json_global += '  "audio": "Background sounds: sons ambientes\\nMusic: None.",\n'

    mensagem_usuario = (
        f"Crie um roteiro de {n_cenas} cenas para Ana Cartomante:\n"
        f"- Signo: {signo_label}\n"
        f"- Tema: {tema_escolhido}\n"
        f"- Mensagem central: {mensagem_central}\n\n"
        "VOCE TEM LIBERDADE CRIATIVA para escolher:\n"
        "- CENARIO: local realista e cinematografico, mas que mantenha a Ana como FOCO PRINCIPAL. "
        "Exemplos: quarto, sala, varanda, jardim, cafe, feira, praia, escritorio, sacada, parque, rua. "
        "O cenario pode ser interno ou externo, mas NUNCA deve competir visualmente com o personagem. "
        "NUNCA use paisagens grandiosas ou panoramicas (deserto, montanha, salar, planalto aberto).\n"
        "- ROUPA: qualquer roupa realista que combine com o cenario\n"
        "- ILUMINACAO: qualquer condicao de luz que crie atmosfera\n"
        "- TOM: qualquer tom emocional que faca sentido para a mensagem\n\n"
        "A UNICA COISA FIXA e o rosto da Ana (descricao facial). Todo o resto voce inventa.\n\n"
        f"{regra_continuidade}"
        "REGRAS OBRIGATORIAS:\n"
        f"1. Gere EXATAMENTE {n_cenas} cenas\n"
        "2. Cena 1 DEVE ser um GANCHO forte (pergunta, revelacao, alerta, misterio)\n"
        f"3. Cena {n_cenas} DEVE ser um CTA claro pedindo comentario/interacao\n"
        "4. Cada dialogo DEVE ter entre 15 e 25 palavras (audio de 8 segundos)\n"
        "5. Cada fala COMPLETA na propria cena (nao corta entre cenas)\n"
        "6. texto_tela: max 5 palavras + 1 emoji, MAIUSCULAS\n"
        f"{campos_instrucao}"
        f"{contexto_anti_rep}\n"
        "MARCADORES OBRIGATORIOS:\n"
        "Inclua um objeto 'marcadores' no JSON com estas chaves:\n"
        "- cenario: descricao curta do local escolhido (em portugues)\n"
        "- variacao_roupa: o que a Ana esta vestindo de diferente (em portugues)\n"
        "- clima_visual: atmosfera/humor visual do video (em portugues)\n"
        "- tom_emocional: tom da mensagem (em portugues)\n"
        "- tema_central: tema central da mensagem (em portugues)\n"
        "- tipo_gancho: tipo de gancho usado na cena 1 (em portugues)\n"
        "- metafora_principal: metafora ou imagem principal usada (em portugues)\n\n"
        "ESTRUTURA DAS CENAS:\n"
        f"{descricao_cenas}\n\n"
        "Retorne EXATAMENTE este JSON (sem markdown):\n"
        "{\n"
        '  "marcadores": {\n'
        '    "cenario": "...", "variacao_roupa": "...", "clima_visual": "...",\n'
        '    "tom_emocional": "...", "tema_central": "...",\n'
        '    "tipo_gancho": "...", "metafora_principal": "..."\n'
        "  },\n"
        f"{campos_json_global}"
        '  "cenas": [\n'
        f"{exemplos_json}\n"
        "  ],\n"
        '  "descricao": "caption do video em max 2 frases",\n'
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
        validar_dialogos=lambda cenas_json: _validar_dialogos(cenas_json),
        min_palavras=MIN_PALAVRAS,
        max_palavras=MAX_PALAVRAS,
        fn_gerar_texto=fn_gerar_texto,
    )

    # Registra no historico individual da persona
    marcadores = resultado.get("marcadores", {})
    cenas = resultado.get("cenas", [])
    dialogos = [c.get("dialogo", "") for c in cenas if c.get("dialogo")]

    registrar_video(
        persona_id=ID,
        tema=tema_escolhido,
        signo=signo_label,
        marcadores=marcadores,
        dialogos=dialogos,
        descricao=resultado.get("descricao", ""),
        hashtags=resultado.get("hashtags", []),
    )

    resultado["tema_efetivo"] = tema_escolhido
    resultado["signo_efetivo"] = signo_label
    return resultado