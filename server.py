#!/usr/bin/env python3
"""
TikTok Live - Sensei del Amor y la Seducción (VPS / Coolify Headless Streaming)
Transmisión en vivo 24/7 sin OBS: Escucha preguntas de seducción, conquista,
parejas e infidelidades en TikTok, genera sabiduría con IA y responde con voz neuronal en tiempo real.
"""

import os
import re
import sys
import json
import asyncio
import time
import logging
import subprocess
import base64
from pathlib import Path
import collections
import aiohttp
from aiohttp import web

from agent_manager import (
    agent_manager,
    verify_admin_password,
    create_admin_session,
    verify_session_token,
    change_admin_password,
    AGENT_TEMPLATES
)
from perfumes_expert import obtener_sommelier_experto, buscar_en_catalogo_perfumes

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
    if env_k and not env_k.startswith("AQ."):
        return env_k.strip()
    try:
        k = base64.b64decode(DEFAULT_GEMINI_KEY_B64).decode("utf-8").strip()
        if k and not k.startswith("AQ."):
            return k
    except Exception:
        pass
    try:
        k_oa = base64.b64decode(DEFAULT_OPENAI_KEY_B64).decode("utf-8").strip()
        if k_oa and not k_oa.startswith("AQ."):
            return k_oa
    except Exception:
        pass
    return ""

def obtener_gemini_key_default():
    return obtener_ai_key_default()

# Estado del sistema
estado = {
    "is_streaming": False,
    "tiktok_username": os.environ.get("TIKTOK_USERNAME", "senseidelamor"),
    "tiktok_session_id": os.environ.get("TIKTOK_SESSION_ID", ""),
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

# ==================== SISTEMA DE MONETIZACIÓN Y PRIORIDAD VIP ====================
usuarios_vip = {}  # {usuario_lower: timestamp_expiracion}

def es_usuario_vip(usuario: str) -> bool:
    u = (usuario or "").lower().lstrip("@").strip()
    return time.time() < usuarios_vip.get(u, 0)

def registrar_usuario_vip(usuario: str, minutos: int = 15):
    u = (usuario or "").lower().lstrip("@").strip()
    if u:
        usuarios_vip[u] = time.time() + (minutos * 60)

def obtener_info_donador(user) -> dict:
    """
    Determina si un espectador es donador activo / tiene insignia de donador de TikTok (Pay Grade / Gifter Level >= 1).
    Detecta Pay Grade (Nivel 1 a 50+), Gifter Level, badges de regalo (scene 8/6),
    o presencia de insignias de apoyo en su perfil/nombre.
    """
    if not user:
        return {"es_donador": False, "nivel": 0, "tipo": None}

    # 1. Pay Grade (Nivel de donaciones acumuladas de TikTok 1-50+)
    pg = getattr(user, "pay_grade", None)
    if pg:
        lvl = getattr(pg, "level", 0) or (pg.get("level", 0) if isinstance(pg, dict) else 0)
        if lvl and lvl > 0:
            return {"es_donador": True, "nivel": lvl, "tipo": "pay_grade"}

    # 2. Gifter Level directo
    gl = getattr(user, "gifter_level", 0)
    if gl and gl > 0:
        return {"es_donador": True, "nivel": gl, "tipo": "gifter_level"}

    # 3. Badges de TikTok (scene 8 = Gifter Level, scene 6 = Top Gifter)
    badges = getattr(user, "badges", None) or getattr(user, "badge_list", None) or []
    for b in badges:
        scene = getattr(b, "badge_scene", None) or (b.get("badge_scene") if isinstance(b, dict) else None)
        if scene in (8, 6):
            lvl = getattr(b, "level", 0) or (b.get("level", 0) if isinstance(b, dict) else 0)
            return {"es_donador": True, "nivel": lvl or 1, "tipo": f"badge_scene_{scene}"}
        b_str = str(b).lower()
        if any(w in b_str for w in ["gift", "donad", "regalo", "pay_grade", "honor"]):
            return {"es_donador": True, "nivel": 1, "tipo": "badge_text"}

    # 4. Helper has_badge de TikTokLive
    if hasattr(user, "has_badge") and callable(user.has_badge):
        try:
            if user.has_badge("GIFT") or user.has_badge("GIFTER") or user.has_badge("PAY_GRADE"):
                return {"es_donador": True, "nivel": 1, "tipo": "has_badge"}
        except Exception:
            pass

    # 5. Símbolos o emojis de honor/donador en apodo
    nick = getattr(user, "nickname", "") or getattr(user, "unique_id", "") or ""
    if any(sym in nick for sym in ["👑", "💎", "🌹", "✨"]):
        return {"es_donador": True, "nivel": 1, "tipo": "simbolo_honor"}

    return {"es_donador": False, "nivel": 0, "tipo": None}

async def encolar_pregunta(usuario: str, pregunta: str, es_vip: bool = False):
    """
    Encola una pregunta para El Sensei.
    Si es_vip=True (ha donado 1 Rosa o regalo), SALTA LA FILA y se coloca de primero.
    Capacidad ampliada a 25 para no descartar preguntas legítimas de la audiencia.
    """
    global cola_preguntas
    if es_vip:
        pendientes = []
        while not cola_preguntas.empty():
            try:
                pendientes.append(cola_preguntas.get_nowait())
                cola_preguntas.task_done()
            except Exception:
                break
        await cola_preguntas.put((usuario, pregunta))
        for p in pendientes[:10]:
            await cola_preguntas.put(p)
    else:
        if cola_preguntas.qsize() >= 25:
            try:
                cola_preguntas.get_nowait()
                cola_preguntas.task_done()
            except Exception:
                pass
        await cola_preguntas.put((usuario, pregunta))


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

# ==================== POOL HTTP PERSISTENTE (MODO DIOS VELOZ DEL OESTE) ====================
_http_session = None

async def get_http_session() -> aiohttp.ClientSession:
    """Reutiliza una única sesión TCP/TLS con keep-alive para respuestas en <300ms."""
    global _http_session
    if _http_session is None or _http_session.closed:
        connector = aiohttp.TCPConnector(limit=60, keepalive_timeout=75, enable_cleanup_closed=True)
        timeout = aiohttp.ClientTimeout(total=10.0, connect=3.0)
        _http_session = aiohttp.ClientSession(connector=connector, timeout=timeout)
    return _http_session

active_tiktok_client = None

async def enviar_comentario_chat_tiktok(client, usuario: str, respuesta: str):
    """
    Envía la respuesta por escrito directamente al chat nativo de TikTok Live como soporte.
    """
    try:
        if not client or not getattr(client, "connected", False):
            return

        resp_clean = re.sub(r"\[[A-Z_]+\]", "", respuesta).strip()
        u_clean = usuario.replace("@", "").strip()
        msg_chat = f"@{u_clean} {resp_clean}"
        if len(msg_chat) > 140:
            msg_chat = msg_chat[:137] + "..."

        await client.send_room_chat(msg_chat)
        registrar_log(f"💬 [SOPORTE CHAT TIKTOK] Enviado a @{u_clean}: \"{msg_chat}\"", "green")
    except Exception as e_chat:
        err_str = str(e_chat)
        if "session" in err_str.lower() or "authenticated" in err_str.lower():
            logger.info("ℹ️ Para enviar respuestas escritas al chat de TikTok, configura tu Session ID en el panel.")
        else:
            logger.warning(f"Aviso al enviar mensaje al chat de TikTok: {e_chat}")


# ==================== CEREBRO IA: SABIDURÍA Y SEDUCCIÓN ====================
# Memoria conversacional por usuario en TikTok Live para coherencia y seguimiento de hilos
memoria_conversacion_usuarios = collections.defaultdict(lambda: collections.deque(maxlen=3))
tiempo_ultimo_comentario_usuario = {}

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

def parse_emocion_y_texto(raw: str, pregunta: str, usuario: str = "") -> tuple:
    emocion = "SABIO"
    t = raw.strip()
    if t.startswith("[") and "]" in t:
        tag, rest = t[1:].split("]", 1)
        emocion = tag.strip().upper()
        t = rest.strip()

    # Si la respuesta no leyó la pregunta al inicio, la anteponemos para que siempre se escuche
    t_clean = t.lower()
    q_words = [w for w in pregunta.lower().replace("?", "").replace("¿", "").split() if len(w) >= 4]
    menciona_pregunta = any(w in t_clean[:90] for w in q_words) or "pregunta" in t_clean[:60] or "preguntas" in t_clean[:60]
    if usuario and pregunta and not menciona_pregunta:
        t = f"{usuario} nos pregunta: «{pregunta}». {t}"

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

    # 0. RESPUESTA INSTANTÁNEA PARA SALUDOS SIMPLES (0 ms de espera para TikTok Live)
    saludos_cortos = ["hola", "buenas", "buenas noches", "buen dia", "saludos", "que tal", "hola sensei", "holaa", "como estas", "cómo estás", "como va", "volviste", "volvió", "ya volví", "saludos sensei", "buenas noches sensei"]
    p_clean = pregunta.lower().strip().rstrip(".!?¿¡")
    if p_clean in saludos_cortos or len(p_clean) <= 3:
        import random
        if agent_type == "tienda_ventas":
            return (f"¡Hola {nombre_humano}! Bienvenida a la boutique en vivo. ¿Qué aroma o producto buscas hoy?", "AMIGABLE")
        elif "perfume" in (agent.get("niche") or "").lower() or "perfume" in agent_name.lower():
            opc_perf = [
                f"¡Saludos {nombre_humano}! Un placer saludarte. Dime qué perfume usas hoy o qué fragancia buscas calificar.",
                f"¡Hola {nombre_humano}! Bienvenido al consultorio olfativo. ¿Qué aroma te tiene pensando hoy?",
                f"¡Qué tal {nombre_humano}! Pasa al templo de los aromas. ¿Buscas un perfume para conquistar o para uso diario?"
            ]
            return (random.choice(opc_perf), "SABIO")
        else:
            opc_amor = [
                f"¡Qué tal {nombre_humano}! Bienvenido al templo. Dime, ¿qué dilema de amor o conquista tienes hoy?",
                f"¡Saludos {nombre_humano}! Pasa adelante. Cuéntame tu caso de amor o desamor y te digo la verdad sin anestesia.",
                f"¡Hombre {nombre_humano}! Bienvenido al dojo del amor. Deja tu situación en el chat y la destripamos en vivo.",
                f"¡Epa {nombre_humano}! Activo en la sala. Cuéntame: ¿estás sufriendo por amor o quieres aprender a conquistar?",
                f"¡Bienvenido {nombre_humano}! Apoya la sala con dos toques a la pantalla y cuéntame qué te tiene pensando en esa persona."
            ]
            return (random.choice(opc_amor), "SABIO")

    base_prompt = agent.get("system_prompt", "").strip()
    sales_mode = agent.get("sales_mode")
    if not sales_mode:
        sales_mode = "sensei_puro" if agent_type == "consultorio" else "modo_bestia"

    # Recuperar memoria conversacional reciente con este espectador (hilo secuencial de conversación)
    import time
    ahora = time.time()
    t_prev = tiempo_ultimo_comentario_usuario.get(usuario, 0)
    if ahora - t_prev > 240:
        memoria_conversacion_usuarios[usuario].clear()

    historial_usuario = list(memoria_conversacion_usuarios[usuario])
    contexto_conversacion = ""
    if historial_usuario:
        lineas_h = []
        for prev_q, prev_a in historial_usuario:
            prev_a_clean = re.sub(r"\[[A-Z_]+\]", "", prev_a).strip()
            lineas_h.append(f"- {nombre_humano} dijo: \"{prev_q}\"")
            lineas_h.append(f"- Tú respondiste: \"{prev_a_clean}\"")
        contexto_conversacion = (
            f"\nHISTORIAL DE LA CONVERSACIÓN PREVIA CON {nombre_humano}:\n"
            + "\n".join(lineas_h)
            + f"\nREGLA OBLIGATORIA DE SEGUIMIENTO Y COHERENCIA: El nuevo comentario de {nombre_humano} es una CONTINUACIÓN de lo que acaban de hablar. SÍGUELE LA CORRIENTE CON TOTAL COHERENCIA. Si te contrapregunta, aclara, insiste o compara (ej: 'pero entre hombres y mujeres', '¿por qué?', '¿y qué hago?'), respóndele directamente sobre esa misma idea y dale un veredicto definitivo con picardía y sabiduría.\n"
        )

    def registrar_y_retornar(texto: str, emocion: str) -> tuple:
        memoria_conversacion_usuarios[usuario].append((pregunta, texto))
        tiempo_ultimo_comentario_usuario[usuario] = time.time()
        return texto, emocion

    # 1. MODO SENSEI DEL PERFUME (0% VENTAS - PURA SABIDURÍA OLFATIVA)
    if sales_mode == "sensei_puro" and ("perfume" in (agent.get("niche") or "").lower() or "perfume" in agent_name.lower() or "fragancia" in (agent.get("niche") or "").lower()):
        kb_matches = buscar_en_catalogo_perfumes(pregunta, limit=3)
        kb_text = ""
        if kb_matches:
            kb_lines = []
            for item in kb_matches:
                insp_str = f" (Inspiración/Equivalente: {item['inspiration']})" if item.get('inspiration') and item['inspiration'].lower() not in item['name'].lower() else ""
                house_str = f" | Casa: {item['house']}" if item.get('house') else ""
                notes_str = f" | Notas: {item['notes']}" if item.get('notes') else ""
                kb_lines.append(f"- {item['name']}{insp_str}{house_str}{notes_str}")
            kb_text = "\nINFORMACIÓN TÉCNICA Y NOTAS DEL CATÁLOGO (Kikluxe, LMD, Esencia y Estilo Colombia):\n" + "\n".join(kb_lines) + "\n"

        prompt = f"""{base_prompt}
Tu rol en este Live: El legendario Sensei de las Fragancias (0% VENTAS, MÁXIMA SABIDURÍA Y AUTORIDAD OLFATIVA).
{kb_text}
REGLAS DE ORO DEL SENSEI DE LOS PERFUMES (ESTRICTO):
1. Saluda al espectador con calidez y respeto usando su nombre limpio: "{nombre_humano}".
2. CERO VENTAS / TERMINANTEMENTE PROHIBIDO VENDER:
   - JAMÁS vendas, JAMÁS menciones precios, ofertas, inventario, envíos, links en biografía ni digas 'en mi boutique'.
   - Eres una autoridad independiente, respetada y con olfato de élite. Tu valor radica en educar, calificar perfumes objetivamente y elevar el estilo olfativo del espectador.
3. VEREDICTOS Y CALIFICACIONES DE MAESTRO:
   - Si preguntan por un perfume: describe sus notas sensoriales (salida, corazón y fondo), para qué ocasión sirve y califícalo sobre 10 en fijación y cumplidos.
   - Si piden recomendación: dale las mejores fragancias del mundo (nicho, árabes o diseñador) según su edad, estilo o clima con criterio imparcial.
   - Cierra siempre con una pregunta reflexiva sobre el gusto del espectador.
4. Si el espectador se ríe (jaja, jeje, xd): ríete con él con carisma y complicidad.
5. NUNCA digas que eres una IA o bot; eres Don Perfume, el Sensei de las Fragancias.
6. Al puro inicio pon la emoción entre corchetes: [SABIO], [RECOMENDACION] o [RISA].
7. Máximo 3 a 4 oraciones de alto impacto.

Pregunta del espectador en TikTok: "{pregunta}"
Respuesta del Sensei de los Perfumes:"""

    # 2. MODO BESTIA COMERCIAL (VENTA ACTIVA CON OPCIONES DE PREGUNTAS A/B)
    elif sales_mode == "modo_bestia":
        prods = agent.get("featured_products", [])
        cat_lines = []
        for p in prods:
            item_str = f"- {p['name']} ({p.get('price', '')})"
            if p.get("sizes"):
                item_str += f" | Tallas/Presentación: {p['sizes']}"
            if p.get("notes"):
                item_str += f": {p['notes']}"
            cat_lines.append(item_str)

        # Si el agente es de perfumería, incorporar referencias relevantes de la base de datos colombiana (Kikluxe, LMD, Esencia y Estilo)
        if "perfume" in (agent.get("niche") or "").lower() or "perfume" in agent_name.lower() or "fragancia" in (agent.get("niche") or "").lower():
            kb_matches = buscar_en_catalogo_perfumes(pregunta, limit=2)
            for km in kb_matches:
                if not any(km.get("name", "").lower() in cl.lower() for cl in cat_lines):
                    km_str = f"- {km['name']} ({km.get('price', '$160.000 COP')})"
                    if km.get("sizes"):
                        km_str += f" | Tallas/Presentación: {km['sizes']}"
                    if km.get("inspiration") and km["inspiration"].lower() not in km["name"].lower():
                        km_str += f" (Inspiración: {km['inspiration']})"
                    if km.get("notes"):
                        km_str += f": {km['notes']}"
                    cat_lines.append(km_str)

        cat_text = "\n".join(cat_lines) if cat_lines else "Productos exclusivos disponibles."
        cta = agent.get("call_to_action", "Pide el tuyo en el enlace de la bio.")

        prompt = f"""{base_prompt}

CATÁLOGO ACTUAL DE TU TIENDA:
{cat_text}

LLAMADO A LA ACCIÓN: {cta}

REGLAS DE VENTA EN MODO BESTIA COMERCIAL (VENTA ACTIVA CON OPCIONES DE PREGUNTAS):
1. Saluda con entusiasmo y energía usando su nombre limpio: "{nombre_humano}".
2. VENTA ACTIVA CON OPCIONES DE PREGUNTAS (PERSUASIVA, NO ABUSIVA):
   - Reconoce el producto, modelo o necesidad que menciona el cliente y conéctala con las opciones de tu catálogo.
   - TALLAS Y DISPONIBILIDAD: Si el cliente pregunta por una talla (ej: '¿tienen talla 40?', '¿tienen en 41?', '¿talla L?'), revisa las tallas exactas de tu catálogo. Si está disponible, confírmale de inmediato con energía y dile que se la apartas antes de que se agote.
   - OFRECE SIEMPRE OPCIONES ATRACTIVAS A/B AL CLIENTE para facilitar la decisión (ej: "¿Prefieres el modelo clásico A o la opción B con mayor exclusividad?", "¿Te gustaría en talla 40 o 41?", "¿Prefieres la opción individual o el paquete completo?").
   - Menciona el precio accesible y crea urgencia de inventario limitado ("quedan pocas piezas disponibles hoy").
   - Cierra con una pregunta de cierre con opciones (ej: '¿cuál de los dos prefieres?') e invita a tocar el enlace del perfil: "{cta}".
3. Si el espectador se ríe (jaja, jeje, xd): ríete con él y contagia buena vibra.
4. NUNCA digas que eres una IA o bot; eres el experto/a y presentador/a en vivo de la tienda.
5. Al puro inicio pon la emoción entre corchetes: [VENTA], [RECOMENDACION] o [RISA].
6. Máximo 3 a 4 oraciones de alto impacto para TikTok Live.

Pregunta del cliente en TikTok: "{pregunta}"
Respuesta en Modo Bestia Comercial:"""

    # 3. MODO CONSULTIVO EQUILIBRADO
    elif agent_type == "tienda_ventas" or sales_mode == "consultivo":
        prods = agent.get("featured_products", [])
        cat_lines = []
        for p in prods:
            item_str = f"- {p['name']} ({p.get('price', '')})"
            if p.get("sizes"):
                item_str += f" | Tallas/Presentación: {p['sizes']}"
            if p.get("notes"):
                item_str += f": {p['notes']}"
            cat_lines.append(item_str)

        # Si el agente es de perfumería, incorporar referencias relevantes de la base de datos colombiana
        if "perfume" in (agent.get("niche") or "").lower() or "perfume" in agent_name.lower() or "fragancia" in (agent.get("niche") or "").lower():
            kb_matches = buscar_en_catalogo_perfumes(pregunta, limit=2)
            for km in kb_matches:
                if not any(km.get("name", "").lower() in cl.lower() for cl in cat_lines):
                    km_str = f"- {km['name']} ({km.get('price', '$160.000 COP')})"
                    if km.get("sizes"):
                        km_str += f" | Tallas/Presentación: {km['sizes']}"
                    if km.get("inspiration") and km["inspiration"].lower() not in km["name"].lower():
                        km_str += f" (Inspiración: {km['inspiration']})"
                    if km.get("notes"):
                        km_str += f": {km['notes']}"
                    cat_lines.append(km_str)

        cat_text = "\n".join(cat_lines) if cat_lines else "Productos exclusivos disponibles."
        cta = agent.get("call_to_action", "Pide el tuyo en el enlace de la bio.")

        prompt = f"""{base_prompt}

CATÁLOGO ACTUAL DE TU TIENDA:
{cat_text}

LLAMADO A LA ACCIÓN: {cta}

REGLAS DE VENTA Y CONVERSIÓN EN TIKTOK LIVE (VENTA CONSULTIVA EQUILIBRADA):
1. Saluda a la persona con calidez usando su nombre limpio: "{nombre_humano}" (sin '@' ni guiones).
2. INTELIGENCIA DE VENTA Y CONVERSACIÓN (NATURAL Y CONSULTIVA):
   A) Si el espectador pregunta por COMPRA, PRECIO, ENVÍO O DISPONIBILIDAD (ej: '¿cuánto cuesta?', '¿dónde lo compro?', '¿tienen stock?', 'recomiéndame uno para comprar'):
      - Menciona el precio accesible, que lo tienes disponible con envío prioritario y cierra con el llamado a la acción: "{cta}".
   B) Si el espectador hace una pregunta de OPINIÓN, CARACTERÍSTICAS, COMPARACIÓN O CURIOSIDAD (ej: '¿qué tal esa marca?', '¿cuál dura o rinde más?', '¿es cómodo?'):
      - NO intentes venderle agresivamente ni le menciones precios o enlaces de compra de forma forzada.
      - Responde como un especialista apasionado describiendo las cualidades, materiales o sensaciones del producto.
      - CIERRA CON UNA PREGUNTA DE ENGANCHE PARA EL LIVE (ej: '¿Tú buscas algo más clásico o prefieres lo más moderno y exclusivo?', '¿Para qué uso o estilo lo necesitas?'). Esto hace que la gente comente en el live de TikTok y se queden enganchados.
3. Si el espectador se ríe (jaja, jeje, xd): ríete con él y mantén la vibra alegre y magnética.
4. NUNCA digas que eres una IA o bot; eres el experto/a en vivo de la tienda.
5. Al puro inicio pon la emoción entre corchetes: [VENTA], [RECOMENDACION], [RISA] o [SABIO].
6. Máximo 3 a 4 oraciones de alto impacto para TikTok Live.

Pregunta del cliente en TikTok: "{pregunta}"
Respuesta del Asesor en Directo:"""

    else:
        tono = "sabio, elegante, magnético y con alta autoestima" if agent.get("estilo") == "sabio_directo" else "picante, directo a la llaga y con verdades sin anestesia"
        vip_tag_prompt = f"\n⭐ ATENCIÓN VIP: {nombre_humano} es un donador VIP del live. Dale trato preferencial de honor, reconócelo como miembro distinguido del dojo y dale un consejo certero y exclusivo.\n" if es_usuario_vip(usuario) else ""
        prompt = f"""{base_prompt}
Tu estilo general: {tono}.
{vip_tag_prompt}{contexto_conversacion}
REGLAS DE ORO, COHERENCIA Y VELOCIDAD PARA TIKTOK LIVE:
1. TU ÚNICO UNIVERSO: El amor, desamor, conquista, parejas, infidelidad y dignidad.
2. PROHIBIDO SALIR DEL PERSONAJE: Jamás digas que eres IA, bot, modelo de lenguaje ni menciones tecnología.
3. COHERENCIA Y SEGUIMIENTO: Si el espectador está continuando o aclarando un comentario anterior, conéctalo de inmediato. Síguele la idea con lógica, picardía y veredicto definitivo.
4. LECTURA DE LA PREGUNTA Y CONSEJO (OBLIGATORIO):
   - Al comenzar tu respuesta, PRIMERO lee o menciona en voz alta la pregunta de "{nombre_humano}" para que toda la audiencia del Live entienda qué te preguntó (por ejemplo: "{nombre_humano} nos pregunta: «{pregunta}»...").
   - Inmediatamente después dale tu veredicto o consejo sabio, contundente y memorable en 1 o 2 oraciones de alto impacto.
5. Si el espectador se ríe ("jajaja", "xd"): ¡Ríete con él y vacílalo con gracia!
6. Al puro inicio pon la emoción: [RISA], [SABIO], [PICANTE] o [ESTOICO].
7. POLÍTICA ANTI-BLOQUEO TIKTOK (ESTRICTO): PROHIBIDO pedir regalos, rosas, monedas o dinero. TikTok bloquea y suspende transmisiones que piden regalos. En su lugar pide toques a la pantalla (likes) o dile que comente su caso.
8. MÁXIMA VARIEDAD Y CERO REPETICIÓN: Sé original, fresco e impredecible. Varía el tono, las analogías y el remate en cada caso.

Nuevo comentario de {nombre_humano} en TikTok: "{pregunta}"
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
                    "temperature": 0.7,
                    "max_tokens": 80
                }
                async with aiohttp.ClientSession() as session:
                    async with session.post(url, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=4)) as resp:
                        if resp.status == 200:
                            d = await resp.json()
                            raw_ans = d["choices"][0]["message"]["content"].strip()
                            t, emo = parse_emocion_y_texto(raw_ans, pregunta, nombre_humano)
                            return registrar_y_retornar(t, emo)
                        else:
                            err_txt = await resp.text()
                            logger.warning(f"OpenAI API HTTP {resp.status}: {err_txt}")
            except Exception as e:
                logger.warning(f"Error consultando OpenAI API: {e}")

        # Soporte para Google Gemini (Gemini Flash con respuesta ultra rápida instantánea)
        else:
            import aiohttp
            # Modelos oficiales vigentes en v1beta sin 404
            modelos_gemini = ["gemini-flash-latest", "gemini-2.5-flash", "gemini-flash-lite-latest"]
            for modelo in modelos_gemini:
                try:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent?key={api_key}"
                    payload = {
                        "contents": [{"parts": [{"text": prompt}]}],
                        "generationConfig": {
                            "temperature": 0.85,
                            "maxOutputTokens": 180
                        }
                    }
                    session = await get_http_session()
                    async with session.post(url, json=payload) as resp:
                            if resp.status == 200:
                                d = await resp.json()
                                parts = d.get("candidates", [{}])[0].get("content", {}).get("parts", [])
                                for p in parts:
                                    if "text" in p and p["text"].strip():
                                        # Auto-reparar la clave del agente para futuras consultas
                                        if agent.get("gemini_api_key") != api_key:
                                            agent["gemini_api_key"] = api_key
                                            agent_manager.save_agents()
                                        t, emo = parse_emocion_y_texto(p["text"].strip(), pregunta, nombre_humano)
                                        return registrar_y_retornar(t, emo)
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
        t, emo = obtener_sommelier_experto(usuario, pregunta, agent)
        return registrar_y_retornar(t, emo)

    # 2. Agente del Amor / Seducción
    elif "amor" in nicho or "seduccion" in nicho or "seducción" in nicho or "pareja" in nicho or "sensei" in nombre_ag:
        t, emo = obtener_consejo_amor_sensei(usuario, pregunta)
        return registrar_y_retornar(t, emo)

    # 3. Agente Personalizado creado desde cero por el usuario
    else:
        t, emo = generar_respuesta_agente_personalizado(usuario, pregunta, agent)
        return registrar_y_retornar(t, emo)

def obtener_consejo_amor_sensei(usuario: str, pregunta: str) -> tuple:
    """Oráculo de Sabiduría Local de Seducción y Relaciones con Respuestas Rotativas y Dinámicas."""
    import random
    q = pregunta.lower().strip()
    nombre = limpiar_nombre_usuario(usuario)

    # Blindaje contra preguntas técnicas / fuera de nicho (palabras completas exactas)
    palabras_q = set(re.findall(r"\b[a-záéíóúñ]+\b", q))
    tech_words = {"ia", "robot", "bot", "python", "servidor", "codigo", "código", "algoritmo", "prompt", "programado"}
    if tech_words.intersection(palabras_q) or any(f in q for f in ["inteligencia artificial", "como estas hecho", "cómo estás hecho", "quien te creo", "quién te creó", "que modelo eres"]):
        respuestas_tech = [
            f"Escucha con atención, {nombre}: en este dojo no venimos a hablar de cables ni de códigos; aquí venimos a sanar el corazón y aprender a conquistar con dignidad. Cuéntame sobre tu caso amoroso y déjate de rodeos.",
            f"¡Hombre {nombre}! El único algoritmo que enseñamos aquí es el del amor propio y la seducción magnética. Déjame tu duda con esa persona y te digo la verdad sin anestesia.",
            f"Atento, {nombre}: no te distraigas con preguntas técnicas. La verdadera maestría está en saber cuándo retirarse y cuándo dar el paso en el amor. ¿Qué te tiene desvelado hoy?"
        ]
        return (random.choice(respuestas_tech), "SABIO")

    # Risa / Humor local
    if any(k in q for k in ["jaja", "jeje", "xd", "chiste", "gracioso", "broma"]):
        respuestas_risa = [
            f"¡Jajaja! Ay, {nombre}, te ríes para no llorar, pero la verdad es clara: si estás aquí preguntando es porque esa persona te mueve el piso. ¡Párate firme, ríete del pasado y que el chiste no sea tu dignidad!",
            f"¡Jajaja! {nombre}, la risa es la mejor terapia para sacudirse el desamor, pero después de reírte hay que tomar decisiones firmes. Cuéntame el chisme completo para darte el veredicto.",
            f"¡Qué risa, {nombre}! En este dojo nos reímos de las derrotas de ayer porque mañana salimos a conquistar como reyes. ¡Arriba ese ánimo!"
        ]
        return (random.choice(respuestas_risa), "RISA")

    # 1. Salir de la Friendzone
    elif any(k in q for k in ["friendzone", "amigo", "amiga", "hermano", "zona de amigos"]):
        respuestas_fz = [
            f"{nombre} nos pregunta: «{pregunta}»... Para salir de la friendzone debes romper el papel de consejero incondicional: toma distancia, deja de estar disponible a toda hora y demuestra intención clara sin miedo al rechazo.",
            f"{nombre} pregunta cómo salir de la zona de amigos... Hermano, el que se queda de amigo esperando que ella se dé cuenta, solo ve cómo otro se lleva el premio. Desaparece un tiempo, sube tu valor y vuelve con intención, o retírate con honor.",
            f"{nombre} consulta sobre la friendzone... Escucha: si te trata como a su mejor amiga, es porque tú aceptaste ese contrato. Rompe ese pacto hoy mismo; la escasez genera deseo, la disponibilidad excesiva genera desinterés."
        ]
        return (random.choice(respuestas_fz), "SABIO")

    # 2. Cómo hablarle a la crush / Iniciar conversación
    elif any(k in q for k in ["hablarle", "iniciar", "acercarme", "que le digo", "qué le digo", "romper el hielo"]):
        respuestas_hablar = [
            f"{nombre} nos pregunta: «{pregunta}»... Nunca empieces con un soso 'hola, qué haces'. Haz una observación divertida sobre su entorno o un cumplido a su actitud; la naturalidad y el buen humor siempre conquistan.",
            f"{nombre} quiere saber cómo romper el hielo... Lo que atrae no son frases ensayadas de internet, sino la seguridad al decirlas. Sé directo, hazle una pregunta interesante que desafíe su mente y mantén contacto visual relajado.",
            f"{nombre} nos consulta cómo hablarle... Entra con una vibra alegre, hazla reír en los primeros 10 segundos y luego retira un poco tu atención; la intriga es el imán más potente de la seducción."
        ]
        return (random.choice(respuestas_hablar), "PICANTE")

    # 3. Responder historias de Instagram / WhatsApp
    elif any(k in q for k in ["historia", "storie", "responderle", "instagram", "mensaje", "escribirle"]):
        respuestas_historias = [
            f"{nombre} nos pregunta: «{pregunta}»... Jamás respondas con un fueguito o un 'qué hermosa'. Comenta algo ingenioso que abra debate o hazle una pregunta que despierte su curiosidad; dale una razón real para querer contestarte.",
            f"{nombre} pregunta qué responder a sus historias... Un hombre de alto valor no adula en vano. Si subió una foto de comida o viaje, haz un comentario pícaro o una broma sobre sus gustos; haz que se ría y quiera justificarse.",
            f"{nombre} duda qué escribirle... Si solo reaccionas con emojis eres uno más en su bandeja de entrada. Desafíala con ingenio y déjala esperando tu próxima respuesta; el misterio atrae."
        ]
        return (random.choice(respuestas_historias), "PICANTE")

    # 4. Generar misterio y atracción
    elif any(k in q for k in ["misterio", "atraer", "atractivo", "interesar", "gustarle"]):
        respuestas_misterio = [
            f"{nombre} nos pregunta: «{pregunta}»... El secreto de la seducción es no entregar todo el libro en la primera página. Deja las charlas en su punto más alto y ten metas apasionantes; lo que es escaso se valora, lo regalado aburre.",
            f"{nombre} busca generar misterio... Quien cuenta toda su vida en dos horas mata la curiosidad. Ten proyectos propios, no contestes al segundo y haz que descubrirte sea un premio para la otra persona.",
            f"{nombre} nos pide claves de atracción... La atracción nace de la polaridad: ten tu propio camino, no mendigues validación y sonríe con la seguridad de quien sabe perfectamente lo que vale."
        ]
        return (random.choice(respuestas_misterio), "SABIO")

    # 5. Primera cita
    elif any(k in q for k in ["primera cita", "cita", "invitarla", "invitarlo", "adonde", "a dónde"]):
        respuestas_cita = [
            f"{nombre} nos pregunta: «{pregunta}»... Para tu primera cita, evita cenas formales y aburridas. Elige un plan dinámico donde puedan caminar, reírse y compartir un café; el objetivo no es impresionarle con dinero, sino conectar con tu personalidad.",
            f"{nombre} nos consulta sobre la primera cita... Lleva a tu crush a un lugar interactivo donde la conversación fluya sin presión. Escucha el 70% del tiempo, habla el 30% y déjala con ganas de una segunda vuelta.",
            f"{nombre} pregunta por la cita ideal... Haz que se sienta cómoda y segura. No te esfuerces de más por agradar; actúa como si ya fuera tu cómplice de aventuras y la chispa se encenderá sola."
        ]
        return (random.choice(respuestas_cita), "PICANTE")

    # 6. Saber si le gustas / Señales
    elif any(k in q for k in ["le gusto", "señal", "señales", "interesada", "interesado"]):
        respuestas_senales = [
            f"{nombre} nos pregunta: «{pregunta}»... Quien tiene interés verdadero busca pretextos para hablarte y facilita verse. Si tienes que dudar o siempre hay una excusa para no salir, la respuesta ya es un no.",
            f"{nombre} busca señales de interés... El interés se nota, el desinterés se nota todavía más. Si te busca, te hace preguntas y te mira con atención, avanza; si siempre tarda o es cortante, retira tu atención de inmediato.",
            f"{nombre} nos pregunta si le gusta... La regla de oro del dojo: el interés genuino es mutuo y fluido. Nunca persigas a quien camina despacio cuando tú estás corriendo por verlo."
        ]
        return (random.choice(respuestas_senales), "ESTOICO")

    # 7. Infidelidades
    elif any(k in q for k in ["infiel", "engañó", "engaño", "cuerno", "traicion", "traición", "otra"]):
        respuestas_infiel = [
            f"{nombre} nos pregunta: «{pregunta}»... La infidelidad no es un error de cálculo ni un tropiezo, es una decisión consciente. Quien te traiciona una vez te demuestra que no respeta tu valor; ten dignidad y sal de ahí.",
            f"{nombre} consulta sobre infidelidad... Perdonar una traición casi siempre es comprar un boleto para que te la vuelvan a hacer con mayor confianza. Cierra esa puerta, sana tu amor propio y busca a alguien leal.",
            f"{nombre} nos habla de una traición... Mi hermano, la lealtad es un valor no negociable. Si rompen tu confianza, no discutas ni mendigues explicaciones; retírate en silencio y que tu ausencia sea su mayor lección."
        ]
        return (random.choice(respuestas_infiel), "ESTOICO")

    # 8. Volver con el ex
    elif any(k in q for k in ["volver", "ex", "regresar", "extraño", "bloqueo", "bloquear"]):
        respuestas_ex = [
            f"{nombre} nos pregunta: «{pregunta}»... Volver con tu ex es como comprar tu propia ropa usada esperando que huela a nuevo. Recuerda exactamente por qué terminó la historia y aplica contacto cero absoluto.",
            f"{nombre} pregunta si debe volver con su ex... El basurero pasa a recoger los desechos, no a llevarlos de nuevo a la sala. Mira hacia adelante; hay 8 mil millones de personas en el planeta para quedarse estancado en el pasado.",
            f"{nombre} consulta si regresar con su ex... Si vuelven sin que ninguno haya cambiado de verdad, el final ya está escrito en la misma página de antes. Date la oportunidad de conocer a alguien que sí te valore desde el día uno."
        ]
        return (random.choice(respuestas_ex), "SABIO")

    # 9. Dejar en visto / Ghosting
    elif any(k in q for k in ["visto", "ignora", "escribe", "tarda", "frio", "fría"]):
        respuestas_visto = [
            f"{nombre} nos pregunta: «{pregunta}»... La falta de interés también es una respuesta clara y rotunda. Quien te quiere te busca, quien no, te pone pretextos. No mendigues la atención ni el tiempo de nadie.",
            f"{nombre} pregunta qué hacer si lo dejan en visto... Si te deja en visto, tú déjalo en el pasado. No vuelvas a escribir para reclamar; el silencio absoluto es la respuesta más elegante y poderosa que existe.",
            f"{nombre} duda qué hacer ante la frialdad... La atención no se ruega ni se exige. Si baja la intensidad, tú bajas el volumen por completo y enfocas tu energía en ti mismo."
        ]
        return (random.choice(respuestas_visto), "ESTOICO")

    # 10. Los "Casi Algo"
    elif any(k in q for k in ["casi algo", "formalizar", "amigos con derecho", "etiqueta"]):
        respuestas_casialgo = [
            f"{nombre} nos pregunta: «{pregunta}»... Si ya llevan meses y te dice que 'no busca nada serio', lo que en realidad te está diciendo es que no lo busca contigo. Retira tu cariño de donde no hay compromiso.",
            f"{nombre} consulta sobre su casi algo... Los 'casi algo' duelen porque se idealiza lo que pudo ser. No te quedes en el limbo de la incertidumbre; o te dan tu lugar como corresponde o que siga su camino.",
            f"{nombre} pregunta por su situación de casi algo... No regales beneficios de pareja a quien solo te ofrece migajas de atención. Exige claridad o da un paso al costado con orgullo."
        ]
        return (random.choice(respuestas_casialgo), "SABIO")

    else:
        respuestas_generales = [
            f"{nombre} nos pregunta: «{pregunta}»... En el amor y en la conquista, tu mayor atractivo siempre será tu seguridad y tu amor propio. Camina firme y nunca te conformes con migajas.",
            f"{nombre} nos comparte su caso: «{pregunta}»... La regla suprema de este dojo es muy simple: donde no puedas amar con dignidad y reciprocidad, no te demores. Valórate primero.",
            f"{nombre} nos plantea este dilema: «{pregunta}»... El que sabe lo que vale no compite por atención; atrae por presencia y repele por respeto propio. Pon límites claros hoy mismo.",
            f"{nombre} nos consulta: «{pregunta}»... Para que alguien te admire afuera, primero tienes que respetarte tú adentro. Toma la iniciativa con calma y que tu paz mental sea innegociable.",
            f"{nombre} nos dice: «{pregunta}»... Si una situación te quita la tranquilidad más de lo que te aporta alegría, la respuesta ya la tienes en el pecho. Da el salto con coraje."
        ]
        return (random.choice(respuestas_generales), "SABIO")

def generar_respuesta_agente_personalizado(usuario: str, pregunta: str, agent: dict) -> tuple:
    """Responde de forma profesional y personalizada según el nicho, productos y reglas de cualquier agente creado desde cero."""
    nombre = limpiar_nombre_usuario(usuario)
    ag_name = agent.get("name", "Asesor").split("·")[0].strip()
    nicho = agent.get("niche", "nuestra especialidad")
    cta = agent.get("call_to_action", "Toca el enlace de nuestro perfil para pedir el tuyo.")
    sales_mode = agent.get("sales_mode", "modo_bestia")
    prods = agent.get("featured_products", [])
    
    q_low = pregunta.lower()

    # Risa / Humor
    if any(k in q_low for k in ["jaja", "jeje", "xd", "chiste", "broma", "risa"]):
        return (f"¡Jajaja! Saludos {nombre}, me encanta tu energía. En cuanto a lo que preguntas sobre {nicho}, aquí en vivo estamos respondiendo cada duda. {cta}", "RISA")

    # 1. Búsqueda de productos específicos en el catálogo del agente (Calzado, Ropa, etc.)
    for p in prods:
        p_name = p.get("name", "").lower()
        palabras_prod = [w for w in re.findall(r'\b[a-zA-Z0-9]{3,}\b', p_name)]
        if any(w in q_low for w in palabras_prod) or p_name in q_low:
            precio_txt = f"por solo {p.get('price')}" if p.get("price") else ""
            tallas_txt = f" Tallas disponibles: {p.get('sizes')}." if p.get("sizes") else ""
            notes_txt = f" Destaca por: {p.get('notes')}." if p.get("notes") else ""
            if sales_mode == "sensei_puro":
                return (f"¡Excelente elección, {nombre}! El modelo {p['name']} es de lo más cotizado en {nicho}.{tallas_txt}{notes_txt} ¿Para qué tipo de uso o estilo lo estás buscando?", "SABIO")
            else:
                return (f"¡Gran elección, {nombre}! Tenemos disponible {p['name']} {precio_txt}.{tallas_txt}{notes_txt} Quedan pocas unidades en inventario. ¿Te aparto tu talla de una vez? {cta}", "VENTA")

    # 1.1 Si pregunta específicamente por una talla (ej: "talla 40", "talla 41", "talla 42", "tienen en 40", "talla M")
    talla_match = re.search(r'\b(?:talla|número|numero)\s*([a-zA-Z0-9]+)\b|\b(?:en|tienen)\s*([3-4][0-9])\b', q_low)
    if talla_match:
        talla_pedida = talla_match.group(1) or talla_match.group(2)
        prods_con_talla = [p for p in prods if talla_pedida in str(p.get("sizes", ""))]
        if prods_con_talla:
            p_ej = prods_con_talla[0]
            precio_txt = f"por solo {p_ej.get('price')}" if p_ej.get("price") else ""
            return (f"¡Sí, {nombre}! En talla {talla_pedida} tenemos disponible {p_ej['name']} {precio_txt}. Quedan muy pocos pares en stock. Toca el enlace de mi perfil para apartar la tuya antes de que se agote. {cta}", "VENTA")

    # 2. Si pregunta por precios o catálogo en general
    if any(k in q_low for k in ["precio", "cuanto", "cuánto", "vale", "comprar", "tienen", "catalogo", "catálogo", "modelos", "tallas", "zapatos", "calzado", "disponible"]):
        if prods:
            ejemplos = ", ".join([f"{p['name']} ({p.get('price', '')})" for p in prods[:2]])
            return (f"¡Hola {nombre}! En nuestro catálogo tenemos referencias disponibles como {ejemplos} con despacho inmediato. ¿Qué modelo o talla buscas para confirmarte? {cta}", "VENTA")
    
    # 3. Respuesta general inteligente
    palabras = [w for w in re.findall(r'\b[a-zA-ZáéíóúÁÉÍÓÚñÑ]{4,}\b', pregunta) if w.lower() not in ["como", "para", "donde", "cuando", "porque", "tienes", "quiero", "puedo", "hacer", "cual", "cuanto", "cuanto", "hola"]]
    tema = f"sobre '{palabras[0]}'" if palabras else ""

    return (f"Hola {nombre}. Como experto en {nicho}, es una excelente consulta {tema}. Te confirmo que en nuestro catálogo ofrecemos productos y soluciones de máxima calidad garantizada. {cta}", "SABIO")

# ==================== SÍNTESIS DE VOZ (TTS) ====================
async def sintetizar_audio(texto: str, salida_path: str, emocion: str = "SABIO", voz_override: str = None):
    import edge_tts
    import re
    current_agent = agent_manager.get_active_agent() or {}
    voz = voz_override or current_agent.get("voice") or estado.get("voice", "es-MX-JorgeNeural")

    # Limpieza total para pronunciación 100% fluida y blindaje contra NoAudioReceived:
    # 1. Quitar cualquier '@' y nombres de usuario para que Edge-TTS no deletree
    texto_voz = re.sub(r"@([a-zA-ZáéíóúÁÉÍÓÚñÑ]+)[\w\.]*", r"\1", texto)
    texto_voz = texto_voz.replace("@", "")
    texto_voz = texto_voz.replace("_", " ")
    # 2. Filtrar emojis y símbolos extraños que rompen Edge-TTS
    texto_voz = re.sub(r'[\U00010000-\U0010ffff]', '', texto_voz)
    texto_voz = re.sub(r'[\u2600-\u27bf]', '', texto_voz)
    # 3. Mantener caracteres de texto válidos
    texto_voz = re.sub(r'[^\w\s.,!?;:¿¡áéíóúÁÉÍÓÚñÑ]', '', texto_voz)
    texto_voz = re.sub(r"\s+", " ", texto_voz).strip()

    if not texto_voz:
        texto_voz = "Escucha con atención, esto transformará tu perspectiva."

    # Velocidad y tono estables para conservar fielmente la identidad de la voz sin cambios bruscos
    rate = "+10%"
    pitch = "+0Hz"

    tmp_path = Path(salida_path).with_suffix(".tmp.mp3")
    generado_ok = False

    # Conservar fielmente la voz configurada por el usuario, reintentando con la MISMA voz
    for intento in range(2):
        try:
            comunicador = edge_tts.Communicate(texto_voz, voz, rate=rate, pitch=pitch)
            await asyncio.wait_for(comunicador.save(str(tmp_path)), timeout=6.0)
            if tmp_path.exists() and tmp_path.stat().st_size > 500:
                tmp_path.replace(salida_path)
                generado_ok = True
                break
        except Exception as e:
            logger.warning(f"Intento {intento+1} sintetizando con voz fija ({voz}): {e}")
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except Exception:
                    pass
            await asyncio.sleep(0.3)

    if not generado_ok:
        logger.error(f"Error generando audio para: '{texto_voz[:35]}...'")

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

    avatar_type = agent.get("avatar_type", "image")
    video_idle_rel = (agent.get("video_idle") or "").lstrip("/")
    video_file = BASE_DIR / video_idle_rel if video_idle_rel else None
    has_video_loop = (avatar_type == "video_loop") and video_file and video_file.exists()

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

    overlay_file = DATA_DIR / "live_overlay.txt"
    if not overlay_file.exists():
        actualizar_overlay_video("", "", estado_tipo="esperando", agent=agent)

    font_path = asegurar_fuente_tipografica()
    font_param = f":fontfile={font_path}" if font_path else ""

    if has_video_loop:
        # Transmisión con Presentador Humano en Video Loop
        cmd = [
            "ffmpeg",
            "-re",
            "-stream_loop", "-1",
            "-i", str(video_file),
            # Audio en tiempo real por tubería stdin (Voz + Música de fondo)
            "-f", "s16le", "-ar", "44100", "-ac", "2", "-i", "pipe:0"
        ]
        filter_complex = (
            # 1. Marco semitransparente superior para visibilidad de marca
            f"[0:v]drawbox=x=0:y=0:w=720:h=180:color=0x060911@0.75:t=fill,"
            f"drawbox=x=30:y=30:w=660:h=120:color={theme_hex}@0.6:t=2,"
            f"drawtext={font_param[1:] + ':' if font_param else ''}text='{b_title}':fontcolor={accent_hex}:fontsize=24:x=(w-text_w)/2:y=55,"
            f"drawtext={font_param[1:] + ':' if font_param else ''}text='{b_sub}':fontcolor=0x00f0ff:fontsize=15:x=(w-text_w)/2:y=95[bg];"
            # 2. Caja holográfica de consulta en vivo y vitrina en la zona inferior
            f"[bg]drawbox=x=56:y=766:w=608:h=268:color={theme_hex}@0.4:t=fill,"
            "drawbox=x=60:y=770:w=600:h=260:color=0x060911@0.88:t=fill,"
            "drawbox=x=60:y=770:w=600:h=260:color=0x00f0ff@0.7:t=2,"
            f"drawtext=textfile=data/live_overlay.txt:reload=1{font_param}:fontcolor={accent_hex}:fontsize=17:line_spacing=6:x=85:y=795,"
            # 3. Llamado a la acción inferior con borde láser
            "drawbox=x=56:y=1056:w=608:h=73:color=0x00f0ff@0.3:t=fill,"
            "drawbox=x=60:y=1060:w=600:h=65:color=0x0c121f@0.88:t=fill,"
            f"drawbox=x=60:y=1060:w=600:h=65:color={theme_hex}@0.85:t=2,"
            f"drawtext={font_param[1:] + ':' if font_param else ''}text='{cta}':fontcolor={accent_hex}:fontsize=16:x=(w-text_w)/2:y=1083"
        )
        cmd.extend(["-filter_complex", filter_complex])
    else:
        cmd = [
            "ffmpeg",
            "-re",
            "-f", "lavfi",
            # Fondo dinámico del nicho del agente
            "-i", f"color=c={bg_hex}:s=720x1280:r=30",
            # Audio en tiempo real por tubería stdin (Voz + Música de fondo)
            "-f", "s16le", "-ar", "44100", "-ac", "2", "-i", "pipe:0"
        ]
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

async def encolar_saludo_inmediato(usuario: str, nombre_humano: str, agent: dict):
    """Encola un saludo instantáneo y cálido cuando un espectador entra al Live."""
    saludos_frases = [
        f"¡Qué tal {nombre_humano}! Bienvenido al dojo del amor. Deja tu dilema en los comentarios.",
        f"Saludos {nombre_humano}. Bienvenido al templo. ¿Qué dilema de pareja traes hoy?",
        f"¡Hola {nombre_humano}! Un placer tenerte en la sala. Cuéntame tu caso en el chat.",
        f"Bienvenido {nombre_humano}. Estás en el dojo del Sensei. Deja tu caso y te daré mi veredicto sincero.",
        f"¡Qué energía {nombre_humano}! Bienvenido al live. Deja tu pregunta y la analizamos en directo."
    ]
    import random
    frase = random.choice(saludos_frases)
    await cola_preguntas.put((usuario, f"👋 SALUDO: {frase}"))

async def worker_preguntas():
    while estado["is_streaming"]:
        try:
            usuario, pregunta = await cola_preguntas.get()
        except asyncio.CancelledError:
            break

        try:
            nombre_humano = limpiar_nombre_usuario(usuario)
            current_agent = agent_manager.get_active_agent() or {}

            es_saludo = pregunta.startswith("👋 SALUDO:")
            es_regalo = pregunta.startswith("🎁 REGALO VIP:")
            es_bienvenida_donador = pregunta.startswith("👑 BIENVENIDA DONADOR VIP:")
            es_frase_viral = pregunta.startswith("📣 FRASE VIRAL:")
            es_intervencion_manual = pregunta.startswith("🎙️ INTERVENCION_MANUAL:")
            vip_activo = es_usuario_vip(usuario) or es_regalo or es_bienvenida_donador or es_intervencion_manual

            if es_saludo:
                frase_saludo = pregunta.replace("👋 SALUDO:", "").strip()
                estado["active_user"] = f"👋 {nombre_humano}"
                estado["active_question"] = "¡Acaba de entrar al Live! 👋"
                estado["active_answer"] = frase_saludo
                estado["active_emotion"] = "AMIGABLE"
                estado["status_phase"] = "respondiendo"
                actualizar_overlay_video(nombre_humano, "¡Nuevo espectador!", frase_saludo, estado_tipo="respondiendo", agent=current_agent)
                respuesta = frase_saludo
                emocion = "AMIGABLE"

            elif es_intervencion_manual:
                raw_payload = pregunta.replace("🎙️ INTERVENCION_MANUAL:", "").strip()
                if ":::" in raw_payload:
                    preg_real, resp_real = raw_payload.split(":::", 1)
                else:
                    preg_real = "Caso en directo"
                    resp_real = raw_payload
                preg_real = preg_real.strip() or "Consulta en vivo"
                resp_real = resp_real.strip()

                estado["active_user"] = nombre_humano
                estado["active_question"] = preg_real
                estado["status_phase"] = "respondiendo"
                actualizar_overlay_video(nombre_humano, preg_real, estado_tipo="respondiendo", agent=current_agent)
                respuesta = resp_real
                emocion = "PICANTE" if any(k in resp_real.lower() for k in ["jajaja", "infiel", "celos", "tóxica", "toxica", "amigo", "ex"]) else "SABIO"

            elif es_bienvenida_donador:
                nivel_str = pregunta.replace("👑 BIENVENIDA DONADOR VIP:", "").strip()
                registrar_usuario_vip(usuario, minutos=30)
                estado["active_user"] = f"👑 {nombre_humano} [{nivel_str}]"
                estado["active_question"] = "✨ ¡BIENVENIDO DE HONOR AL DOJO! ✨"
                estado["status_phase"] = "respondiendo"
                actualizar_overlay_video(nombre_humano, f"✨ {nivel_str}", estado_tipo="respondiendo", agent=current_agent)

                import random
                frases_saludo_elegante = [
                    f"¡Atención a toda la sala del dojo! Saludo con los más altos honores a nuestro distinguido {nombre_humano}, portador del {nivel_str} en TikTok. Es un verdadero privilegio contar con alguien de tu lealtad y calibre aquí. Siéntete como en casa, déjame tu dilema en el chat y con gusto te daré mi veredicto.",
                    f"Damos la bienvenida con alfombra roja a {nombre_humano}. Tu {nivel_str} te precede como un miembro de honor en este templo. La caballerosidad, el estilo y la lealtad brillan en ti. Cuéntame tu situación de amor o pareja en los comentarios y la analizamos.",
                    f"El dojo se viste de gala con la llegada de {nombre_humano}. Tu presencia de {nivel_str} engalana este live. Bienvenido mi hermano, déjame tu consulta amorosa en el chat y te daré mi respuesta sincera."
                ]
                respuesta = random.choice(frases_saludo_elegante)
                emocion = "EMOCIONADO"

            elif es_frase_viral:
                frase_viral_txt = pregunta.replace("📣 FRASE VIRAL:", "").strip()
                estado["active_user"] = "⛩️ SABIDURÍA DEL SENSEI"
                estado["active_question"] = "🔥 REFLEXIÓN EN VIVO"
                estado["status_phase"] = "respondiendo"
                actualizar_overlay_video("El Sensei", "Reflexión del Sensei", estado_tipo="respondiendo", agent=current_agent)
                respuesta = frase_viral_txt
                emocion = "PICANTE" if any(k in frase_viral_txt.lower() for k in ["jajaja", "esposa", "cogiendola", "infiel", "celos"]) else "SABIO"

            elif es_regalo:
                regalo_desc = pregunta.replace("🎁 REGALO VIP:", "").strip()
                registrar_usuario_vip(usuario, minutos=20)
                estado["active_user"] = f"👑 {nombre_humano}"
                estado["active_question"] = "✨ ¡GRACIAS POR EL APOYO! ✨"
                estado["status_phase"] = "respondiendo"
                actualizar_overlay_video(nombre_humano, f"🎁 {regalo_desc}", estado_tipo="respondiendo", agent=current_agent)

                import random
                frases_agradecimiento = [
                    f"¡Alabado sea el dojo sagrado! Mi total gratitud a {nombre_humano} por ese hermoso apoyo. Eres un miembro de honor en este templo. Déjame tu caso en los comentarios y te responderé con toda la dedicación.",
                    f"¡Qué gran honor para este consultorio! Agradezco profundamente a {nombre_humano} por ese generoso detalle. Tu respeto y lealtad brillan en esta sala. Escribe tu dilema y lo analizamos en vivo.",
                    f"¡Poder y magnetismo para {nombre_humano}! Gracias de corazón por respaldar este espacio de sabiduría. Es un verdadero privilegio tenerte aquí en el dojo. Cuéntame tu situación en el chat."
                ]
                respuesta = random.choice(frases_agradecimiento)
                emocion = "EMOCIONADO"
            else:
                if vip_activo:
                    estado["active_user"] = f"👑 {nombre_humano} [VIP]"
                    estado["active_question"] = f"⭐ {pregunta}"
                else:
                    estado["active_user"] = nombre_humano
                    estado["active_question"] = pregunta
                estado["status_phase"] = "pensando"

                actualizar_overlay_video(nombre_humano, pregunta, estado_tipo="pensando", agent=current_agent)

                tipo_ag = current_agent.get("type", "consultorio")
                tag_icon = "👑 VIP" if vip_activo else ("🛍️ Venta" if tipo_ag == "tienda_ventas" else "🏮 Consulta")
                registrar_log(f"{tag_icon} de {nombre_humano}: \"{pregunta}\"", "hl")

                try:
                    respuesta, emocion = await responder_con_ia(usuario, pregunta, agent=current_agent)
                except Exception as e_ia:
                    logger.error(f"Error en motor IA: {e_ia}. Activando oráculo local de contingencia.")
                    respuesta, emocion = obtener_consejo_amor_sensei(usuario, pregunta)

            # Garantizar que El Sensei SIEMPRE lea la pregunta del usuario en voz alta para que la audiencia entienda:
            resp_clean = (respuesta or "").strip()
            nombre_lower = nombre_humano.lower()

            if not es_regalo and not es_bienvenida_donador and not es_frase_viral and not es_saludo and not es_intervencion_manual:
                # Comprobar si la IA ya leyó la pregunta en voz alta dentro de su respuesta generada
                preg_fragmento = pregunta.lower()[:20].strip()
                ia_ya_leyo = (preg_fragmento in resp_clean.lower()) or (f"{nombre_lower} nos" in resp_clean.lower()) or (f"{nombre_lower} pregunta" in resp_clean.lower()) or ("pregunta:" in resp_clean.lower())

                if not ia_ya_leyo:
                    preg_lectura = pregunta.strip()
                    if len(preg_lectura) > 85:
                        preg_lectura = preg_lectura[:82] + "..."
                    import random
                    intro_lectura = random.choice([
                        f"{nombre_humano} nos dice: «{preg_lectura}».",
                        f"{nombre_humano} pregunta: «{preg_lectura}».",
                        f"Atención al dilema de {nombre_humano}: «{preg_lectura}»."
                    ])
                    if nombre_lower in resp_clean.lower():
                        respuesta = f"{intro_lectura} {resp_clean}"
                    else:
                        respuesta = f"{intro_lectura} Escucha bien: {resp_clean}"
                else:
                    if nombre_lower not in resp_clean.lower() and nombre_lower != "amigo":
                        respuesta = f"Atento {nombre_humano}: {resp_clean}"
            else:
                if nombre_lower not in resp_clean.lower() and nombre_lower != "amigo" and not es_frase_viral and not es_saludo and not es_intervencion_manual:
                    import random
                    prefijos = [
                        f"Escucha bien, {nombre_humano}:",
                        f"Atento {nombre_humano}:",
                        f"Oye {nombre_humano}:"
                    ]
                    respuesta = f"{random.choice(prefijos)} {resp_clean}"

            estado["active_answer"] = respuesta
            estado["active_emotion"] = emocion
            estado["status_phase"] = "respondiendo"

            tag_resp = "🌸 Boutique" if tipo_ag == "tienda_ventas" else f"📿 {current_agent.get('name', 'Sensei')}"
            registrar_log(f"{tag_resp} [{emocion}] responde a {nombre_humano}: \"{respuesta}\"", "green")

            # Proyectar consejo/venta en tiempo real en la caja holográfica del video de TikTok
            actualizar_overlay_video(nombre_humano, pregunta, respuesta, estado_tipo="respondiendo", agent=current_agent)

            audio_tmp = DATA_DIR / "consejo_sensei.mp3"
            try:
                voz_activa = current_agent.get("voice") or estado["voice"]
                await sintetizar_audio(respuesta, str(audio_tmp), emocion, voz_override=voz_activa)
                registrar_log(f"Voz ({voz_activa}) sintetizada.", "hl")

                # Notificar nueva versión de audio para Browser Source (TikTok LIVE Studio / OBS)
                import time
                estado["audio_version"] = int(time.time() * 1000)

                # Estimar la duración del habla con voz ágil (+10% velocidad: ~16 caracteres por segundo)
                duracion_estimada = max(1.8, len(respuesta) / 18.0)

                # Solo si hay un stream RTMP FFmpeg activo procesamos PCM con subproceso
                if ffmpeg_process and ffmpeg_process.poll() is None:
                    cmd_tts = [
                        "ffmpeg", "-y",
                        "-i", str(audio_tmp),
                        "-f", "s16le", "-ar", "44100", "-ac", "2",
                        "-filter:a", "volume=1.15",
                        "pipe:1"
                    ]
                    res_tts = await asyncio.to_thread(subprocess.run, cmd_tts, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
                    duracion_audio = max(2.5, len(res_tts.stdout) / (44100 * 2 * 2)) if res_tts.returncode == 0 else duracion_estimada
                    buffer_voz_pcm.extend(res_tts.stdout)
                    estado["is_speaking"] = True
                    registrar_log(f"Respondiendo con voz en vivo en TikTok sobre la música de fondo.", "green")

                    start_w = time.time()
                    while len(buffer_voz_pcm) > 0 and estado["is_streaming"] and (time.time() - start_w) < duracion_audio + 1.5:
                        await asyncio.sleep(0.15)
                else:
                    # Transmisión vía TikTok LIVE Studio / Browser Source
                    estado["is_speaking"] = True
                    registrar_log(f"Respondiendo en TikTok LIVE Studio con audio sincronizado.", "green")
                    await asyncio.sleep(duracion_estimada)

                estado["is_speaking"] = False
                estado["status_phase"] = "leyendo"

            except Exception as e:
                estado["is_speaking"] = False
                registrar_log(f"Error procesando voz en vivo: {e}", "err")

            # 1. Soporte en el chat nativo de TikTok: enviar la respuesta por escrito al usuario
            if active_tiktok_client and not es_regalo:
                asyncio.create_task(enviar_comentario_chat_tiktok(active_tiktok_client, usuario, respuesta))

            # 2. Transición "Veloz del Oeste / Modo Dios":
            # Si hay preguntas acumuladas en cola, pasar de inmediato (0.05s) para responder al siguiente usuario sin pausas
            if not cola_preguntas.empty():
                await asyncio.sleep(0.05)
            else:
                # Si no hay más preguntas, mantener la respuesta brevemente en pantalla como soporte (3s)
                estado["status_phase"] = "soporte_escrito"
                start_soporte = time.time()
                while cola_preguntas.empty() and (time.time() - start_soporte) < 3.0 and estado["is_streaming"]:
                    await asyncio.sleep(0.15)

                if cola_preguntas.empty():
                    estado["status_phase"] = "esperando"
                    actualizar_overlay_video("", "", estado_tipo="esperando", agent=current_agent)

        except Exception as e_proc:
            logger.error(f"Error en worker_preguntas procesando comentario: {e_proc}")
        finally:
            tiempo_ultima_actividad_comentario = time.time()
            cola_preguntas.task_done()

# ==================== AUTO-ENGANCHE EN TIEMPOS MUERTOS ====================
tiempo_ultima_actividad_comentario = time.time()

FRASES_ENGANCHE_AMOR = [
    "¡Atención dojo! Si tu pareja te esconde el celular o tu casi algo te dejó en visto, deja tu caso en los comentarios. El Sensei te dirá la verdad sin anestesia.",
    "Apoya la sala con tus dos toques a la pantalla y cuéntame tu dilema. Si estás sufriendo por amor, aquí te devolvemos la dignidad de golpe.",
    "¿Sabías que entre más te demores en tener a tu futura esposa más duran disfrutándola otros? Jajaja. Despierta, papá, deja tu caso en los comentarios.",
    "A veces insistimos donde ya nos demostraron con hechos que no somos prioridad. ¿Cuál es tu caso? Escríbelo en el chat y abramos los ojos.",
    "¿Sientes que eres la segunda opción de alguien? La dignidad masculina no se mendiga. Escribe tu dilema y lo destripamos en vivo.",
    "¿Dudas si esa persona de verdad te quiere o solo te busca cuando se aburre? Deja tu caso en los comentarios y te daré mi veredicto sin filtros.",
    "Toca la pantalla dos veces para activar el dojo y comparte este live con ese amigo que sigue rogándole a la ex.",
    "El amor correspondido da paz, no noches en vela. Si tu relación te genera ansiedad, cuéntamelo en el chat y te doy la medicina correcta."
]

FRASES_ENGANCHE_PERFUMES = [
    "Si buscas un perfume que deje huella, un aroma árabe de alta duración o un clon de lujo para hoy, déjame en los comentarios qué estilo buscas y te asesoro en vivo.",
    "¿Quieres saber cuál es el perfume que más cumplidos genera o cuál dura más de 10 horas en piel? Escríbeme tu duda en el chat y te recomiendo la joya perfecta.",
    "En nuestra boutique tenemos fragancias exclusivas disponibles con despacho hoy. Déjame en los comentarios tu duda olfativa y te respondemos en directo."
]

ultima_frase_enganche = ""

async def auto_enganche_tiempo_muerto_loop():
    """
    Cuando hay tiempo muerto prolongado en el Live (>55 segundos sin comentarios),
    El Sensei toma la palabra en vivo con su voz para animar a los espectadores a comentar
    sin repetir la misma frase consecutiva.
    """
    global tiempo_ultima_actividad_comentario, ultima_frase_enganche
    while estado["is_streaming"]:
        await asyncio.sleep(6)
        if not estado["is_streaming"]:
            break

        # Si hay preguntas en cola o el Sensei está respondiendo a un espectador, aplazar
        if not cola_preguntas.empty() or estado.get("is_speaking") or estado.get("status_phase") in ["pensando", "respondiendo"]:
            tiempo_ultima_actividad_comentario = time.time()
            continue

        current_agent = agent_manager.get_active_agent() or {}
        tipo_ag = current_agent.get("type", "consultorio")
        nicho = (current_agent.get("niche") or "").lower()

        # Si han pasado más de 55 segundos de silencio en el Live
        if time.time() - tiempo_ultima_actividad_comentario >= 55:
            import random
            frases_custom = current_agent.get("frases_enganche") or []
            if isinstance(frases_custom, str):
                frases_custom = [f.strip() for f in frases_custom.splitlines() if f.strip()]

            pool = frases_custom or (FRASES_ENGANCHE_PERFUMES if ("perfume" in nicho or tipo_ag == "tienda_ventas") else FRASES_ENGANCHE_AMOR)
            candidatas = [f for f in pool if f != ultima_frase_enganche]
            frase = random.choice(candidatas) if candidatas else (random.choice(pool) if pool else "")
            if not frase:
                continue
            ultima_frase_enganche = frase

            emocion = "PICANTE" if any(k in frase.lower() for k in ["jajaja", "esposa", "infiel", "celos", "casi algo"]) else "SABIO"

            registrar_log(f"📣 [LLAMADO EN VIVO]: \"{frase}\"", "hl")
            tiempo_ultima_actividad_comentario = time.time()

            audio_tmp = DATA_DIR / "consejo_sensei.mp3"
            try:
                voz_activa = current_agent.get("voice") or estado["voice"]
                await sintetizar_audio(frase, str(audio_tmp), emocion, voz_override=voz_activa)

                # Si durante la síntesis entró un comentario real de un usuario, darle paso inmediato
                if not cola_preguntas.empty():
                    continue

                estado["active_user"] = "EN VIVO"
                estado["active_question"] = "❤️ TOCA LA PANTALLA · DEJA TU CASO"
                estado["active_answer"] = frase
                estado["active_emotion"] = emocion
                estado["status_phase"] = "respondiendo"
                estado["is_speaking"] = True

                import time as t_mod
                estado["audio_version"] = int(t_mod.time() * 1000)

                duracion_estimada = max(3.0, len(frase) / 16.0)

                if ffmpeg_process and ffmpeg_process.poll() is None:
                    cmd_tts = [
                        "ffmpeg", "-y",
                        "-i", str(audio_tmp),
                        "-f", "s16le", "-ar", "44100", "-ac", "2",
                        "-filter:a", "volume=1.15",
                        "pipe:1"
                    ]
                    res_tts = await asyncio.to_thread(subprocess.run, cmd_tts, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
                    duracion_audio = max(3.0, len(res_tts.stdout) / (44100 * 2 * 2)) if res_tts.returncode == 0 else duracion_estimada
                    buffer_voz_pcm.extend(res_tts.stdout)
                    start_w = time.time()
                    while len(buffer_voz_pcm) > 0 and estado["is_streaming"] and (time.time() - start_w) < duracion_audio + 1.0:
                        await asyncio.sleep(0.15)
                else:
                    await asyncio.sleep(duracion_estimada)

            except Exception as e_eng:
                logger.warning(f"Aviso en auto-enganche: {e_eng}")
            finally:
                estado["is_speaking"] = False
                if estado.get("status_phase") == "respondiendo" and estado.get("active_user") == "EN VIVO":
                    estado["status_phase"] = "esperando"
                    estado["active_user"] = ""
                    estado["active_question"] = ""
                    estado["active_answer"] = ""
                    current_agent = agent_manager.get_active_agent() or {}
                    actualizar_overlay_video("", "", estado_tipo="esperando", agent=current_agent)
                tiempo_ultima_actividad_comentario = time.time()

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
                estado["last_sale_alert"] = alerta
                estado["status_phase"] = "venta_alerta"
                actualizar_overlay_video(estado_tipo="venta_alerta", agent=current_agent)
                registrar_log(alerta["mensaje"], "green")
                await asyncio.sleep(12)
                estado["last_sale_alert"] = None
                if cola_preguntas.empty() and len(buffer_voz_pcm) == 0:
                    estado["status_phase"] = "esperando"
                    actualizar_overlay_video("", "", estado_tipo="esperando", agent=current_agent)

# ==================== CLIENTE TIKTOK LIVE ====================
historial_comentarios_timestamps = {}

async def escuchar_tiktok():
    from TikTokLive import TikTokLiveClient
    from TikTokLive.events import CommentEvent, ConnectEvent, DisconnectEvent, GiftEvent, JoinEvent

    while estado["is_streaming"]:
        current_agent = agent_manager.get_active_agent() or {}
        usuario = (current_agent.get("tiktok_username") or estado.get("tiktok_username", "")).replace("@", "").strip()
        if not usuario:
            await asyncio.sleep(3)
            continue

        client = None
        # Tiempo de conexión: se descarta el paquete de sincronización inicial en solo 1.2s
        import time
        tiempo_conexion = time.time()
        ignorar_buffer_hasta = tiempo_conexion + 1.2

        try:
            client = TikTokLiveClient(unique_id=usuario)

            # Vincular session_id para responder por escrito directamente en el chat en vivo
            session_id = (current_agent.get("tiktok_session_id") or estado.get("tiktok_session_id") or os.environ.get("TIKTOK_SESSION_ID", "")).strip()
            if session_id:
                try:
                    client._web.set_session(session_id, None)
                    registrar_log("🔑 TikTok Session ID vinculado: Respuestas por escrito activadas en el chat.", "green")
                except Exception as e_sid:
                    logger.warning(f"Aviso configurando TikTok session_id: {e_sid}")

            global active_tiktok_client
            active_tiktok_client = client
            saludos_donadores_recientes = {}

            @client.on(ConnectEvent)
            async def on_connect(event: ConnectEvent):
                registrar_log(f"✅ ¡Conectado al Live de TikTok de @{usuario} ({current_agent.get('name')})!", "green")
                registrar_log("🔥 En vivo: Escuchando comentarios nuevos en tiempo real.", "green")

            usuarios_saludados_recientes = {}

            @client.on(JoinEvent)
            async def on_join(event: JoinEvent):
                try:
                    if time.time() < ignorar_buffer_hasta:
                        return
                    user = getattr(event, "user", None)
                    if not user:
                        return
                    u = getattr(user, "unique_id", "") or ""
                    if not u:
                        return
                    u_key = u.lower().strip()
                    if u_key == usuario.lower().strip():
                        return  # No saludarse a sí mismo (creador del Live)

                    nombre_h = limpiar_nombre_usuario(u)
                    if nombre_h.lower() == "amigo" and hasattr(user, "nickname") and user.nickname:
                        nombre_nick = limpiar_nombre_usuario(user.nickname)
                        if nombre_nick.lower() != "amigo":
                            nombre_h = nombre_nick

                    ahora = time.time()
                    info_donador = obtener_info_donador(user)
                    es_donador = info_donador.get("es_donador", False)

                    # Cooldown de 90 segundos por usuario para no spamear si reconecta
                    if ahora - usuarios_saludados_recientes.get(u_key, 0) < 90:
                        return
                    usuarios_saludados_recientes[u_key] = ahora
                    if len(usuarios_saludados_recientes) > 300:
                        usuarios_saludados_recientes.clear()

                    estado["last_joined_user"] = nombre_h
                    estado["last_joined_ts"] = int(ahora * 1000)

                    if es_donador:
                        nivel = info_donador.get("nivel", 1) or 1
                        registrar_usuario_vip(u, minutos=30)
                        registrar_log(f"👑 ¡DONADOR ENTRANDO AL LIVE! @{u} (Nivel {nivel})", "green")
                        msg_saludo = f"👑 BIENVENIDA DONADOR VIP: Nivel {nivel}"
                        await encolar_pregunta(u, msg_saludo, es_vip=True)
                    else:
                        registrar_log(f"👋 ¡Nuevo conectado! @{u} ({nombre_h}) entró al Live", "green")
                        # Saludar verbalmente si la cola no está saturada
                        if cola_preguntas.qsize() < 3:
                            await encolar_saludo_inmediato(u, nombre_h, current_agent)
                except Exception as e_join:
                    logger.warning(f"Aviso procesando join en TikTok: {e_join}")

            @client.on(GiftEvent)
            async def on_gift(event: GiftEvent):
                try:
                    # Descartar volcado inicial
                    if time.time() < ignorar_buffer_hasta:
                        return

                    # Si el usuario sigue en racha (combo de regalos), esperar a que termine la racha
                    if getattr(event, "streaking", False):
                        return

                    u = event.user.unique_id
                    nombre_h = limpiar_nombre_usuario(u)

                    regalo_nombre = "Rosa"
                    if hasattr(event, "gift") and event.gift:
                        regalo_nombre = getattr(event.gift, "name", None) or getattr(event.gift, "describe", "Regalo")

                    repeticion = getattr(event, "repeat_count", 1) or 1
                    diamantes = 1
                    if hasattr(event, "gift") and event.gift:
                        diamantes = getattr(event.gift, "diamond_count", 1) or 1

                    total_diamantes = diamantes * repeticion
                    registrar_log(f"🎁 ¡REGALO RECIBIDO! @{u} envió {repeticion}x {regalo_nombre} ({total_diamantes} 💎)", "green")

                    # Asignar pase VIP de 20 minutos al donador
                    registrar_usuario_vip(u, minutos=20)

                    # Inyectar al frente de la cola con prioridad VIP absoluta
                    msg_regalo = f"🎁 REGALO VIP: {repeticion}x {regalo_nombre}"
                    await encolar_pregunta(u, msg_regalo, es_vip=True)
                except Exception as e_gift:
                    logger.warning(f"Aviso procesando regalo de TikTok: {e_gift}")


            @client.on(CommentEvent)
            async def on_comment(event: CommentEvent):
                try:
                    # Descartar el volcado de paquetes iniciales de TikTok (<1.2s)
                    if time.time() < ignorar_buffer_hasta:
                        return

                    u = event.user.unique_id
                    c = event.comment.strip()
                    if not c or len(c) < 2:
                        return

                    c_low = c.lower().strip()

                    # 1. Filtro estricto: Descartar eventos de unión emitidos por TikTok como mensajes de chat
                    frases_join = [
                        "se unió", "se unio", "joined", "gracias a las publicaciones", 
                        "gracias a la publicación", "gracias a la publicacion", "se ha unido"
                    ]
                    if any(fj in c_low for fj in frases_join):
                        u_key = u.lower().strip()
                        if u_key != usuario.lower().strip():
                            ahora_j = time.time()
                            if ahora_j - usuarios_saludados_recientes.get(u_key, 0) >= 90:
                                usuarios_saludados_recientes[u_key] = ahora_j
                                nombre_h = limpiar_nombre_usuario(u)
                                if hasattr(event.user, "nickname") and event.user.nickname:
                                    n_nick = limpiar_nombre_usuario(event.user.nickname)
                                    if n_nick.lower() != "amigo":
                                        nombre_h = n_nick
                                estado["last_joined_user"] = nombre_h
                                estado["last_joined_ts"] = int(ahora_j * 1000)
                                if cola_preguntas.qsize() < 3:
                                    await encolar_saludo_inmediato(u, nombre_h, current_agent)
                        return

                    # 2. Filtro estricto: Descartar eventos sociales de likes, shares y follow
                    frases_sociales = [
                        "le dio me gusta", "dio me gusta", "me gusta al live",
                        "compartió el live", "compartio el live", "compartió", "compartio", 
                        "ha compartido", "envió una rosa", "envio una rosa", "envió un regalo", 
                        "envio un regalo", "siguió al creador", "siguio al creador", 
                        "comenzó a seguir", "comenzo a seguir", "te sigue"
                    ]
                    if any(fs in c_low for fs in frases_sociales):
                        return

                    # Filtro anti-duplicados inteligente por tiempo (5 segundos para evitar ecos de red)
                    ahora = time.time()
                    clave_comentario = f"{u.lower()}:{c.lower()}"
                    if clave_comentario in historial_comentarios_timestamps:
                        if ahora - historial_comentarios_timestamps[clave_comentario] < 5.0:
                            return
                    historial_comentarios_timestamps[clave_comentario] = ahora
                    if len(historial_comentarios_timestamps) > 200:
                        historial_comentarios_timestamps = {k: v for k, v in historial_comentarios_timestamps.items() if ahora - v < 60.0}

                    info_donador = obtener_info_donador(event.user)
                    if info_donador.get("es_donador"):
                        registrar_usuario_vip(u, minutos=30)

                    vip_activo = es_usuario_vip(u) or info_donador.get("es_donador")
                    if vip_activo:
                        lvl_tag = f" [DONADOR NIVEL {info_donador.get('nivel', 1)}]" if info_donador.get("es_donador") else " [VIP]"
                        registrar_log(f"👑 [CONSULTA{lvl_tag}] de @{u}: \"{c}\"", "green")
                    else:
                        registrar_log(f"📥 Comentario en vivo de @{u}: \"{c}\"", "hl")

                    await encolar_pregunta(u, c, es_vip=vip_activo)
                except Exception as e:
                    logger.warning(f"Aviso procesando comentario de TikTok: {e}")

            @client.on(DisconnectEvent)
            async def on_disconnect(event: DisconnectEvent):
                global active_tiktok_client
                active_tiktok_client = None
                registrar_log(f"⚠️ Conexión de TikTokLive en pausa para @{usuario}. Reconectando...", "warn")

            # process_connect_events=False: IGNORA comentarios históricos viejos y solo toma los nuevos en vivo
            await client.connect(process_connect_events=False)
        except asyncio.CancelledError:
            break
        except Exception as e:
            err_msg = str(e)
            if "UserOfflineError" in err_msg or "offline" in err_msg.lower():
                registrar_log(f"⚠️ TikTokLive: @{usuario} figura como OFFLINE en TikTok. Si tu live está en otra cuenta, cámbiala en Configuración y pulsa 'Iniciar Transmisión'. Reintentando en 8s...", "warn")
                await asyncio.sleep(8)
            else:
                registrar_log(f"Conexión TikTokLive (@{usuario}): {err_msg}. Reintentando en 3s...", "warn")
                await asyncio.sleep(3)
        finally:
            active_tiktok_client = None
            if client and getattr(client, "connected", False):
                try:
                    await client.disconnect()
                except Exception:
                    pass

# ==================== GUARDIÁN / WATCHDOG ANTI-DESCONEXIÓN ====================
async def tiktok_watchdog_loop():
    """
    Guardián activo para transmisiones largas (2+ horas):
    1. Si el WebSocket de TikTok se desconecta o la tarea muere, la reconecta limpiamente.
    2. Si la pantalla se congela en 'respondiendo' o 'pensando' por más de 22 segundos sin hablar, la resetea a 'esperando'.
    3. Si el worker de preguntas muere, lo levanta de inmediato.
    """
    global tiktok_task, worker_task, enganche_task, active_tiktok_client
    ultimo_estado_fase = ""
    tiempo_en_misma_fase = time.time()
    tiempo_sin_conexion_tiktok = 0

    while estado.get("is_streaming"):
        await asyncio.sleep(10)
        if not estado.get("is_streaming"):
            break

        # A) Watchdog Anti-Congelamiento de Pantalla:
        fase_actual = estado.get("status_phase", "esperando")
        if fase_actual in ["respondiendo", "pensando"]:
            if fase_actual == ultimo_estado_fase:
                tiempo_transcurrido = time.time() - tiempo_en_misma_fase
                if tiempo_transcurrido > 22 and not estado.get("is_speaking", False):
                    registrar_log(f"🛡️ [WATCHDOG]: Pantalla descongelada tras {int(tiempo_transcurrido)}s inactiva en '{fase_actual}'. Restaurando a espera.", "warn")
                    estado["status_phase"] = "esperando"
                    estado["is_speaking"] = False
                    estado["active_user"] = ""
                    estado["active_question"] = ""
                    estado["active_answer"] = ""
                    current_agent = agent_manager.get_active_agent() or {}
                    actualizar_overlay_video("", "", estado_tipo="esperando", agent=current_agent)
                    tiempo_en_misma_fase = time.time()
            else:
                ultimo_estado_fase = fase_actual
                tiempo_en_misma_fase = time.time()
        else:
            ultimo_estado_fase = fase_actual
            tiempo_en_misma_fase = time.time()

        # B) Watchdog de Resucitación de Tareas Principales:
        if worker_task is None or worker_task.done():
            registrar_log("🛡️ [WATCHDOG]: Tarea worker_preguntas restaurada.", "warn")
            worker_task = asyncio.create_task(worker_preguntas())

        if enganche_task is None or enganche_task.done():
            enganche_task = asyncio.create_task(auto_enganche_tiempo_muerto_loop())

        # C) Watchdog de Conexión TikTok Live:
        esta_conectado = active_tiktok_client is not None and getattr(active_tiktok_client, "connected", False)
        if not esta_conectado:
            tiempo_sin_conexion_tiktok += 10
            if tiempo_sin_conexion_tiktok >= 25:
                registrar_log("🛡️ [WATCHDOG]: TikTok no reporta conexión activa (>25s). Reiniciando socket...", "warn")
                if tiktok_task and not tiktok_task.done():
                    try:
                        tiktok_task.cancel()
                    except Exception:
                        pass
                active_tiktok_client = None
                tiktok_task = asyncio.create_task(escuchar_tiktok())
                tiempo_sin_conexion_tiktok = 0
        else:
            tiempo_sin_conexion_tiktok = 0

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
    try:
        if not is_super_admin(request):
            return web.json_response({"ok": False, "error": "Solo el Super Administrador puede editar agentes"}, status=403)
        agent_id = request.match_info.get("id")
        data = await request.json()
        ok = agent_manager.update_agent(agent_id, data)
        if ok and agent_id == agent_manager.active_agent_id:
            ag = agent_manager.get_active_agent()
            actualizar_overlay_video("", "", estado_tipo="esperando", agent=ag)
            registrar_log(f"💾 Configuración guardada y sincronizada para '{ag.get('name')}'", "green")
        return web.json_response({"ok": ok})
    except Exception as e:
        logger.error(f"Error en handle_update_agent: {e}")
        return web.json_response({"ok": False, "error": str(e)}, status=500)

async def handle_test_gifter_join(request):
    """
    Simula la entrada de un donador VIP (con insignia de nivel) al directo.
    """
    try:
        data = await request.json()
    except Exception:
        data = {}
    usuario = (data.get("user") or "SsEBbAS Lion").strip()
    nivel = data.get("level", 4)
    if not estado.get("is_streaming"):
        estado["is_streaming"] = True

    registrar_usuario_vip(usuario, minutos=30)
    registrar_log(f"👑 [SIMULADOR]: Donador VIP @{usuario} (Nivel {nivel}) entra al live.", "green")
    msg_saludo = f"👑 BIENVENIDA DONADOR VIP: Nivel {nivel}"
    await encolar_pregunta(usuario, msg_saludo, es_vip=True)
    return web.json_response({"ok": True, "user": usuario, "level": nivel})

async def handle_trigger_viral_hook(request):
    """
    Fuerza al Sensei a decir una de las frases virales programadas de inmediato.
    """
    try:
        data = await request.json()
    except Exception:
        data = {}
    frase_custom = (data.get("phrase") or "").strip()
    current_agent = agent_manager.get_active_agent() or {}
    if not frase_custom:
        frases = current_agent.get("frases_enganche") or FRASES_ENGANCHE_AMOR
        if isinstance(frases, str):
            frases = [f.strip() for f in frases.splitlines() if f.strip()]
        import random
        frase_custom = random.choice(frases) if frases else "¡Atención dojo! Deja tu dilema en los comentarios."

    if not estado.get("is_streaming"):
        estado["is_streaming"] = True

    msg_viral = f"📣 FRASE VIRAL: {frase_custom}"
    await encolar_pregunta("El Sensei", msg_viral, es_vip=True)
    return web.json_response({"ok": True, "phrase": frase_custom})

async def handle_manual_speak(request):
    """
    Permite al creador intervenir en tiempo real haciéndose pasar por El Sensei:
    Escribe el usuario, la pregunta y el texto exacto a decir con la voz del Sensei.
    """
    try:
        data = await request.json()
    except Exception:
        data = {}
    usuario = (data.get("user") or "amigo").strip().replace("@", "")
    pregunta = (data.get("question") or "Consulta en directo").strip()
    respuesta = (data.get("answer") or "").strip()
    if not respuesta:
        return web.json_response({"ok": False, "error": "La respuesta a decir no puede estar vacía"}, status=400)

    if not estado.get("is_streaming"):
        estado["is_streaming"] = True

    msg_manual = f"🎙️ INTERVENCION_MANUAL:{pregunta}:::{respuesta}"
    await encolar_pregunta(usuario, msg_manual, es_vip=True)
    registrar_log(f"🎙️ [INTERVENCIÓN MANUAL]: Hablando como Sensei para @{usuario}: \"{respuesta}\"", "hl")
    return web.json_response({"ok": True, "user": usuario, "question": pregunta, "answer": respuesta})

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
        if ag.get("voice"):
            estado["voice"] = ag["voice"]
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
    is_speaking = estado.get("is_speaking", False) or len(buffer_voz_pcm) > 0
    return web.json_response({
        **current_agent,
        "is_streaming": estado["is_streaming"],
        "is_speaking": is_speaking,
        "status_phase": estado.get("status_phase", "esperando"),
        "audio_version": estado.get("audio_version", 0),
        "active_agent_id": agent_manager.active_agent_id,
        "active_user": estado.get("active_user", ""),
        "active_emotion": estado.get("active_emotion", "SABIO"),
        "active_question": estado.get("active_question", ""),
        "active_answer": estado.get("active_answer", ""),
        "last_sale_alert": estado.get("last_sale_alert", None),
        "is_admin": is_super_admin(request)
    })

ventas_task = None
enganche_task = None
watchdog_task = None

async def handle_start(request):
    global ffmpeg_process, tiktok_task, worker_task, streamer_task, ventas_task, enganche_task, watchdog_task, active_tiktok_client

    data = await request.json()
    current_agent = agent_manager.get_active_agent() or {}

    if data.get("tiktok_username"):
        clean_user = data["tiktok_username"].replace("@", "").strip()
        current_agent["tiktok_username"] = clean_user
        estado["tiktok_username"] = clean_user
    if "tiktok_session_id" in data:
        current_agent["tiktok_session_id"] = data["tiktok_session_id"]
        estado["tiktok_session_id"] = data["tiktok_session_id"]
    if data.get("rtmp_url"): current_agent["rtmp_url"] = data["rtmp_url"]
    if data.get("stream_key"): current_agent["stream_key"] = data["stream_key"]
    if data.get("voice"): current_agent["voice"] = data["voice"]
    if data.get("estilo"): current_agent["estilo"] = data["estilo"]
    if data.get("gemini_api_key"): current_agent["gemini_api_key"] = data["gemini_api_key"]
    if data.get("avatar"): current_agent["avatar"] = data["avatar"]

    agent_manager.save_agents()

    # Cancelar tareas activas previas para asegurar socket fresco y sin duplicidad
    for t in [tiktok_task, worker_task, streamer_task, enganche_task, watchdog_task, ventas_task]:
        if t and not t.done():
            try:
                t.cancel()
            except Exception:
                pass
    if active_tiktok_client and getattr(active_tiktok_client, "connected", False):
        try:
            await active_tiktok_client.disconnect()
        except Exception:
            pass
    active_tiktok_client = None

    rtmp = (current_agent.get("rtmp_url") or "").strip().rstrip("/")
    sk = (current_agent.get("stream_key") or "").strip()

    # Si el usuario ingresó un RTMP real de TikTok, iniciar FFmpeg directo
    es_rtmp_real = bool(rtmp and sk and not ("127.0.0.1" in rtmp or "localhost" in rtmp or sk == "****"))

    estado["is_streaming"] = True
    historial_comentarios_timestamps.clear()
    while not cola_preguntas.empty():
        try:
            cola_preguntas.get_nowait()
            cola_preguntas.task_done()
        except Exception:
            break

    if es_rtmp_real:
        rtmp_completo = f"{rtmp}/{sk}"
        try:
            ffmpeg_process = iniciar_proceso_ffmpeg(rtmp_completo, agent=current_agent)
            streamer_task = asyncio.create_task(audio_streamer_loop())
            registrar_log(f"Transmisión RTMP directa de '{current_agent.get('name')}' iniciada en TikTok.", "green")
        except Exception as e:
            registrar_log(f"Error iniciando FFmpeg RTMP: {e}", "warn")
    else:
        registrar_log(f"Modo TikTok LIVE Studio / Pantalla Live iniciada para @{current_agent.get('tiktok_username')}.", "green")

    try:
        worker_task = asyncio.create_task(worker_preguntas())
        tiktok_task = asyncio.create_task(escuchar_tiktok())
        enganche_task = asyncio.create_task(auto_enganche_tiempo_muerto_loop())
        watchdog_task = asyncio.create_task(tiktok_watchdog_loop())
        if current_agent.get("type") == "tienda_ventas":
            ventas_task = asyncio.create_task(simulador_ventas_loop())

        return web.json_response({"ok": True, "mode": "rtmp" if es_rtmp_real else "studio"})
    except Exception as e:
        return web.json_response({"ok": False, "error": str(e)})

async def handle_stop(request):
    global ffmpeg_process, tiktok_task, worker_task, streamer_task, ventas_task, enganche_task, watchdog_task
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
    if enganche_task:
        enganche_task.cancel()
    if watchdog_task:
        watchdog_task.cancel()
        watchdog_task = None

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

async def handle_nudge(request):
    """
    ⚡ Pellizcar al Sensei (Forzar Respuesta en Vivo):
    Permite al administrador inyectar una pregunta de un usuario específico cuando el Sensei no ha contestado
    o cuando la cola se ha quedado atrás.
    Descongela inmediatamente la pantalla y le da prioridad VIP para que El Sensei responda en vivo YA.
    """
    global worker_task, enganche_task
    try:
        data = await request.json()
        user = (data.get("user") or "").strip().lstrip("@") or "espectador"
        comment = (data.get("comment") or "").strip()
        if not comment:
            return web.json_response({"ok": False, "error": "Por favor escribe la pregunta o caso del espectador."}, status=400)

        # Si el stream no estaba marcado como activo, activarlo
        if not estado.get("is_streaming"):
            estado["is_streaming"] = True

        # Descongelar pantalla si estaba en auto-enganche o trabada
        estado["is_speaking"] = False
        estado["status_phase"] = "pensando"

        # Asegurar que el worker de preguntas esté activo
        if worker_task is None or worker_task.done():
            worker_task = asyncio.create_task(worker_preguntas())

        # Registrar al usuario como VIP temporal para máxima prioridad
        registrar_usuario_vip(user, minutos=15)
        registrar_log(f"⚡ [PELLIZCO AL SENSEI]: Administrador fuerza respuesta en vivo para @{user}: \"{comment}\"", "green")

        # Inyectar al frente de la cola con prioridad VIP absoluta
        await encolar_pregunta(user, comment, es_vip=True)

        return web.json_response({
            "ok": True,
            "user": user,
            "comment": comment,
            "message": f"¡Sensei pellizcado con éxito! Respondiendo a @{user} en vivo ahora mismo."
        })
    except Exception as e:
        logger.error(f"Error en handle_nudge: {e}")
        return web.json_response({"ok": False, "error": str(e)}, status=500)

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

        enviar_al_live = data.get("enviar_al_live", False)
        if enviar_al_live:
            if not estado["is_streaming"]:
                return web.json_response({"ok": False, "error": "Debes hacer clic primero en 'INICIAR TRANSMISIÓN' para proyectar preguntas al Live en vivo."})
            if comment:
                registrar_log(f"🚀 Pregunta inyectada al Live de @{user}: \"{comment}\"", "hl")
                await encolar_pregunta(user, comment, es_vip=False)
                return web.json_response({
                    "ok": True,
                    "enviado_al_live": True,
                    "user": user,
                    "question": comment,
                    "message": "Pregunta inyectada con éxito al Live en vivo. El Sensei la responderá en pantalla y voz en segundos."
                })

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

async def handle_live_screen(request):
    html_file = BASE_DIR / "live_screen.html"
    return web.FileResponse(html_file)

async def handle_live_audio(request):
    audio_file = DATA_DIR / "consejo_sensei.mp3"
    if audio_file.exists() and audio_file.stat().st_size > 500:
        return web.FileResponse(audio_file, headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Content-Type": "audio/mpeg"
        })
    # Fallback si existe audio de respaldo para no romper la reproducción
    for fb_name in ["test_voice2.mp3", "test_speed.mp3", "test_voice.mp3"]:
        fb_p = DATA_DIR / fb_name
        if fb_p.exists() and fb_p.stat().st_size > 500:
            return web.FileResponse(fb_p, headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Content-Type": "audio/mpeg"
            })
    return web.Response(status=404)

# ==================== MAIN ====================
async def start_dual_servers():
    app = web.Application()
    app.router.add_get("/", handle_index)
    app.router.add_get("/client", handle_index)
    app.router.add_get("/live", handle_live_screen)
    app.router.add_get("/live-screen", handle_live_screen)
    app.router.add_get("/overlay", handle_live_screen)
    app.router.add_get("/api/live-audio", handle_live_audio)
    app.router.add_get("/api/status", handle_status)
    app.router.add_post("/api/start", handle_start)
    app.router.add_post("/api/stop", handle_stop)
    app.router.add_get("/api/logs", handle_logs)
    app.router.add_post("/api/test-comment", handle_test_comment)
    app.router.add_post("/api/test-gifter-join", handle_test_gifter_join)
    app.router.add_post("/api/trigger-viral-hook", handle_trigger_viral_hook)
    app.router.add_post("/api/manual-speak", handle_manual_speak)
    app.router.add_post("/api/nudge", handle_nudge)
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
    
    # Asegurar que el Sensei del Amor tenga siempre asignado 'senseidelamor' por defecto
    try:
        ag_sensei = agent_manager.get_agent("sensei-amor")
        if ag_sensei and not ag_sensei.get("tiktok_username"):
            ag_sensei["tiktok_username"] = os.environ.get("TIKTOK_USERNAME", "senseidelamor")
            ag_sensei["call_to_action"] = "💬 Escribe tu caso en los comentarios y apoya con dos toques a la pantalla ❤️"
            ag_sensei["banner_subtitle"] = "Conquista · Infidelidad · Parejas · Amor Propio"
            agent_manager.save_agents()
    except Exception as e_init:
        logger.warning(f"Aviso verificando usuario default: {e_init}")
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
