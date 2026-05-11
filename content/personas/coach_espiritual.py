"""
Persona: Coach Espiritual
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
ID = "CoachEspiritual"
NOME = "Coach Espiritual"
CENAS_PADRAO = 3
USA_SIGNOS = False
SIGNOS: list[str] = []
TEMA_PADRAO = "aleatorio"

HISTORICO_MAX = 100
MIN_PALAVRAS = 15
MAX_PALAVRAS = 25

# ── Temas ─────────────────────────────────────────────────────────────────────
TEMAS = {
    "superacao": "superar a dor com fe, coragem e presenca de Deus",
    "amor": "curar o coracao e aprender a amar com paz e proposito",
    "fe": "fortalecer a fe mesmo em dias dificeis e silenciosos",
    "deus": "confiar em Deus e descansar no tempo dEle",
    "salmos": "buscar forca, consolo e direcao espiritual atraves dos salmos",
    "aleatorio": None,
}


def tema_exige_signo(tema: str) -> bool:
    return False


def fallback_mensagem(tema: str) -> str:
    return f"mensagem espiritual, acolhedora e poderosa sobre {tema}"


# ── Blocos FIXOS (identidade — nao muda) ─────────────────────────────────────
CHARACTER_BLOCK = (
    "Character: Serene Brazilian life coach, around 42 years old, composed presence. "
    "Face: calm steady eyes, soft features, short neatly styled gray hair, "
    "salt-and-pepper beard, gentle and empathetic expression."
)

VOICE_STYLE = (
    "Voice: calm Brazilian male voice, warm and empathetic, speaking with a soothing, "
    "spiritual and encouraging tone."
)

STYLE_BLOCK = (
    "Style: Hyper-realistic cinematic video, 9:16 vertical, minimal camera movement, "
    "framed chest-up, focusing on subtle emotional expressions and eye contact."
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
    "Voce e um diretor criativo especialista em videos virais de conteudo espiritual e motivacional.\n"
    "Voce cria roteiros para o Coach Espiritual: um homem sereno, sabio, que fala sobre Deus, "
    "fe, superacao e amor com profundidade e acolhimento.\n"
    "Voce tem LIBERDADE TOTAL para escolher cenarios, roupas, acoes e atmosfera.\n"
    "Cada video deve ser visualmente UNICO — local diferente, roupa diferente, momento do dia diferente.\n"
    "A unica coisa FIXA e o rosto e a voz do Coach (descricao facial nunca muda).\n"
    "Ele pode estar em casa, na rua, em um parque, em uma igreja, em um cafe — VOCE DECIDE.\n\n"
    "REGRA CRITICA — PRESENCA OBRIGATORIA DO PERSONAGEM:\n"
    "O Coach DEVE aparecer VISIVEL e FALANDO PARA A CAMERA em TODAS as cenas.\n"
    "NUNCA gere cenas de paisagem, cortes externos, outras pessoas ou cenas sem o Coach.\n"
    "A mensagem do video deve ser DISTRIBUIDA por TODAS as cenas igualmente.\n"
    "NAO concentre o conteudo em poucas cenas — CADA cena tem uma fala propria e unica.\n\n"
    "VARIEDADE DE CAMERA — FUNDAMENTAL para engajamento:\n"
    "Cada cena DEVE ter um angulo de camera DIFERENTE. Varie entre:\n"
    "- 'selfie close-up': rosto proximo, estilo selfie de celular\n"
    "- 'medium shot': enquadramento da cintura pra cima, mostrando gestos\n"
    "- 'full body': corpo inteiro visivel, mostrando postura completa\n"
    "- 'walking towards camera': personagem andando em direcao a camera\n"
    "- 'seated talking': sentado falando, enquadramento medio\n"
    "NUNCA repita o mesmo angulo em cenas consecutivas.\n\n"
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
)

# ── Montador de prompt Veo3 ───────────────────────────────────────────────────
def _montar_prompt(cena: dict, dialogo: str) -> str:
    d = dialogo.replace('"', "'")

    cena_idx = cena.get("_cena_idx", 1)
    total_cenas = cena.get("_total_cenas", 3)

    background = cena.get("background", "Background: A quiet, peaceful indoor setting with warm morning light.")
    action = cena.get("action", "The coach speaks calmly, looking directly at the camera.")
    lighting = cena.get("lighting", "Lighting: Soft warm light creating a peaceful atmosphere.")
    outfit = cena.get("outfit", "")
    audio = cena.get("audio", "Background sounds: Very subtle ambient noise.\nMusic: None.")
    camera = cena.get("camera", "selfie close-up")

    char_block = CHARACTER_BLOCK
    if outfit:
        char_block += f"\nOutfit: {outfit}"

    # Subject dinâmico baseado no campo camera
    camera_lower = camera.lower()
    if "full body" in camera_lower:
        subject = (
            "Full body video of a serene Brazilian spiritual life coach speaking directly "
            "to camera. He is standing, his entire body visible. "
            "The man MUST be clearly visible and centered in frame throughout the entire clip."
        )
        framing = (
            "MANDATORY: The character must be fully visible from head to toe, centered in frame. "
            "His face must be clearly recognizable."
        )
    elif "walking" in camera_lower:
        subject = (
            "Dynamic video of a serene Brazilian spiritual life coach walking towards camera "
            "while speaking calmly. "
            "The man MUST be clearly visible throughout the entire clip."
        )
        framing = (
            "MANDATORY: The character must be clearly visible, walking toward the camera. "
            "His face, body and outfit must be fully shown."
        )
    elif "medium" in camera_lower:
        subject = (
            "Medium shot video of a serene Brazilian spiritual life coach speaking to camera. "
            "Framed from waist up, showing his hand gestures. "
            "The man MUST be visible and centered in frame throughout the entire clip."
        )
        framing = (
            "MANDATORY: The character must be visible from waist up, centered in frame. "
            "His face and hand gestures must be clearly visible."
        )
    elif "seated" in camera_lower or "sitting" in camera_lower:
        subject = (
            "Video of a serene Brazilian spiritual life coach seated and speaking to camera. "
            "He is sitting comfortably, framed from chest up. "
            "The man MUST be visible and centered in frame throughout the entire clip."
        )
        framing = (
            "MANDATORY: The character must be seated and clearly visible, centered in frame. "
            "His face and upper body must occupy most of the frame."
        )
    else:
        subject = (
            "Close-up selfie video of a serene Brazilian spiritual life coach speaking directly "
            "to camera. The man MUST be visible and centered in frame throughout the entire clip."
        )
        framing = (
            "MANDATORY: The character's face and upper body must be clearly visible "
            "and occupy at least 60% of the frame."
        )

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
        "(face, hair, skin tone, eye color) must be IDENTICAL in every "
        "scene. Never show only scenery.\n"
        "CRITICAL: The character is a MAN (around 35 years old). "
        "NEVER generate a female character, an elderly person, a child, or anyone who does not match "
        "the exact description above. If in doubt, prioritize the face description.\n\n"
        "Dialogue rules:\n"
        "- Spoken in Brazilian Portuguese.\n"
        "- Single continuous sentence per scene.\n"
        "- STRICT length: around 20 words per scene.\n"
        "- Natural, calm, easy to speak within an 8-second clip.\n\n"
        f"Dialogue: spoken in Brazilian Portuguese [{VOICE_STYLE}]\n"
        f'"{d}"\n\n'
        f"{audio}\n"
        f"{TECH_BLOCK}"
    )


# ── Validacao ─────────────────────────────────────────────────────────────────
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
        raise ValueError(f"Dialogos fora da faixa ({MIN_PALAVRAS}-{MAX_PALAVRAS} palavras).")
    return avisos


def _escolher_tema(tema: str, historico: list[dict]) -> str:
    if tema != "aleatorio":
        return tema
    temas_fixos = [t for t in TEMAS.keys() if t != "aleatorio"]
    usados = {item.get("tema") for item in historico[-HISTORICO_MAX:]}
    candidatos = [t for t in temas_fixos if t not in usados]
    return random.choice(candidatos) if candidatos else random.choice(temas_fixos)


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

    contexto_anti_rep = montar_contexto_anti_repeticao(ID)

    estrutura_cenas = []
    estrutura_cenas.append({
        "numero": 1, "nome": "Gancho",
        "objetivo": "Reconhecer a dor, o cansaco ou o peso emocional do espectador de forma imediata e acolhedora.",
    })
    for i in range(2, n_cenas):
        estrutura_cenas.append({
            "numero": i, "nome": f"Reflexao {i-1}",
            "objetivo": "Aprofundar com verdade biblica, perspectiva em Deus ou conselho espiritual pratico.",
        })
    estrutura_cenas.append({
        "numero": n_cenas, "nome": "CTA",
        "objetivo": "Fechar com CTA pedindo comentario, 'Amem' ou compartilhamento.",
    })

    descricao_cenas = "\n".join(
        [f"Cena {c['numero']} - {c['nome']}: {c['objetivo']}" for c in estrutura_cenas]
    )

    campos_por_cena = '"camera": "selfie close-up ou medium shot ou full body ou walking towards camera ou seated talking", "action": "descricao da acao/gesto nesta cena especifica"'
    if variar_cenario:
        campos_por_cena = '"background": "Background: cenario desta cena", ' + campos_por_cena
    if variar_roupa:
        campos_por_cena = '"outfit": "roupa desta cena", ' + campos_por_cena

    exemplos_json = ",\n".join([
        f'    {{"numero": {c["numero"]}, "nome": "{c["nome"]}", '
        f'"texto_tela": "TEXTO CURTO", "dialogo": "fala natural de ~20 palavras", '
        f'{campos_por_cena}}}'
        for c in estrutura_cenas
    ])

    # Regra de continuidade dinâmica
    if not variar_cenario and not variar_roupa:
        regra_cont = (
            "\u26a0\ufe0f REGRA CRITICA DE CONTINUIDADE:\n"
            f"O video e UMA SEQUENCIA CONTINUA de {n_cenas} cenas.\n"
            "TODAS as cenas: MESMO LOCAL, MESMA ROUPA, MESMA ILUMINACAO.\n"
            "Campos visuais sao GLOBAIS (JSON raiz). So varia: FALA e GESTO.\n"
            "A CAMERA deve variar de angulo entre as cenas para manter o video dinamico.\n\n"
        )
    else:
        partes = []
        if variar_cenario: partes.append("CENARIO DIFERENTE")
        if variar_roupa: partes.append("ROUPA DIFERENTE")
        regra_cont = f"\u26a0\ufe0f VARIACAO: {', '.join(partes)} em cada cena.\n"
        if not variar_cenario: regra_cont += "MANTER: MESMO CENARIO.\n"
        if not variar_roupa: regra_cont += "MANTER: MESMA ROUPA.\n"
        regra_cont += "Iluminacao e audio sao GLOBAIS. Cada fala COMPLETA na cena.\n\n"

    bg_l = "(GLOBAL)" if not variar_cenario else "(POR CENA)"
    out_l = "(GLOBAL)" if not variar_roupa else "(POR CENA)"
    campos_instr = (
        f"7. background {bg_l}: cenario em INGLES\n"
        f"8. outfit {out_l}: roupa em INGLES\n"
        "9. lighting (GLOBAL): iluminacao em INGLES\n"
        "10. audio (GLOBAL): sons ambientes em INGLES\n"
        "11. camera (POR CENA): angulo de camera — VARIE entre: 'selfie close-up', 'medium shot', 'full body', 'walking towards camera', 'seated talking'. NUNCA repita em cenas consecutivas.\n"
        "12. action (POR CENA): gesto/movimento que COMBINA com o angulo escolhido\n\n"
    )
    campos_global = ""
    if not variar_cenario: campos_global += '"background": "Background: cenario UNICO", '
    if not variar_roupa: campos_global += '"outfit": "roupa UNICA", '
    campos_global += '"lighting": "Lighting: iluminacao UNICA", "audio": "Background sounds: sons\\nMusic: None.", '

    mensagem_usuario = (
        f"Crie um roteiro de {n_cenas} cenas para o Coach Espiritual:\n"
        f"- Tema: {tema_escolhido}\n"
        f"- Mensagem central: {mensagem_central}\n\n"
        "VOCE TEM LIBERDADE CRIATIVA para escolher:\n"
        "- CENARIO: local INTIMO e PROXIMO — casa, sala, escritorio, igreja por dentro, varanda, jardim, "
        "cafe, banco de praca, trilha no parque (de perto). "
        "NUNCA use paisagens grandiosas ou panoramicas. "
        "O cenario DEVE funcionar como FUNDO de um video SELFIE — PROXIMO e DESFOCADO atras dele.\n"
        "- ROUPA: qualquer roupa realista que combine\n"
        "- ILUMINACAO: qualquer condicao de luz\n"
        "- TOM: qualquer tom emocional\n\n"
        "A UNICA COISA FIXA e o rosto do Coach.\n\n"
        f"{regra_cont}"
        "REGRAS OBRIGATORIAS:\n"
        f"1. Gere EXATAMENTE {n_cenas} cenas\n"
        "2. Cena 1 = GANCHO que reconhece a dor do espectador\n"
        f"3. Cena {n_cenas} = CTA pedindo 'Amem', comentario ou compartilhamento\n"
        "4. Cada dialogo: 15-25 palavras (audio de 8 segundos)\n"
        "5. Cada fala COMPLETA na propria cena\n"
        "6. texto_tela: max 5 palavras + 1 emoji, MAIUSCULAS\n"
        f"{campos_instr}"
        f"{contexto_anti_rep}\n"
        "MARCADORES OBRIGATORIOS:\n"
        "Inclua 'marcadores' no JSON com:\n"
        "- cenario, variacao_roupa, clima_visual, tom_emocional,\n"
        "  tema_central, tipo_gancho, metafora_principal (em portugues)\n\n"
        f"ESTRUTURA:\n{descricao_cenas}\n\n"
        "Retorne JSON:\n"
        '{"marcadores": {...}, '
        f'{campos_global}'
        '"cenas": [\n'
        f"{exemplos_json}\n"
        '], "descricao": "caption", "hashtags": ["#tag1"]}\n'
    )

    print(f"\n[ROTEIRO] Gerando roteiro — Coach | Tema: {tema_escolhido} | Cenas: {n_cenas}")

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

    marcadores = resultado.get("marcadores", {})
    cenas = resultado.get("cenas", [])
    dialogos = [c.get("dialogo", "") for c in cenas if c.get("dialogo")]

    registrar_video(
        persona_id=ID, tema=tema_escolhido, signo="",
        marcadores=marcadores, dialogos=dialogos,
        descricao=resultado.get("descricao", ""),
        hashtags=resultado.get("hashtags", []),
    )

    resultado["tema_efetivo"] = tema_escolhido
    return resultado