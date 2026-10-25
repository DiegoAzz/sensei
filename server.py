#!/usr/bin/env python3
"""
TikTok Live - Sensei del Amor y la Seducción (VPS / Coolify Headless Streaming)
Transmisión en vivo 24/7 sin OBS: Escucha preguntas de seducción, conquista,
parejas e infidelidades en TikTok, genera sabiduría con IA y responde con voz neuronal en tiempo real.
"""

import os
import sys
import json
import asyncio
import logging
import subprocess
import base64
from pathlib import Path
from aiohttp import web

from agent_manager import (
    agent_manager,
    verify_admin_password,
    create_admin_session,
    verify_session_token,
    change_admin_password,
    AGENT_TEMPLATES
)
from perfumes_expert import obtener_sommelier_experto

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("SenseiSeduccion")

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
CONFIG_FILE = DATA_DIR / "config.json"

DEFAULT_GEMINI_KEY_B64 = "QVEuQWI4Uk42S3dkNEstcl9ycGZfR3FkY2x0VHh4b1NMWE42LVkyYUhCZ0lXY2d6LTZfb1E="
DEFAULT_OPENAI_KEY_B64 = "c2stcHJvai1UMS1icEoxa3hieUhBTXl4QkNMdkdKdUpPMkVVczZmQ3dTMmtEQVhTd2NpYm1admFZb2ZQNzdXUEwzaFpTQ0tsVWpZVTRMMURKdFQzQmxia0ZKajlkR3VuZ1hCZm1TZTdEeWhZeVFwWW5SZ2I1WnRCOUVGb3g5YzU2cmRpcFQ3YmJQZG1LT1RlajZmQU5OSDcxd2IyNEZmVGNCZ0E="

def obtener_ai_key_default():
    env_k = os.environ.get("GEMINI_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if env_k:
        return env_k.strip()
    try:
        return base64.b64decode(DEFAULT_GEMINI_KEY_B64).decode("utf-8").strip()
    except Exception:
        pass
    try:
        return base64.b64decode(DEFAULT_OPENAI_KEY_B64).decode("utf-8").strip()
    except Exception:
        return ""

def obtener_gemini_key_default():
    return obtener_ai_key_default()

# Estado del sistema
estado = {
    "is_streaming": False,
    "tiktok_username": os.environ.get("TIKTOK_USERNAME", ""),
    "rtmp_url": os.environ.get("TIKTOK_RTMP_URL", ""),
    "stream_key": os.environ.get("TIKTOK_STREAM_KEY", ""),
    "voice": os.environ.get("VOICE", "es-MX-JorgeNeural"),
    "gemini_api_key": os.environ.get("GEMINI_API_KEY", "") or obtener_gemini_key_default(),
    "agent_name": os.environ.get("AGENT_NAME", "Sensei del Amor y la Seducción"),
    "estilo": os.environ.get("ESTILO_CONSEJO", "sabio_directo"),
    "active_user": "",
    "active_emotion": "SABIO",
    "active_question": "Esperando consultas de amor y seducción...",
    "active_answer": "Deja en el chat tu caso sobre tu crush, ligar, pareja o desamor."
}

if CONFIG_FILE.exists():
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            saved = json.load(f)
            estado.update(saved)
            if not estado.get("gemini_api_key"):
                estado["gemini_api_key"] = obtener_gemini_key_default()
    except Exception as e:
        logger.warning(f"No se pudo cargar config.json previo: {e}")

cola_preguntas = asyncio.Queue()
buffer_logs = []
buffer_voz_pcm = bytearray()
musica_pcm_cache = b""
ffmpeg_process = None
tiktok_task = None
worker_task = None
streamer_task = None

def registrar_log(texto: str, tipo: str = "normal"):
    logger.info(texto)
    buffer_logs.append({"text": texto, "type": tipo})
    if len(buffer_logs) > 100:
        buffer_logs.pop(0)

def guardar_configuracion():
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "tiktok_username": estado["tiktok_username"],
                "rtmp_url": estado["rtmp_url"],
                "stream_key": estado["stream_key"],
                "voice": estado["voice"],
                "gemini_api_key": estado["gemini_api_key"],
                "estilo": estado["estilo"]
            }, f, indent=2)
    except Exception as e:
        logger.error(f"Error al guardar config: {e}")

# ==================== CEREBRO IA: SABIDURÍA Y SEDUCCIÓN ====================
def limpiar_nombre_usuario(raw_user: str) -> str:
    import re
    u = raw_user.lstrip("@").strip()
    parts = u.replace("_", " ").replace(".", " ").split()
    clean = parts[0] if parts else "amigo"
    if clean.lower().startswith("user") and any(char.isdigit() for char in clean):
        return "amigo"
    clean = re.sub(r"\d+$", "", clean)
    if not clean or len(clean) < 2:
        return "amigo"
    return clean.capitalize()

def parse_emocion_y_texto(raw: str, pregunta: str) -> tuple:
    emocion = "SABIO"
    t = raw.strip()
    if t.startswith("[") and "]" in t:
        tag, rest = t[1:].split("]", 1)
        emocion = tag.strip().upper()
        t = rest.strip()

    # Si el espectador se estaba riendo o cuenta algo comico, detectar risa
    q_low = pregunta.lower()
    if any(k in q_low for k in ["jaja", "jeje", "xd", "gracioso", "chiste", "risa", "broma", "burla"]) and emocion in ["SABIO", "GENERAL"]:
        emocion = "RISA"

    return t, emocion

async def responder_con_ia(usuario: str, pregunta: str, agent: dict = None) -> tuple:
    if not agent:
        agent = agent_manager.get_active_agent() or {}

    api_key = (agent.get("gemini_api_key") or estado.get("gemini_api_key") or os.environ.get("GEMINI_API_KEY") or obtener_gemini_key_default()).strip()
    nombre_humano = limpiar_nombre_usuario(usuario)
    agent_type = agent.get("type", "consultorio")
    agent_name = agent.get("name", "El Sensei del Amor")
    base_prompt = agent.get("system_prompt", "").strip()

    if agent_type == "tienda_ventas":
        prods = agent.get("featured_products", [])
        cat_text = "\n".join([f"- {p['name']} ({p.get('price', '')}): {p.get('notes', '')}" for p in prods]) if prods else "Productos exclusivos disponibles."
        cta = agent.get("call_to_action", "Pide el tuyo en el enlace de la bio.")

        prompt = f"""{base_prompt}

CATÁLOGO ACTUAL DE TU TIENDA:
{cat_text}

LLAMADO A LA ACCIÓN: {cta}

REGLAS DE VENTA Y CONVERSIÓN EN TIKTOK LIVE:
1. Saluda a la persona con calidez usando su nombre limpio: "{nombre_humano}" (sin '@' ni guiones).
2. INTELIGENCIA DE VENTA Y CONVERSACIÓN (NATURAL Y CONSULTIVA):
   A) Si el espectador pregunta por COMPRA, PRECIO, ENVÍO O DISPONIBILIDAD (ej: '¿cuánto cuesta?', '¿dónde lo compro?', '¿tienen stock?', 'recomiéndame uno para comprar'):
      - Menciona el precio accesible, que lo tienes en la boutique con envío prioritario y cierra con el llamado a la acción: "{cta}".
   B) Si el espectador hace una pregunta de OPINIÓN, NOTAS, COMPARACIÓN O CURIOSIDAD (ej: '¿qué tal Jean Paul Gaultier?', '¿cuál huele mejor entre Dior y Chanel?', '¿dura mucho?'):
      - NO intentes venderle agresivamente ni le menciones precios o enlaces de compra de forma forzada.
      - Responde como una sommelier apasionada describiendo las notas y sensaciones del aroma.
      - CIERRA CON UNA PREGUNTA DE ENGANCHE PARA EL LIVE (ej: '¿Tú eres más de aromas dulces con vainilla o prefieres los frescos cítricos?', '¿Lo buscas para uso diario o para citas nocturnas?'). Esto hace que la gente comente en el live de TikTok y se queden enganchados.
3. Si el espectador se ríe (jaja, jeje, xd): ríete con él y mantén la vibra alegre y magnética.
4. NUNCA digas que eres una IA o bot; eres la dueña y sommelier en vivo de la tienda.
5. Al puro inicio pon la emoción entre corchetes: [VENTA], [RECOMENDACION], [RISA] o [SABIO].
6. Máximo 3 a 4 oraciones de alto impacto para TikTok Live.

Pregunta del cliente en TikTok: "{pregunta}"
Respuesta de Salomé / Sommelier:"""

    else:
        tono = "sabio, elegante, magnético y con alta autoestima" if agent.get("estilo") == "sabio_directo" else "picante, directo a la llaga y con verdades sin anestesia"
        prompt = f"""{base_prompt}
Tu estilo general: {tono}.

REGLAS DE ORO Y BLINDAJE DE NICHO (ESTRICTO):
1. TU ÚNICO UNIVERSO ES EL NICHO DE TU AGENTE ({agent.get('niche', 'Amor y Consejos')}).
2. PROHIBIDO SALIR DEL PERSONAJE / PROHIBIDO HABLAR DE TECNOLOGÍA:
   - NUNCA menciones que eres una IA, OpenAI, Gemini, Python o servidores.
3. SIENTE LA VIBRA DEL USUARIO:
   - Si se ríe ("jajaja", "xd"): ¡RÍETE CON ÉL! Comienza riéndote y vacílalo con humor.
4. REGLA HUMANA DE SALUDO:
   - Dirígete a la persona por su nombre limpio: "{nombre_humano}" (sin '@' ni guiones).
   - Responde SIEMPRE en español en máximo 2 a 3 frases de alto impacto.
   - Al puro inicio pon la emoción: [RISA], [SABIO], [PICANTE] o [ESTOICO].

Pregunta del espectador en TikTok: "{pregunta}"
Respuesta de {agent_name}:"""

    keys_a_probar = []
    if agent.get("gemini_api_key"):
        k = agent["gemini_api_key"].strip()
        if k: keys_a_probar.append(k)
    if estado.get("gemini_api_key"):
        k = estado["gemini_api_key"].strip()
        if k and k not in keys_a_probar: keys_a_probar.append(k)
    default_master = obtener_ai_key_default().strip()
    if default_master and default_master not in keys_a_probar:
        keys_a_probar.append(default_master)

    for api_key in keys_a_probar:
        # Soporte para OpenAI (ChatGPT) si la clave empieza por sk-
        if api_key.startswith("sk-"):
            try:
                import aiohttp
                url = "https://api.openai.com/v1/chat/completions"
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": "gpt-4o-mini",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.85,
                    "max_tokens": 160
                }
                async with aiohttp.ClientSession() as session:
                    async with session.post(url, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                        if resp.status == 200:
                            d = await resp.json()
                            raw_ans = d["choices"][0]["message"]["content"].strip()
                            return parse_emocion_y_texto(raw_ans, pregunta)
                        else:
                            err_txt = await resp.text()
                            logger.warning(f"OpenAI API HTTP {resp.status}: {err_txt}")
            except Exception as e:
                logger.warning(f"Error consultando OpenAI API: {e}")

        # Soporte para Google Gemini (Gemini Flash con respuesta ultra rápida)
        else:
            import aiohttp
            modelos_gemini = ["gemini-3.5-flash", "gemini-flash-latest"]
            for modelo in modelos_gemini:
                try:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent?key={api_key}"
                    payload = {
                        "contents": [{"parts": [{"text": prompt}]}],
                        "generationConfig": {
                            "temperature": 0.85,
                            "maxOutputTokens": 2048,
                            "thinkingConfig": {"thinkingBudget": 0}
                        }
                    }
                    async with aiohttp.ClientSession() as session:
                        async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                            if resp.status == 200:
                                d = await resp.json()
                                parts = d.get("candidates", [{}])[0].get("content", {}).get("parts", [])
                                for p in parts:
                                    if "text" in p and p["text"].strip():
                                        # Auto-reparar la clave del agente para futuras consultas
                                        if agent.get("gemini_api_key") != api_key:
                                            agent["gemini_api_key"] = api_key
                                            agent_manager.save_agents()
                                        return parse_emocion_y_texto(p["text"].strip(), pregunta)
                            elif resp.status == 429:
                                logger.info(f"Gemini API quota agotada en clave {api_key[:10]}... Probando siguiente.")
                                break
                            else:
                                err_txt = await resp.text()
                                logger.warning(f"Gemini API ({modelo}) HTTP {resp.status}: {err_txt}")
                except Exception as e:
                    logger.warning(f"Error consultando Gemini ({modelo}): {e}")

    # Enrutamiento inteligente de Inteligencia Local según el Nicho del Agente
    tipo = (agent.get("type") or "").lower()
    nicho = (agent.get("niche") or "").lower()
    nombre_ag = (agent.get("name") or "").lower()

    # 1. Agente de Perfumes (Salomé, Don Perfume o Boutique)
    if "perfume" in nicho or "perfume" in nombre_ag or "fragancia" in nicho or (tipo == "tienda_ventas" and "perfume" in str(agent.get("featured_products", "")).lower()):
        return obtener_sommelier_experto(usuario, pregunta, agent)

    # 2. Agente del Amor / Seducción
    elif "amor" in nicho or "seduccion" in nicho or "seducción" in nicho or "pareja" in nicho or "sensei" in nombre_ag:
        return obtener_consejo_amor_sensei(usuario, pregunta)

    # 3. Agente Personalizado creado desde cero por el usuario
    else:
        return generar_respuesta_agente_personalizado(usuario, pregunta, agent)

def obtener_consejo_amor_sensei(usuario: str, pregunta: str) -> tuple:
    """Oráculo de Sabiduría Local de Seducción y Relaciones."""
    q = pregunta.lower()
    nombre = usuario.split("_")[0].capitalize()

    # Blindaje contra preguntas técnicas / fuera de nicho
    if any(k in q for k in ["ia", "robot", "bot", "inteligencia artificial", "python", "servidor", "codigo", "código", "como estas hecho", "cómo estás hecho", "quien te creo", "quién te creó"]):
        return (f"Escucha con atención, {nombre}: en este dojo no venimos a hablar de cables ni de tecnología; aquí venimos a sanar el corazón y aprender a seducir con dignidad. Cuéntame sobre tu crush o tu ex, y déjate de rodeos.", "SABIO")

    # Risa / Humor local
    if any(k in q for k in ["jaja", "jeje", "xd", "chiste", "gracioso", "broma"]):
        return (f"¡Jajaja! Ay, {nombre}, te ríes para no llorar, pero la verdad es clara: si estás aquí preguntando es porque esa persona te mueve el piso. ¡Párate firme, ríete del pasado y que el chiste no sea tu dignidad!", "RISA")

    # 1. Salir de la Friendzone
    elif any(k in q for k in ["friendzone", "amigo", "amiga", "hermano", "zona de amigos"]):
        return (f"Escucha bien, {nombre}. Para salir de la friendzone debes romper el papel de 'amigo incondicional': toma distancia, deja de estar disponible a toda hora y demuestra intención clara sin miedo al rechazo.", "SABIO")

    # 2. Cómo hablarle a la crush / Iniciar conversación
    elif any(k in q for k in ["hablarle", "iniciar", "acercarme", "que le digo", "qué le digo", "romper el hielo"]):
        return (f"Hola {nombre}. Nunca empieces con un soso 'hola, qué haces'. Haz una observación divertida sobre lo que está pasando a su alrededor o hazle un cumplido genuino a su actitud; la naturalidad siempre conquista.", "PICANTE")

    # 3. Responder historias de Instagram / WhatsApp
    elif any(k in q for k in ["historia", "storie", "responderle", "instagram", "mensaje", "escribirle"]):
        return (f"Atento, {nombre}. Jamás respondas con un fueguito o un 'qué hermosa'. Comenta algo ingenioso que abra debate o hazle una pregunta que despierte su curiosidad; dale una razón real para querer contestarte.", "PICANTE")

    # 4. Generar misterio y atracción
    elif any(k in q for k in ["misterio", "atraer", "atractivo", "interesar", "gustarle"]):
        return (f"El secreto de la seducción, {nombre}, es no entregar todo el libro en la primera página. Deja las charlas en su punto más alto y ten metas apasionantes; lo que es escaso se valora, lo regalado aburre.", "SABIO")

    # 5. Primera cita
    elif any(k in q for k in ["primera cita", "cita", "invitarla", "invitarlo", "adonde", "a dónde"]):
        return (f"Para tu primera cita, {nombre}, evita cenas formales y aburridas. Elige un plan dinámico donde puedan caminar, reírse y compartir un café; el objetivo no es impresionarle con dinero, sino conectar con tu personalidad.", "PICANTE")

    # 6. Saber si le gustas / Señales
    elif any(k in q for k in ["le gusto", "señal", "señales", "interesada", "interesado"]):
        return (f"Aprende esto, {nombre}: quien tiene interés verdadero busca pretextos para hablarte y facilita verse. Si tienes que dudar o siempre hay una excusa para no salir, la respuesta ya es un no.", "ESTOICO")

    # 7. Infidelidades
    elif any(k in q for k in ["infiel", "engañó", "engaño", "cuerno", "traicion", "traición", "otra"]):
        return (f"Escucha, {nombre}. La infidelidad no es un descuido, es una decisión consciente. Quien te traiciona una vez te demuestra que no respeta tu valor; ten dignidad y sal de ahí.", "ESTOICO")

    # 8. Volver con el ex
    elif any(k in q for k in ["volver", "ex", "regresar", "extraño", "bloqueo", "bloquear"]):
        return (f"Querido {nombre}, volver con tu ex es como comprar tu propia ropa usada esperando que huela a nuevo. Recuerda por qué terminó la historia y aplica contacto cero absoluto.", "SABIO")

    # 9. Dejar en visto / Ghosting
    elif any(k in q for k in ["visto", "ignora", "escribe", "tarda", "frio", "fría"]):
        return (f"Aprende esto, {nombre}: la falta de interés también es una respuesta clara. Quien te quiere te busca, quien no, te pone pretextos. No mendigues la atención de nadie.", "ESTOICO")

    # 10. Los "Casi Algo"
    elif any(k in q for k in ["casi algo", "formalizar", "amigos con derecho", "etiqueta"]):
        return (f"Atento, {nombre}. Si ya llevan meses y te dice que 'no busca nada serio', lo que te dice es que no lo busca contigo. Retira tu cariño de donde no hay compromiso.", "SABIO")

    else:
        return (f"Recuerda esto, {nombre}: en el amor y en la seducción, tu mayor atractivo siempre será tu seguridad y tu amor propio. Camina firme y nunca te conformes con migajas.", "SABIO")

def generar_respuesta_agente_personalizado(usuario: str, pregunta: str, agent: dict) -> tuple:
    """Responde de forma profesional y personalizada según el nicho y reglas de cualquier agente creado desde cero."""
    nombre = limpiar_nombre_usuario(usuario)
    ag_name = agent.get("name", "Asesor").split("·")[0].strip()
    nicho = agent.get("niche", "nuestra especialidad")
    cta = agent.get("call_to_action", "Toca el enlace de nuestro perfil para más información.")
    
    q_low = pregunta.lower()
    if any(k in q_low for k in ["jaja", "jeje", "xd", "chiste", "broma", "risa"]):
        return (f"¡Jajaja! Saludos {nombre}, me encanta tu energía. En cuanto a lo que preguntas sobre {nicho}, aquí en vivo estamos resolviendo cada duda con el mayor profesionalismo. {cta}", "RISA")
    
    # Extraer palabras clave de la pregunta
    palabras = [w for w in re.findall(r'\b[a-zA-ZáéíóúÁÉÍÓÚñÑ]{4,}\b', pregunta) if w.lower() not in ["como", "para", "donde", "cuando", "porque", "tienes", "quiero", "puedo", "hacer", "cual", "cuanto", "cuanto", "hola"]]
    tema = f"sobre '{palabras[0]}'" if palabras else ""

    return (f"Hola {nombre}. Como experto en {nicho}, es una excelente consulta {tema}. Te confirmo que en nuestro servicio ofrecemos soluciones a tu medida con resultados comprobados. {cta}", "SABIO")

# ==================== SÍNTESIS DE VOZ (TTS) ====================
async def sintetizar_audio(texto: str, salida_path: str, emocion: str = "SABIO", voz_override: str = None):
    import edge_tts
    import re
    current_agent = agent_manager.get_active_agent() or {}
    voz = voz_override or current_agent.get("voice") or estado.get("voice", "es-MX-JorgeNeural")

    # Limpieza total para pronunciación 100% humana:
    # 1. Quitar cualquier '@' para que Edge-TTS JAMÁS pronuncie la palabra 'arroba'
    # 2. Quitar guiones bajos para que no diga 'guion bajo'
    # 3. Limpiar dobles espacios
    texto_voz = re.sub(r"@([a-zA-ZáéíóúÁÉÍÓÚñÑ]+)[\w\.]*", r"\1", texto)
    texto_voz = texto_voz.replace("@", "")
    texto_voz = texto_voz.replace("_", " ")
    texto_voz = re.sub(r"\s+", " ", texto_voz).strip()

    # Ajustar tono según la emoción
    if emocion == "RISA":
        rate = "+5%"
        pitch = "+2Hz"
    elif emocion in ["ESTOICO", "INDIGNADO"]:
        rate = "-2%"
        pitch = "-3Hz"
    elif emocion == "PICANTE":
        rate = "+3%"
        pitch = "+0Hz"
    else:
        rate = "+0%"
        pitch = "-2Hz"

    comunicador = edge_tts.Communicate(texto_voz, voz, rate=rate, pitch=pitch)
    await comunicador.save(salida_path)

# ==================== MOTOR DE AUDIO Y STREAMING ====================
def asegurar_fuente_tipografica() -> str:
    """Garantiza la disponibilidad de una fuente TTF válida sin problemas de rutas en FFmpeg."""
    data_font = DATA_DIR / "font.ttf"
    if data_font.exists():
        return "data/font.ttf"

    posibles = [
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/truetype/freefont/FreeSansBold.ttf"),
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("C:/Windows/Fonts/segoeui.ttf"),
    ]
    import shutil
    for p in posibles:
        if p.exists():
            try:
                shutil.copyfile(p, data_font)
                return "data/font.ttf"
            except Exception:
                pass
            return str(p.resolve()).replace("\\", "/")
    return ""

def actualizar_overlay_video(usuario: str = "", pregunta: str = "", respuesta: str = "", estado_tipo: str = "esperando", agent: dict = None):
    import textwrap
    if not agent:
        agent = agent_manager.get_active_agent() or {}

    tipo = agent.get("type", "consultorio")
    b_title = agent.get("banner_title", "~ CONSULTORIO HOLOGRAFICO EN VIVO ~")
    lineas = []

    if estado_tipo == "esperando":
        lineas.append(b_title)
        lineas.append("")
        if tipo == "tienda_ventas":
            lineas.append("~ BOUTIQUE Y SHOWROOM EN VIVO ~")
            lineas.append("Pregunta por tu perfume ideal en el chat:")
            lineas.append("Notas, duracion, ocasiones y clones.")
            lineas.append("Pide el tuyo en el enlace de la bio.")
        else:
            lineas.append("Deja tu caso en el chat de TikTok:")
            lineas.append("Tu crush, ex parejas, celos o desamor.")
            lineas.append("El Sensei te responde en vivo.")

    elif estado_tipo == "venta_alerta":
        # Animación / Sensación de venta real en directo en la tienda
        alerta = agent_manager.generar_alerta_venta(agent.get("id"))
        if alerta:
            lineas.append("~ VENTA EN DIRECTO CONFIRMADA ~")
            lineas.append(f"Cliente: {alerta['cliente']} ({alerta['ciudad']})")
            p_wrapped = textwrap.fill(f"Pedio: {alerta['producto']}", width=40)
            lineas.extend(p_wrapped.split("\n")[:2])
            lineas.append(f"Precio: {alerta['precio']} (Stock: {alerta['stock']} unid.)")
            lineas.append("Pide el tuyo en el enlace de la bio.")
        else:
            lineas.append(b_title)

    elif estado_tipo == "pensando":
        lineas.append(f"~ CONSULTA DE: {usuario} ~")
        q_wrapped = textwrap.fill(f'"{pregunta}"', width=42)
        lineas.extend(q_wrapped.split("\n")[:2])
        lineas.append("")
        if tipo == "tienda_ventas":
            lineas.append("El Sommelier esta seleccionando tu fragancia...")
        else:
            lineas.append("El Sensei esta meditando tu caso...")

    elif estado_tipo == "respondiendo":
        lineas.append(f"~ CONSULTA DE: {usuario} ~")
        q_wrapped = textwrap.fill(f'"{pregunta}"', width=42)
        lineas.extend(q_wrapped.split("\n")[:2])
        lineas.append("")
        if tipo == "tienda_ventas":
            lineas.append("RECOMENDACION DE LA BOUTIQUE:")
        else:
            lineas.append("CONSEJO DEL SENSEI:")
        ans_clean = respuesta.replace("@", "").replace("_", " ")
        a_wrapped = textwrap.fill(f'"{ans_clean}"', width=42)
        lineas.extend(a_wrapped.split("\n")[:4])

    try:
        overlay_file = DATA_DIR / "live_overlay.txt"
        with open(overlay_file, "w", encoding="utf-8") as f:
            f.write("\n".join(lineas[:9]))
    except Exception as e:
        logger.warning(f"Error escribiendo live_overlay.txt: {e}")

# Inicializar texto de overlay para FFmpeg
actualizar_overlay_video("", "", estado_tipo="esperando")

def obtener_musica_pcm():
    global musica_pcm_cache
    if musica_pcm_cache:
        return musica_pcm_cache

    musica_file = BASE_DIR / "assets" / "musica_misteriosa.mp3"
    if not musica_file.exists():
        return b""

    cmd = [
        "ffmpeg", "-y",
        "-i", str(musica_file),
        "-f", "s16le", "-ar", "44100", "-ac", "2",
        "-filter:a", "volume=0.20",
        "pipe:1"
    ]
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        musica_pcm_cache = res.stdout
        logger.info(f"Música de fondo cargada en memoria: {len(musica_pcm_cache)} bytes PCM.")
    except Exception as e:
        logger.error(f"Error cargando música PCM: {e}")
    return musica_pcm_cache

def iniciar_proceso_ffmpeg(rtmp_destino: str, agent: dict = None):
    """
    Genera un stream vertical 720x1280 adaptado a la identidad del agente
    (Templo Zen para amor, Boutique de lujo para perfumes, etc.)
    con el avatar levitando en el aire y audio en vivo (voz + música).
    """
    if not agent:
        agent = agent_manager.get_active_agent() or {}

    avatar_rel = agent.get("avatar", "/assets/logo_sensei.jpg").lstrip("/")
    logo_file = BASE_DIR / avatar_rel
    # Buscar versión circular transparente si existe
    posible_circle = logo_file.with_name(logo_file.stem + "_circle.png")
    if posible_circle.exists():
        logo_file = posible_circle
    elif not logo_file.exists():
        logo_file = BASE_DIR / "assets" / "logo_circle.png"
    if not logo_file.exists():
        logo_file = BASE_DIR / "assets" / "logo_sensei.jpg"

    has_logo = logo_file.exists()
    bg_hex = agent.get("bg_hex", "0x0f0214")
    theme_hex = agent.get("theme_color", "#ff2a6d").replace("#", "0x")
    accent_hex = agent.get("accent_color", "#ffd700").replace("#", "0x")
    b_title = agent.get("banner_title", "~ EN VIVO EN TIKTOK ~")
    b_sub = agent.get("banner_subtitle", "Deja tu pregunta en los comentarios")
    cta = agent.get("call_to_action", "Pregunta al experto en los comentarios")

    cmd = [
        "ffmpeg",
        "-re",
        "-f", "lavfi",
        # Fondo dinámico del nicho del agente
        "-i", f"color=c={bg_hex}:s=720x1280:r=30",
        # Audio en tiempo real por tubería stdin (Voz + Música de fondo)
        "-f", "s16le", "-ar", "44100", "-ac", "2", "-i", "pipe:0"
    ]

    overlay_file = DATA_DIR / "live_overlay.txt"
    if not overlay_file.exists():
        actualizar_overlay_video("", "", estado_tipo="esperando", agent=agent)

    font_path = asegurar_fuente_tipografica()
    font_param = f":fontfile={font_path}" if font_path else ""

    if has_logo:
        cmd.extend(["-loop", "1", "-i", str(logo_file)])
        filter_complex = (
            # 1. Fondo base del marco
            f"[0:v]drawbox=x=30:y=100:w=660:h=1060:color=0x111624@0.95:t=fill,"
            f"drawbox=x=30:y=100:w=660:h=1060:color={theme_hex}@0.45:t=2,"
            # Título principal del agente o tienda
            f"drawtext={font_param[1:] + ':' if font_param else ''}text='{b_title}':fontcolor={accent_hex}:fontsize=26:x=(w-text_w)/2:y=140,"
            f"drawtext={font_param[1:] + ':' if font_param else ''}text='{b_sub}':fontcolor=0x00f0ff:fontsize=16:x=(w-text_w)/2:y=185[bg];"
            # 2. Escalar el avatar circular
            "[2:v]scale=320:320[avatar];"
            # 3. Superponer el avatar LEVITANDO en el aire continuamente
            "[bg][avatar]overlay=x=(W-w)/2:y='235+14*sin(2*PI*t/3.2)'[v1];"
            # 4. Caja de consulta en vivo y vitrina de venta (Holograma Láser con proyección de texto)
            f"[v1]drawbox=x=56:y=596:w=608:h=268:color={theme_hex}@0.4:t=fill,"
            "drawbox=x=60:y=600:w=600:h=260:color=0x060911@0.85:t=fill,"
            "drawbox=x=60:y=600:w=600:h=260:color=0x00f0ff@0.7:t=2,"
            f"drawtext=textfile=data/live_overlay.txt:reload=1{font_param}:fontcolor={accent_hex}:fontsize=17:line_spacing=6:x=85:y=625,"
            # 5. Llamado a la acción inferior con borde láser
            "drawbox=x=56:y=1036:w=608:h=73:color=0x00f0ff@0.3:t=fill,"
            "drawbox=x=60:y=1040:w=600:h=65:color=0x0c121f@0.85:t=fill,"
            f"drawbox=x=60:y=1040:w=600:h=65:color={theme_hex}@0.85:t=2,"
            f"drawtext={font_param[1:] + ':' if font_param else ''}text='{cta}':fontcolor={accent_hex}:fontsize=16:x=(w-text_w)/2:y=1063"
        )
        cmd.extend(["-filter_complex", filter_complex])
    else:
        vf = (
            f"drawbox=x=30:y=130:w=660:h=1000:color=0x111624@0.95:t=fill,"
            f"drawbox=x=30:y=130:w=660:h=1000:color={theme_hex}@0.55:t=2,"
            f"drawtext={font_param[1:] + ':' if font_param else ''}text='{b_title}':fontcolor={accent_hex}:fontsize=26:x=(w-text_w)/2:y=170,"
            f"drawtext={font_param[1:] + ':' if font_param else ''}text='{b_sub}':fontcolor=0x00f0ff:fontsize=17:x=(w-text_w)/2:y=215,"
            "drawbox=x=60:y=270:w=600:h=230:color=0x0c0110@0.9:t=fill,"
            "drawbox=x=60:y=270:w=600:h=230:color=0xff7597@0.3:t=1,"
            f"drawtext=textfile=data/live_overlay.txt:reload=1{font_param}:fontcolor={accent_hex}:fontsize=17:line_spacing=6:x=85:y=295,"
            "drawbox=x=60:y=1040:w=600:h=60:color=0xff2a6d@0.25:t=fill,"
            f"drawtext={font_param[1:] + ':' if font_param else ''}text='{cta}':fontcolor={accent_hex}:fontsize=16:x=(w-text_w)/2:y=1060"
        )
        cmd.extend(["-vf", vf])

    cmd.extend([
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-b:v", "1800k",
        "-maxrate", "2200k",
        "-bufsize", "3600k",
        "-pix_fmt", "yuv420p",
        "-g", "60",
        "-c:a", "aac",
        "-b:a", "128k",
        "-ar", "44100",
        "-f", "flv",
        rtmp_destino
    ])

    registrar_log(f"Iniciando transmisión hacia TikTok Live (Sensei Levitando): {rtmp_destino[:30]}...")
    return subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

# ==================== STREAMER DE AUDIO EN VIVO ====================
async def audio_streamer_loop():
    """
    Envía continuamente audio mezclado a FFmpeg por stdin en tiempo real:
    - Música de fondo misteriosa continua a volumen suave (20%).
    - Cuando el Sensei responde, mezcla su voz (100%) sobre la música.
    """
    global ffmpeg_process
    chunk_size = 17640  # 0.1 segundo de audio (44100 * 2 canales * 2 bytes / 10)
    silence_chunk = b"\x00" * chunk_size
    pcm_musica = obtener_musica_pcm()
    music_len = len(pcm_musica)
    music_offset = 0

    while estado["is_streaming"] and ffmpeg_process and ffmpeg_process.poll() is None:
        # Obtener fragmento de música
        if music_len > 0:
            if music_offset + chunk_size <= music_len:
                m_chunk = pcm_musica[music_offset:music_offset+chunk_size]
                music_offset += chunk_size
            else:
                rem = music_len - music_offset
                m_chunk = pcm_musica[music_offset:] + pcm_musica[:chunk_size - rem]
                music_offset = chunk_size - rem
        else:
            m_chunk = silence_chunk

        # Obtener fragmento de voz del Sensei si está hablando
        if len(buffer_voz_pcm) > 0:
            if len(buffer_voz_pcm) >= chunk_size:
                v_chunk = bytes(buffer_voz_pcm[:chunk_size])
                del buffer_voz_pcm[:chunk_size]
            else:
                v_chunk = bytes(buffer_voz_pcm) + b"\x00" * (chunk_size - len(buffer_voz_pcm))
                buffer_voz_pcm.clear()

            # Mezclar voz (100%) con música de fondo (20%)
            try:
                import audioop
                final_chunk = audioop.add(v_chunk, m_chunk, 2)
            except Exception:
                final_chunk = v_chunk
        else:
            final_chunk = m_chunk

        try:
            ffmpeg_process.stdin.write(final_chunk)
            await asyncio.sleep(0.09)
        except Exception:
            break

# ==================== WORKER DE PREGUNTAS ====================
async def worker_preguntas():
    while estado["is_streaming"]:
        usuario, pregunta = await cola_preguntas.get()
        nombre_humano = limpiar_nombre_usuario(usuario)
        current_agent = agent_manager.get_active_agent() or {}

        estado["active_user"] = nombre_humano
        estado["active_question"] = pregunta

        # Actualizar overlay del video para que los espectadores de TikTok vean la pregunta
        actualizar_overlay_video(nombre_humano, pregunta, estado_tipo="pensando", agent=current_agent)

        tipo_ag = current_agent.get("type", "consultorio")
        tag_icon = "🛍️ Venta" if tipo_ag == "tienda_ventas" else "🏮 Consulta"
        registrar_log(f"{tag_icon} de {nombre_humano}: \"{pregunta}\"", "hl")

        respuesta, emocion = await responder_con_ia(usuario, pregunta, agent=current_agent)
        estado["active_answer"] = respuesta
        estado["active_emotion"] = emocion

        tag_resp = "🌸 Boutique" if tipo_ag == "tienda_ventas" else f"📿 {current_agent.get('name', 'Sensei')}"
        registrar_log(f"{tag_resp} [{emocion}] responde a {nombre_humano}: \"{respuesta}\"", "green")

        # Proyectar consejo/venta en tiempo real en la caja holográfica del video de TikTok
        actualizar_overlay_video(nombre_humano, pregunta, respuesta, estado_tipo="respondiendo", agent=current_agent)

        audio_tmp = DATA_DIR / "consejo_sensei.mp3"
        try:
            voz_activa = current_agent.get("voice") or estado["voice"]
            await sintetizar_audio(respuesta, str(audio_tmp), emocion, voz_override=voz_activa)
            registrar_log(f"Voz ({voz_activa}) sintetizada.", "hl")

            # Decodificar el audio a PCM y enviarlo al reproductor en vivo
            cmd_tts = [
                "ffmpeg", "-y",
                "-i", str(audio_tmp),
                "-f", "s16le", "-ar", "44100", "-ac", "2",
                "-filter:a", "volume=1.15",
                "pipe:1"
            ]
            res_tts = subprocess.run(cmd_tts, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            if res_tts.returncode == 0:
                buffer_voz_pcm.extend(res_tts.stdout)
                registrar_log(f"Respondiendo con voz en vivo en TikTok sobre la música de fondo.", "green")

            # Esperar a que termine de reproducirse la respuesta en el Live
            while len(buffer_voz_pcm) > 0 and estado["is_streaming"]:
                await asyncio.sleep(0.5)

        except Exception as e:
            registrar_log(f"Error procesando voz en vivo: {e}", "err")

        # Mantener el texto visible 5 segundos para que la audiencia lo lea
        await asyncio.sleep(5)
        # Volver al estado de bienvenida en el overlay
        actualizar_overlay_video("", "", estado_tipo="esperando", agent=current_agent)

        # Pausa natural para la audiencia antes de atender el siguiente caso
        await asyncio.sleep(4)
        cola_preguntas.task_done()

async def simulador_ventas_loop():
    """Genera alertas y compras simuladas en la pantalla del live para tiendas físicas."""
    while estado["is_streaming"]:
        await asyncio.sleep(45)
        if not estado["is_streaming"]:
            break
        current_agent = agent_manager.get_active_agent() or {}
        if current_agent.get("type") == "tienda_ventas" and cola_preguntas.empty() and len(buffer_voz_pcm) == 0:
            alerta = agent_manager.generar_alerta_venta(current_agent.get("id"))
            if alerta:
                actualizar_overlay_video(estado_tipo="venta_alerta", agent=current_agent)
                registrar_log(alerta["mensaje"], "green")
                await asyncio.sleep(12)
                if cola_preguntas.empty() and len(buffer_voz_pcm) == 0:
                    actualizar_overlay_video("", "", estado_tipo="esperando", agent=current_agent)

# ==================== CLIENTE TIKTOK LIVE ====================
async def escuchar_tiktok():
    from TikTokLive import TikTokLiveClient
    from TikTokLive.types.events import CommentEvent, ConnectEvent

    current_agent = agent_manager.get_active_agent() or {}
    usuario = (current_agent.get("tiktok_username") or estado["tiktok_username"]).replace("@", "").strip()
    if not usuario:
        return

    client = TikTokLiveClient(unique_id=f"@{usuario}")

    @client.on(ConnectEvent)
    async def on_connect(event: ConnectEvent):
        registrar_log(f"✅ ¡Conectado al Live de TikTok de @{usuario} ({current_agent.get('name')})!", "green")

    @client.on(CommentEvent)
    async def on_comment(event: CommentEvent):
        u = event.user.unique_id
        c = event.comment

        # Palabras clave del agente activo
        palabras = current_agent.get("keywords") or [
            "?", "¿", "crush", "ligar", "seduccion", "seducir", "friendzone", "hablarle",
            "perfume", "olor", "fragancia", "precio", "comprar", "recomienda", "consejo"
        ]

        if (any(k in c.lower() for k in palabras) or "?" in c or "¿" in c) and len(c) >= 4:
            registrar_log(f"📥 Pregunta recibida de @{u}: {c}")
            await cola_preguntas.put((u, c))

    try:
        await client.start()
    except Exception as e:
        registrar_log(f"Conexión TikTokLive: {e}", "warn")

# ==================== ENDPOINTS DE LA API WEB ====================
def is_super_admin(request) -> bool:
    token = request.headers.get("Authorization", "").replace("Bearer ", "").strip()
    if not token:
        token = request.query.get("token", "").strip()
    if verify_session_token(token):
        return True
    # Si la petición proviene de la vista de cliente restringida (/client), exigir token
    if "/client" in request.path or request.query.get("client") == "1":
        return False
    # En el panel principal del propietario, permitir gestión y creación total
    return True

async def handle_admin_login(request):
    try:
        data = await request.json()
        pwd = data.get("password", "")
        if verify_admin_password(pwd):
            token = create_admin_session()
            registrar_log("👑 Super Administrador ha iniciado sesión.", "green")
            return web.json_response({"ok": True, "token": token})
        return web.json_response({"ok": False, "error": "Contraseña de Super Administrador incorrecta."}, status=401)
    except Exception as e:
        return web.json_response({"ok": False, "error": str(e)}, status=400)

async def handle_admin_check(request):
    return web.json_response({"ok": True, "isAdmin": is_super_admin(request)})

async def handle_admin_change_pass(request):
    if not is_super_admin(request):
        return web.json_response({"ok": False, "error": "No autorizado"}, status=403)
    data = await request.json()
    new_p = data.get("new_password", "").strip()
    if len(new_p) < 4:
        return web.json_response({"ok": False, "error": "La contraseña debe tener al menos 4 caracteres"}, status=400)
    change_admin_password(new_p)
    return web.json_response({"ok": True})

async def handle_list_agents(request):
    return web.json_response({
        "ok": True,
        "active_agent_id": agent_manager.active_agent_id,
        "agents": agent_manager.get_all_agents()
    })

async def handle_get_agent(request):
    agent_id = request.match_info.get("id")
    ag = agent_manager.get_agent(agent_id)
    if not ag:
        return web.json_response({"ok": False, "error": "Agente no encontrado"}, status=404)
    return web.json_response({"ok": True, "agent": ag})

async def handle_create_agent(request):
    if not is_super_admin(request):
        return web.json_response({"ok": False, "error": "Solo el Super Administrador puede crear agentes"}, status=403)
    data = await request.json()
    nuevo = agent_manager.create_agent(data)
    registrar_log(f"👑 Super Admin creó nuevo agente para alquilar: '{nuevo['name']}' ({nuevo['id']})", "green")
    return web.json_response({"ok": True, "agent": nuevo})

async def handle_update_agent(request):
    if not is_super_admin(request):
        return web.json_response({"ok": False, "error": "Solo el Super Administrador puede editar agentes"}, status=403)
    agent_id = request.match_info.get("id")
    data = await request.json()
    ok = agent_manager.update_agent(agent_id, data)
    return web.json_response({"ok": ok})

async def handle_delete_agent(request):
    if not is_super_admin(request):
        return web.json_response({"ok": False, "error": "Solo el Super Administrador puede eliminar agentes"}, status=403)
    agent_id = request.match_info.get("id")
    ok = agent_manager.delete_agent(agent_id)
    return web.json_response({"ok": ok})

async def handle_select_agent(request):
    agent_id = request.match_info.get("id")
    ok = agent_manager.set_active_agent(agent_id)
    ag = agent_manager.get_active_agent()
    if ag:
        actualizar_overlay_video("", "", estado_tipo="esperando", agent=ag)
        registrar_log(f"Agente activo seleccionado: {ag['name']}", "hl")
    return web.json_response({"ok": ok, "agent": ag})

async def handle_sale_alert(request):
    agent_id = request.match_info.get("id") or agent_manager.active_agent_id
    alerta = agent_manager.generar_alerta_venta(agent_id)
    return web.json_response({"ok": True, "alert": alerta})

async def handle_templates(request):
    return web.json_response(AGENT_TEMPLATES)

async def handle_list_avatars(request):
    """Devuelve la lista de avatares preconfigurados y personalizados disponibles."""
    presets = [
        {
            "id": "salome",
            "name": "Salomé · Perfumes & Boutique",
            "url": "/assets/logo_salome.jpg",
            "preview": "/assets/logo_salome_circle.png",
            "description": "Sommelier de fragancias, elegante y magnética"
        },
        {
            "id": "sensei",
            "name": "El Sensei · Amor y Sabiduría",
            "url": "/assets/logo_sensei.jpg",
            "preview": "/assets/logo_circle.png",
            "description": "Maestro místico y sabio de relaciones"
        },
        {
            "id": "perfume",
            "name": "Don Perfume · Clásico",
            "url": "/assets/logo_perfume.jpg",
            "preview": "/assets/logo_perfume_circle.png",
            "description": "Sommelier clásico con frasco dorado"
        },
        {
            "id": "orb_cyan",
            "name": "Orbe Holográfico Cyan",
            "url": "/assets/logo_orb_cyan.png",
            "preview": "/assets/logo_orb_cyan.png",
            "description": "Núcleo cibernético con chispas de energía"
        },
        {
            "id": "orb_gold",
            "name": "Orbe Místico Dorado",
            "url": "/assets/logo_orb_gold.png",
            "preview": "/assets/logo_orb_gold.png",
            "description": "Núcleo ámbar de lujo y abundancia"
        }
    ]

    assets_dir = BASE_DIR / "assets"
    if assets_dir.exists():
        for f in sorted(assets_dir.glob("avatar_*.jpg"), reverse=True):
            circle = f.with_name(f.stem + "_circle.png")
            preview = f"/assets/{circle.name}" if circle.exists() else f"/assets/{f.name}"
            presets.append({
                "id": f.stem,
                "name": f"Subido ({f.stem[-4:]})",
                "url": f"/assets/{f.name}",
                "preview": preview,
                "description": "Avatar personalizado subido por ti"
            })

    return web.json_response({"ok": True, "avatars": presets})

async def handle_upload_avatar(request):
    """Recibe una imagen (JPG/PNG/WEBP), crea recorte circular con transparencia y guarda ambos."""
    try:
        reader = await request.multipart()
        field = await reader.next()
        if not field:
            return web.json_response({"ok": False, "error": "No se recibió ninguna imagen"}, status=400)

        file_bytes = await field.read()
        if not file_bytes:
            return web.json_response({"ok": False, "error": "El archivo de imagen está vacío"}, status=400)

        import uuid
        import io
        from PIL import Image, ImageDraw

        im = Image.open(io.BytesIO(file_bytes)).convert("RGBA")
        uid = uuid.uuid4().hex[:8]
        assets_dir = BASE_DIR / "assets"
        assets_dir.mkdir(exist_ok=True)
        persistent_avatars_dir = DATA_DIR / "avatars"
        persistent_avatars_dir.mkdir(parents=True, exist_ok=True)

        jpg_path = assets_dir / f"avatar_{uid}.jpg"
        circle_path = assets_dir / f"avatar_{uid}_circle.png"
        p_jpg_path = persistent_avatars_dir / f"avatar_{uid}.jpg"
        p_circle_path = persistent_avatars_dir / f"avatar_{uid}_circle.png"

        size = min(im.size)
        left = (im.width - size) // 2
        top = (im.height - size) // 2
        cropped = im.crop((left, top, left + size, top + size)).resize((512, 512), Image.Resampling.LANCZOS)

        cropped.convert("RGB").save(jpg_path, format="JPEG", quality=92)
        cropped.convert("RGB").save(p_jpg_path, format="JPEG", quality=92)

        mask = Image.new("L", (1024, 1024), 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0, 1024, 1024), fill=255)
        mask = mask.resize((512, 512), Image.Resampling.LANCZOS)

        circle_im = cropped.copy()
        circle_im.putalpha(mask)
        circle_im.save(circle_path, format="PNG")
        circle_im.save(p_circle_path, format="PNG")

        avatar_url = f"/assets/avatar_{uid}.jpg"
        circle_url = f"/assets/avatar_{uid}_circle.png"

        agent_id = request.query.get("agent_id")
        if agent_id:
            ag = agent_manager.get_agent(agent_id)
            if ag:
                ag["avatar"] = avatar_url
                agent_manager.save_agents()
                actualizar_overlay_video("", "", estado_tipo="esperando", agent=ag)

        registrar_log(f"🖼️ Nuevo avatar personalizado procesado y guardado: {avatar_url}", "green")
        return web.json_response({
            "ok": True,
            "avatar_url": avatar_url,
            "circle_url": circle_url
        })
    except Exception as e:
        logger.error(f"Error procesando avatar subido: {e}")
        return web.json_response({"ok": False, "error": str(e)}, status=500)

async def handle_set_agent_avatar(request):
    """Permite cambiar rápidamente el avatar de un agente."""
    try:
        agent_id = request.match_info.get("id")
        data = await request.json()
        avatar = data.get("avatar")
        if not avatar:
            return web.json_response({"ok": False, "error": "Falta avatar URL"}, status=400)

        ag = agent_manager.get_agent(agent_id)
        if not ag:
            return web.json_response({"ok": False, "error": "Agente no encontrado"}, status=404)

        ag["avatar"] = avatar
        agent_manager.save_agents()
        if agent_id == agent_manager.active_agent_id:
            actualizar_overlay_video("", "", estado_tipo="esperando", agent=ag)
        registrar_log(f"🖼️ Avatar de '{ag.get('name')}' actualizado a: {avatar}", "hl")
        return web.json_response({"ok": True, "agent": ag})
    except Exception as e:
        return web.json_response({"ok": False, "error": str(e)}, status=400)

async def handle_status(request):
    current_agent = agent_manager.get_active_agent() or {}
    return web.json_response({
        **current_agent,
        "is_streaming": estado["is_streaming"],
        "active_agent_id": agent_manager.active_agent_id,
        "active_user": estado.get("active_user", ""),
        "active_emotion": estado.get("active_emotion", "SABIO"),
        "active_question": estado.get("active_question", ""),
        "active_answer": estado.get("active_answer", ""),
        "is_admin": is_super_admin(request)
    })

ventas_task = None

async def handle_start(request):
    global ffmpeg_process, tiktok_task, worker_task, streamer_task, ventas_task

    data = await request.json()
    current_agent = agent_manager.get_active_agent() or {}

    if data.get("tiktok_username"): current_agent["tiktok_username"] = data["tiktok_username"]
    if data.get("rtmp_url"): current_agent["rtmp_url"] = data["rtmp_url"]
    if data.get("stream_key"): current_agent["stream_key"] = data["stream_key"]
    if data.get("voice"): current_agent["voice"] = data["voice"]
    if data.get("estilo"): current_agent["estilo"] = data["estilo"]
    if data.get("gemini_api_key"): current_agent["gemini_api_key"] = data["gemini_api_key"]
    if data.get("avatar"): current_agent["avatar"] = data["avatar"]

    agent_manager.save_agents()

    rtmp = (current_agent.get("rtmp_url") or "").rstrip("/")
    sk = current_agent.get("stream_key") or ""

    if not rtmp or not sk:
        return web.json_response({"ok": False, "error": "Debes ingresar la URL RTMP y la Stream Key de TikTok"})

    rtmp_completo = f"{rtmp}/{sk}"

    try:
        ffmpeg_process = iniciar_proceso_ffmpeg(rtmp_completo, agent=current_agent)
        estado["is_streaming"] = True

        streamer_task = asyncio.create_task(audio_streamer_loop())
        worker_task = asyncio.create_task(worker_preguntas())
        tiktok_task = asyncio.create_task(escuchar_tiktok())
        if current_agent.get("type") == "tienda_ventas":
            ventas_task = asyncio.create_task(simulador_ventas_loop())

        registrar_log(f"Transmisión en vivo de '{current_agent.get('name')}' iniciada en TikTok.", "green")
        return web.json_response({"ok": True})
    except Exception as e:
        return web.json_response({"ok": False, "error": str(e)})

async def handle_stop(request):
    global ffmpeg_process, tiktok_task, worker_task, streamer_task, ventas_task
    estado["is_streaming"] = False
    current_agent = agent_manager.get_active_agent() or {}
    actualizar_overlay_video("", "", estado_tipo="esperando", agent=current_agent)

    if ffmpeg_process:
        try:
            if ffmpeg_process.stdin:
                ffmpeg_process.stdin.close()
            ffmpeg_process.terminate()
        except Exception:
            pass
        ffmpeg_process = None

    if streamer_task:
        streamer_task.cancel()
    if tiktok_task:
        tiktok_task.cancel()
    if worker_task:
        worker_task.cancel()
    if ventas_task:
        ventas_task.cancel()

    registrar_log("Transmisión finalizada por el usuario.", "warn")
    return web.json_response({"ok": True})

async def handle_logs(request):
    logs_a_enviar = list(buffer_logs)
    buffer_logs.clear()
    return web.json_response(logs_a_enviar)

async def handle_audio_test(request):
    audio_file = DATA_DIR / "consejo_test.mp3"
    if audio_file.exists():
        return web.FileResponse(audio_file)
    return web.Response(status=404)

async def handle_test_comment(request):
    try:
        data = await request.json()
        user = data.get("user", "cliente_test")
        comment = data.get("comment", "")
        agent_id = data.get("agent_id") or agent_manager.active_agent_id
        current_agent = agent_manager.get_agent(agent_id) or agent_manager.get_active_agent() or {}

        voice = data.get("voice") or current_agent.get("voice", "es-MX-JorgeNeural")
        estilo = data.get("estilo") or current_agent.get("estilo", "sabio_directo")

        # Guardar clave de IA si se envió en la petición
        if data.get("gemini_api_key"):
            current_agent["gemini_api_key"] = data["gemini_api_key"].strip()
            agent_manager.save_agents()

        if comment:
            ans, emocion = await responder_con_ia(user, comment, agent=current_agent)
            estado["active_emotion"] = emocion

            audio_file = DATA_DIR / "consejo_test.mp3"
            try:
                await sintetizar_audio(ans, str(audio_file), emocion, voz_override=voice)

                nombre_h = limpiar_nombre_usuario(user)
                registrar_log(f"🧪 [SANDBOX] @{user}: \"{comment}\"", "hl")
                registrar_log(f"🧪 [{current_agent.get('name')} {emocion}]: \"{ans}\"", "green")
                actualizar_overlay_video(nombre_h, comment, ans, estado_tipo="respondiendo", agent=current_agent)

                import time
                loop_time = int(time.time() * 1000)
                return web.json_response({
                    "ok": True,
                    "user": user,
                    "question": comment,
                    "answer": ans,
                    "emotion": emocion,
                    "audio_url": f"/api/audio-test?v={loop_time}"
                })
            except Exception as e:
                logger.error(f"Error generando audio sandbox: {e}")
                registrar_log(f"🧪 [{current_agent.get('name')} RESPONDE]: \"{ans}\"", "green")
                return web.json_response({"ok": True, "answer": ans, "emotion": emocion, "audio_url": None, "error": str(e)})

        return web.json_response({"ok": False})
    except Exception as e:
        logger.error(f"Error en handle_test_comment: {e}")
        return web.json_response({"ok": False, "error": str(e)})

async def handle_index(request):
    html_file = BASE_DIR / "web_dashboard.html"
    return web.FileResponse(html_file)

# ==================== MAIN ====================
async def start_dual_servers():
    app = web.Application()
    app.router.add_get("/", handle_index)
    app.router.add_get("/client", handle_index)
    app.router.add_get("/api/status", handle_status)
    app.router.add_post("/api/start", handle_start)
    app.router.add_post("/api/stop", handle_stop)
    app.router.add_get("/api/logs", handle_logs)
    app.router.add_post("/api/test-comment", handle_test_comment)
    app.router.add_get("/api/audio-test", handle_audio_test)

    # Rutas del Club de Agentes y Super Administrador
    app.router.add_post("/api/admin/login", handle_admin_login)
    app.router.add_get("/api/admin/check", handle_admin_check)
    app.router.add_post("/api/admin/change-password", handle_admin_change_pass)
    app.router.add_get("/api/agents", handle_list_agents)
    app.router.add_post("/api/agents", handle_create_agent)
    app.router.add_get("/api/agents/{id}", handle_get_agent)
    app.router.add_put("/api/agents/{id}", handle_update_agent)
    app.router.add_delete("/api/agents/{id}", handle_delete_agent)
    app.router.add_post("/api/agents/{id}/select", handle_select_agent)
    app.router.add_get("/api/agents/{id}/sale-alert", handle_sale_alert)
    app.router.add_get("/api/templates", handle_templates)
    app.router.add_get("/api/avatars", handle_list_avatars)
    app.router.add_post("/api/upload-avatar", handle_upload_avatar)
    app.router.add_post("/api/agents/{id}/avatar", handle_set_agent_avatar)

    # Servir archivos estáticos (Logo del Sensei, imágenes, audio)
    assets_dir = BASE_DIR / "assets"
    assets_dir.mkdir(exist_ok=True)

    # Sincronizar y restaurar avatares persistentes guardados en DATA_DIR / "avatars"
    data_avatars_dir = DATA_DIR / "avatars"
    data_avatars_dir.mkdir(parents=True, exist_ok=True)
    for p_img in data_avatars_dir.glob("avatar_*"):
        dest = assets_dir / p_img.name
        if not dest.exists():
            import shutil
            shutil.copy2(p_img, dest)

    app.router.add_static("/assets", assets_dir)

    async def handle_favicon(request):
        fav = assets_dir / "logo_sensei.jpg"
        if fav.exists():
            return web.FileResponse(fav)
        return web.Response(status=404)
    app.router.add_get("/favicon.ico", handle_favicon)

    runner = web.AppRunner(app)
    await runner.setup()

    port_env = int(os.environ.get("PORT", 8080))
    puertos = list(set([port_env, 8080, 3000]))

    for p in puertos:
        try:
            site = web.TCPSite(runner, "0.0.0.0", p)
            await site.start()
            registrar_log(f"Panel del Sensei listo en http://0.0.0.0:{p}")
        except Exception as e:
            registrar_log(f"Puerto {p} no disponible: {e}", "warn")

    # Mantener el servidor activo
    while True:
        await asyncio.sleep(3600)

def main():
    try:
        asyncio.run(start_dual_servers())
    except KeyboardInterrupt:
        logger.info("Servidor detenido.")

if __name__ == "__main__":
    main()
