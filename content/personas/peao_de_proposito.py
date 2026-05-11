"""
Persona: Peao de Proposito
Identidade fixa (rosto/voz) + liberdade criativa total para cenarios, roupas e acoes.
Roteiros focados em fe, salmos, motivacao e superacao em contexto rural.
"""

import random

from content.roteiro_core import gerar_roteiro_generico, contar_palavras
from content.historico_persona import (
    montar_contexto_anti_repeticao,
    registrar_video,
)

# ── Identidade ────────────────────────────────────────────────────────────────
ID = "PeaoDeProposito"
NOME = "Peao de Proposito"
CENAS_PADRAO = 3
USA_SIGNOS = False
SIGNOS: list[str] = []
TEMA_PADRAO = "aleatorio"

HISTORICO_MAX = 100
MIN_PALAVRAS = 15
MAX_PALAVRAS = 25

# ── Temas ─────────────────────────────────────────────────────────────────────
TEMAS = {
    "fe": "mensagens de fe e confianca em Deus no meio da rotina do campo",
    "salmos": "reflexoes e consolo baseados em salmos e textos biblicos",
    "superacao": "motivacao para quem esta cansado, lutando e quase desistindo",
    "trabalho": "o valor do trabalho honesto e a dignidade de quem luta todo dia",
    "aleatorio": None,
}


def tema_exige_signo(tema: str) -> bool:
    return False


def fallback_mensagem(tema: str) -> str:
    return f"mensagem de fe, salmos e superacao ({tema})"


# ── Blocos FIXOS (identidade — nao muda) ─────────────────────────────────────
CHARACTER_BLOCK = (
    "Character: Handsome 30-year-old Brazilian farmer, strong masculine presence, "
    "natural athletic build from hard farm work, square jaw, sun-kissed tanned skin. "
    "Short rugged stubble beard, deep light-brown eyes, and a subtle, knowing but "
    "welcoming half-smile."
)

VOICE_STYLE = (
    "Voice: deep Brazilian male voice, calm and gentle, with rural accent, "
    "speaking with spiritual, encouraging and peaceful tone."
)

STYLE_BLOCK = (
    "Style: Hyper-realistic cinematic video, 9:16 vertical, minimal camera movement, "
    "framed waist-up or chest-up, focusing on emotional expressions and eye contact."
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
    "Voce e um diretor criativo especialista em videos virais de fe, motivacao e superacao.\n"
    "Voce cria roteiros para o Peao de Proposito: um fazendeiro brasileiro de 30 anos, bonito, "
    "forte, marcado pelo trabalho no campo, que fala de Deus, salmos e fe com profundidade.\n"
    "Voce tem LIBERDADE TOTAL para escolher cenarios, roupas, acoes e atmosfera.\n"
    "Cada video deve ser visualmente UNICO — local diferente, roupa diferente, atividade diferente.\n"
    "A unica coisa FIXA e o rosto e a voz do Peao (descricao facial nunca muda).\n"
    "Ele pode estar na fazenda, no pasto, na estrada de terra, no curral, na horta, "
    "montado a cavalo, junto ao gado, na varanda da sede — VOCE DECIDE.\n\n"
    "REGRA CRITICA — PRESENCA OBRIGATORIA DO PERSONAGEM:\n"
    "O Peao DEVE aparecer VISIVEL e FALANDO PARA A CAMERA em TODAS as cenas.\n"
    "NUNCA gere cenas de paisagem, cortes externos, outras pessoas ou cenas sem o Peao.\n"
    "A mensagem do video deve ser DISTRIBUIDA por TODAS as cenas igualmente.\n"
    "NAO concentre o conteudo em poucas cenas — CADA cena tem uma fala propria e unica.\n\n"
    "VARIEDADE DE CAMERA — FUNDAMENTAL para engajamento:\n"
    "Cada cena DEVE ter um angulo de camera DIFERENTE. Varie entre:\n"
    "- 'selfie close-up': rosto proximo, estilo selfie de celular\n"
    "- 'medium shot': enquadramento da cintura pra cima, mostrando gestos\n"
    "- 'full body': corpo inteiro visivel, mostrando a roupa rural completa\n"
    "- 'walking towards camera': personagem andando na fazenda em direcao a camera\n"
    "- 'seated talking': sentado num banco/cerca, enquadramento medio\n"
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

    background = cena.get("background", "Background: A real Brazilian farm at sunrise with green pasture and wooden fences.")
    action = cena.get("action", "The farmer looks at the camera with a serene and understanding gaze.")
    lighting = cena.get("lighting", "Lighting: Natural warm sunlight creating soft highlights.")
    outfit = cena.get("outfit", "")
    audio = cena.get("audio", "Background sounds: Subtle rural ambience, distant birds, soft wind.\nMusic: None.")
    camera = cena.get("camera", "selfie close-up")

    char_block = CHARACTER_BLOCK
    if outfit:
        char_block += f"\nOutfit: {outfit}"

    # Subject dinâmico baseado no campo camera
    camera_lower = camera.lower()
    if "full body" in camera_lower:
        subject = (
            "Full body video of a handsome Brazilian farmer speaking directly "
            "to camera. He is standing, his entire body visible. "
            "The man MUST be clearly visible and centered in frame throughout the entire clip."
        )
        framing = (
            "MANDATORY: The character must be fully visible from head to toe, centered in frame. "
            "His face must be clearly recognizable. Show his full outfit and posture."
        )
    elif "walking" in camera_lower:
        subject = (
            "Dynamic video of a handsome Brazilian farmer walking through the farm towards camera "
            "while speaking with faith and strength. "
            "The man MUST be clearly visible throughout the entire clip."
        )
        framing = (
            "MANDATORY: The character must be clearly visible, walking toward the camera. "
            "His face, body and outfit must be fully shown."
        )
    elif "medium" in camera_lower:
        subject = (
            "Medium shot video of a handsome Brazilian farmer speaking to camera. "
            "Framed from waist up, showing his expressive hand gestures. "
            "The man MUST be visible and centered in frame throughout the entire clip."
        )
        framing = (
            "MANDATORY: The character must be visible from waist up, centered in frame. "
            "His face and hand gestures must be clearly visible."
        )
    elif "seated" in camera_lower or "sitting" in camera_lower:
        subject = (
            "Video of a handsome Brazilian farmer seated on a fence/bench speaking to camera. "
            "He is sitting naturally, framed from chest up. "
            "The man MUST be visible and centered in frame throughout the entire clip."
        )
        framing = (
            "MANDATORY: The character must be seated and clearly visible, centered in frame. "
            "His face and upper body must occupy most of the frame."
        )
    else:
        subject = (
            "Close-up selfie video of a handsome Brazilian farmer speaking directly "
            "to camera with faith and strength. The man MUST be visible and centered "
            "in frame throughout the entire clip."
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
        "(face, hair, skin tone, eye color, beard) must be IDENTICAL in every "
        "scene. Never show only scenery.\n"
        "CRITICAL: The character is a MAN (around 32 years old). "
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
        "objetivo": "Reconhecer o peso, a luta e o cansaco de quem esta plantando no silencio.",
    })
    for i in range(2, n_cenas):
        estrutura_cenas.append({
            "numero": i, "nome": f"Palavra {i-1}",
            "objetivo": "Trazer verdade biblica, forca espiritual ou reflexao profunda sobre fe e colheita.",
        })
    estrutura_cenas.append({
        "numero": n_cenas, "nome": "CTA",
        "objetivo": "Declaracao de fe forte + CTA pedindo 'Amem', comentario ou compartilhamento.",
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

    if not variar_cenario and not variar_roupa:
        regra_cont = (
            "\u26a0\ufe0f REGRA CRITICA DE CONTINUIDADE:\n"
            f"Video SEQUENCIA CONTINUA de {n_cenas} cenas.\n"
            "MESMO LOCAL, MESMA ROUPA, MESMA ILUMINACAO.\n"
            "Campos visuais GLOBAIS (JSON raiz). So varia: FALA e GESTO.\n\n"
        )
    else:
        partes = []
        if variar_cenario: partes.append("CENARIO DIFERENTE")
        if variar_roupa: partes.append("ROUPA DIFERENTE")
        regra_cont = f"\u26a0\ufe0f VARIACAO: {', '.join(partes)} em cada cena.\n"
        if not variar_cenario: regra_cont += "MANTER: MESMO CENARIO.\n"
        if not variar_roupa: regra_cont += "MANTER: MESMA ROUPA.\n"
        regra_cont += "Iluminacao e audio GLOBAIS. Cada fala COMPLETA na cena.\n\n"

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
        f"Crie um roteiro de {n_cenas} cenas para o Peao de Proposito:\n"
        f"- Tema: {tema_escolhido}\n"
        f"- Mensagem central: {mensagem_central}\n\n"
        "VOCE TEM LIBERDADE CRIATIVA para escolher:\n"
        "- CENARIO: local rural INTIMO e PROXIMO — varanda da sede, porteira, curral de perto, "
        "baia do cavalo, horta, mesa da cozinha da fazenda, galpao, beirada do rio (de perto). "
        "NUNCA use paisagens panoramicas de campo aberto. "
        "O cenario DEVE funcionar como FUNDO de SELFIE — PROXIMO e DESFOCADO atras dele.\n"
        "- ROUPA: qualquer roupa rural realista que combine\n"
        "- ILUMINACAO: qualquer condicao de luz natural\n"
        "- TOM: firme, gentil, profundo, esperancoso, reflexivo\n\n"
        "A UNICA COISA FIXA e o rosto do Peao.\n\n"
        f"{regra_cont}"
        "REGRAS OBRIGATORIAS:\n"
        f"1. EXATAMENTE {n_cenas} cenas\n"
        "2. Cena 1 = GANCHO reconhecendo a luta/dor do espectador\n"
        f"3. Cena {n_cenas} = CTA pedindo 'Amem', comentario ou compartilhamento\n"
        "4. Cada dialogo: 15-25 palavras\n"
        "5. Cada fala COMPLETA na propria cena\n"
        "6. texto_tela: max 5 palavras + 1 emoji, MAIUSCULAS\n"
        f"{campos_instr}"
        f"{contexto_anti_rep}\n"
        "MARCADORES OBRIGATORIOS (em portugues):\n"
        "cenario, variacao_roupa, clima_visual, tom_emocional,\n"
        "tema_central, tipo_gancho, metafora_principal\n\n"
        f"ESTRUTURA:\n{descricao_cenas}\n\n"
        "Retorne JSON:\n"
        '{"marcadores": {...}, '
        f'{campos_global}'
        '"cenas": [\n'
        f"{exemplos_json}\n"
        '], "descricao": "caption", "hashtags": ["#tag1"]}\n'
    )

    print(f"\n[ROTEIRO] Gerando roteiro — Peao | Tema: {tema_escolhido} | Cenas: {n_cenas}")

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