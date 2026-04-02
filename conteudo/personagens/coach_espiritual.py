"""
Perfil fixo e completo do personagem Coach Espiritual.
Todos os blocos técnicos do prompt Veo 3 estão aqui centralizados.
Nunca altere este arquivo durante a geração — apenas entre roteiros.
"""

NOME = "Coach Espiritual"
DESCRICAO_CURTA = "Coach Espiritual — mensagens de superação, amor, fé e Deus"

# ── Blocos fixos do prompt Veo 3 ────────────────────────────────────────────

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
    "Background sounds: Very subtle household ambience, faint room tone. "
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

# ── Estrutura das 3 cenas ────────────────────────────────────────────────────
# Cada cena define os campos fixos (ação, tom, objetivo).
# O Gemini preenche apenas: dialogo e texto_tela.

ESTRUTURA_CENAS = [
    {
        "numero": 1,
        "nome": "O Peso da Manhã",
        "subject_suffix": "delivering a compassionate opening reflection.",
        "action": (
            "The coach stands still in the kitchen, holding a mug with both hands at chest level. "
            "He takes a slow deep breath, briefly lowers his eyes as if feeling the weight of the day, "
            "and then looks directly into the camera with empathy."
        ),
        "tone": "gentle and understanding tone",
        "objetivo": (
            "Hook inicial que reconhece o peso emocional de alguns dias, fazendo o espectador se sentir "
            "visto e compreendido logo de cara."
        ),
    },
    {
        "numero": 2,
        "nome": "Um Dia de Cada Vez",
        "subject_suffix": "sharing a faith-centered reassurance.",
        "action": (
            "The coach is now near the table with an open Bible beside the coffee cup. "
            "He gently touches the open page with one hand, nods with peaceful certainty, "
            "and then looks at the camera com olhar firme e acolhedor."
        ),
        "tone": "reassuring and spiritual tone",
        "objetivo": (
            "Mostrar que Deus não exige que tudo seja resolvido de uma vez, reforçando a ideia de "
            "caminhar com fé, um dia de cada vez."
        ),
    },
    {
        "numero": 3,
        "nome": "Respira e Entrega",
        "subject_suffix": "delivering an encouraging call to surrender to God.",
        "action": (
            "The coach smiles softly, places one hand on his chest, then slowly gestures forward "
            "como se convidasse o espectador a seguir em paz. O ambiente está um pouco mais claro, "
            "transmitindo sensação de alívio e esperança."
        ),
        "tone": "encouraging and hopeful tone",
        "objetivo": (
            "Convidar o espectador a respirar fundo, entregar o peso nas mãos de Deus e interagir "
            "com a mensagem, fortalecendo a fé e o engajamento."
        ),
    },
]