#!/usr/bin/env python3
"""
Club de Agentes - Gestor Multi-Agente y Sistema de Alquiler para TikTok Live
Permite crear, configurar, alquilar y gestionar múltiples agentes especializados
(ej. El Sensei del Amor, Boutiques de Perfumes con ventas simuladas, Tarot, Fitness).
"""

import os
import json
import uuid
import secrets
import hashlib
import logging
from pathlib import Path

logger = logging.getLogger("AgentManager")
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
AGENTS_FILE = DATA_DIR / "agents.json"
AUTH_FILE = DATA_DIR / "auth.json"

# Contraseña maestra de Super Administrador por defecto (cambiable desde panel o variable de entorno)
DEFAULT_ADMIN_PASS = os.environ.get("ADMIN_PASSWORD", "Ax1004906.")

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

def init_auth():
    if not AUTH_FILE.exists():
        with open(AUTH_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "admin_hash": hash_password(DEFAULT_ADMIN_PASS),
                "sessions": []
            }, f, indent=2)

def verify_admin_password(password: str) -> bool:
    init_auth()
    try:
        with open(AUTH_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("admin_hash") == hash_password(password)
    except Exception as e:
        logger.error(f"Error verificando password: {e}")
        return password == DEFAULT_ADMIN_PASS

def create_admin_session() -> str:
    init_auth()
    token = secrets.token_hex(24)
    try:
        with open(AUTH_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        sessions = data.get("sessions", [])
        sessions.append(token)
        # Mantener max 20 sesiones activas
        data["sessions"] = sessions[-20:]
        with open(AUTH_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"Error guardando sesion: {e}")
    return token

def verify_session_token(token: str) -> bool:
    if not token:
        return False
    init_auth()
    try:
        with open(AUTH_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return token in data.get("sessions", [])
    except Exception:
        return False

def change_admin_password(new_pass: str) -> bool:
    init_auth()
    try:
        with open(AUTH_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        data["admin_hash"] = hash_password(new_pass)
        with open(AUTH_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return True
    except Exception as e:
        logger.error(f"Error actualizando password: {e}")
        return False

# ==================== PLANTILLAS PRECONFIGURADAS DE AGENTES ====================
AGENT_TEMPLATES = {
    "tienda_perfumes": {
        "name": "Salomé · Perfumes & Boutique en Vivo",
        "type": "tienda_ventas",
        "sales_mode": "modo_bestia",
        "niche": "Perfumería fina, fragancias árabes, clones de diseñador y asesoría olfativa",
        "banner_title": "~ BOUTIQUE SALOMÉ PERFUMES EN VIVO ~",
        "banner_subtitle": "Fragancias Árabes · Diseñador · Asesoría Olfativa 🛍️",
        "voice": "es-CO-SalomeNeural",
        "estilo": "vendedor_experto",
        "theme_color": "#d4af37",
        "accent_color": "#00f0ff",
        "avatar": "/assets/logo_salome.jpg",
        "avatar_type": "video_loop",
        "video_idle": "/assets/salome_idle.mp4",
        "video_talking": "/assets/salome_talking.mp4",
        "bg_hex": "0x0a0c16",
        "store_name": "Salomé Fragrances & Luxury Boutique",
        "call_to_action": "📦 Pide tu perfume favorito tocando el enlace de nuestra biografía. Envíos gratis a toda Colombia hoy.",
        "keywords": [
            "perfume", "olor", "fragancia", "notas", "duracion", "estela", "cumplidos",
            "clon", "arabe", "árabe", "comprar", "precio", "oferta", "envio", "envío",
            "tienda", "recomiendame", "recomienda", "sauvage", "lattafa", "asad", "khamrah",
            "club de nuit", "noche", "fiesta", "oficina", "cita", "yara", "bharara", "orientica"
        ],
        "featured_products": [
            {
                "id": "p1",
                "name": "Lattafa Yara 100ml EDP (Original)",
                "price": "$163.000 COP",
                "sizes": "100ml",
                "notes": "Orquídea dulce, mandarina jugosa, heliotropo, frutas tropicales y vainilla sedosa. La fragancia femenina viral número 1 en Colombia.",
                "badge": "🌸 VIRAL FEMENINO"
            },
            {
                "id": "p2",
                "name": "Lattafa Khamrah EDP 100ml",
                "price": "$195.000 COP",
                "sizes": "100ml",
                "notes": "Inspirado en Angels' Share de Kilian. Canela dulce, dátiles exóticos, praliné crujiente y haba tonka gourmand. Estela bestial de 12+ horas.",
                "badge": "🍯 REY GOURMAND"
            },
            {
                "id": "p3",
                "name": "Club de Nuit Intense Man Armaf 105ml",
                "price": "$186.000 COP",
                "sizes": "105ml",
                "notes": "Inspirado en Creed Aventus. Limón chispeante, grosellas negras, abedul ahumado y ámbar gris. La fiera negra de cumplidos masculinos.",
                "badge": "👑 REY DE CUMPLIDOS"
            },
            {
                "id": "p4",
                "name": "Lattafa Asad EDP 100ml",
                "price": "$170.000 COP",
                "sizes": "100ml",
                "notes": "Inspirado en Dior Sauvage Elixir. Pimienta negra especiada, piña oscura, tabaco noble, café y vainilla cremosa. Fijación potente nocturna.",
                "badge": "🔥 BESTIA NOCTURNA"
            },
            {
                "id": "p5",
                "name": "Bharara King EDP 100ml",
                "price": "$293.000 COP",
                "sizes": "100ml",
                "notes": "Naranja sanguina, bergamota fresca, ámbar blanco cautivador y vainilla adictiva. La joya de proyección y estatus de alta alcurnia.",
                "badge": "👑 ESTATUS & PODER"
            },
            {
                "id": "p6",
                "name": "Amber Oud Gold Edition Al Haramain 60ml",
                "price": "$223.000 COP",
                "sizes": "60ml",
                "notes": "Inspirado en Erba Pura de Xerjoff. Frutas dulces de verano, melón jugoso, bergamota, ámbar dorado y almizcle blanco irresistible.",
                "badge": "⭐ ORO PURO"
            }
        ],
        "system_prompt": """Eres 'Salomé', una maestra y sommelier de alta perfumería carismática, sensual, elegante, persuasiva y apasionada en una transmisión en vivo de TikTok.
Estás dentro de tu exclusiva boutique de fragancias.

TIENES ACCESO A LA BASE DE CONOCIMIENTO ENCICLOPÉDICA DE MÁS DE 860 PERFUMES EN COLOMBIA (Kikluxe, LMD Perfumes Árabes, Esencia y Estilo):
- Conoces clones de diseñador (Sauvage, Toy Boy, Stronger With You, Good Girl, Black Opium, etc.), perfumes árabes originales (Lattafa, Armaf, Afnan, Bharara, Orientica) y sus notas olfativas exactas.
- Tus precios oficiales están en PESOS COLOMBIANOS (COP) con envíos a toda Colombia.

REGLAS DE ORO DE LA MAESTRA SOMMELIER (MODO BESTIA COMERCIAL CON OPCIONES):
1. TRANSMITE EL AROMA CON PASIÓN Y SEDUCCIÓN:
   - Describe las notas de salida, corazón y fondo de manera sensorial (cítricos chispeantes, maderas ahumadas, vainilla embriagadora, etc.).
   - Dile al cliente exactamente para qué ocasiones sirve (citas nocturnas, oficina, calor, seducción y conquista).
2. INTELIGENCIA DE VENTA ACTIVA CON OPCIONES (PERSUASIVA, NO ABUSIVA):
   - Conecta siempre la consulta del cliente con el catálogo de tu boutique o con la inspiración que busca.
   - OFRECE SIEMPRE OPCIONES ATRACTIVAS A/B (ej: "¿Prefieres llevarte el frasco original de Lattafa o te gustaría probar la alternativa de alta concentración por menor precio?", "¿Prefieres el dulce seductor de Khamrah o la frescura y estatus de Club de Nuit?").
   - Menciona el precio accesible en pesos colombianos ($ COP), que quedan pocas unidades y cierra con un llamado a la acción claro al enlace de tu biografía.
3. FORMATO DE RESPUESTA:
   - Sé enérgica, cercana, educada y habla dirigiéndote a la persona por su nombre limpio (sin arrobas).
   - Longitud: 3 a 4 oraciones directas, persuasivas y llenas de magnetismo olfativo.
   - Jamás hables de que eres una inteligencia artificial o un bot; eres la dueña y sommelier de la boutique en vivo.
"""
    },
    "sensei_perfumes": {
        "name": "Don Perfume · El Sensei de las Fragancias",
        "type": "consultorio",
        "sales_mode": "sensei_puro",
        "niche": "Alta perfumería, familias olfativas, notas, tops, rendimiento y estilo olfativo (0% Ventas)",
        "banner_title": "~ EL SENSEI DE LOS PERFUMES EN VIVO ~",
        "banner_subtitle": "Veredicto Olfativo · Notas · Tops · Calificaciones 👑",
        "voice": "es-MX-JorgeNeural",
        "estilo": "sabio_directo",
        "theme_color": "#d4af37",
        "accent_color": "#00f0ff",
        "avatar": "/assets/logo_perfume.jpg",
        "bg_hex": "0x0a0c16",
        "store_name": "Consultorio del Maestro Sommelier",
        "call_to_action": "Deja el nombre de tu perfume o la ocasión en el chat para darte mi veredicto",
        "keywords": [
            "perfume", "fragancia", "olor", "sauvage", "lattafa", "asad", "khamrah",
            "club de nuit", "gaultier", "creed", "baccarat", "notas", "fijacion", "duracion",
            "estela", "califica", "top", "opinion", "versace", "chanel", "dior", "arabe"
        ],
        "featured_products": [],
        "system_prompt": """Eres 'Don Perfume', el legendario Sensei de las Fragancias y maestro sommelier de alta perfumería en TikTok Live.
Tu estilo es sabio, elegante, respetado, certero y apasionado por el arte olfativo.

TIENES ACCESO A LA BASE DE CONOCIMIENTO ENCICLOPÉDICA DE MÁS DE 860 PERFUMES EN COLOMBIA (Kikluxe, LMD Perfumes Árabes, Esencia y Estilo):
- Conoces las casas, notas exactas (salida, corazón, fondo), fijación, estela, clima y ocasiones de uso.

REGLAS SUPREMAS DEL SENSEI DE LAS FRAGANCIAS:
1. CERO VENTAS / PROHIBIDO VENDER (ESTRICTO):
   - Jamás vendas productos, jamás menciones tiendas, ofertas, precios, envíos ni links en la biografía.
   - Tu valor es 100% de autoridad, sabiduría, educación y asesoría de alto estatus.
2. VEREDICTOS Y CALIFICACIONES DE MAESTRO:
   - Cuando el espectador pregunte por un perfume, dale tu veredicto sincero, describe sus notas (salida, corazón y fondo) y califícalo sobre 10 en fijación y magnetismo.
   - Desmiente mitos olfativos y enseña secretos de maceración y aplicación estratégica.
3. CONVERSACIÓN Y ENGANCHE EN TIKTOK LIVE:
   - Dirígete a la persona por su nombre limpio (sin arrobas ni números feos).
   - Cierra con una frase memorable y una pregunta para conocer el estilo o la colección del espectador.
   - Longitud: 3 a 4 oraciones de máxima autoridad.
"""
    },
    "sensei_amor": {
        "name": "El Sensei del Amor y la Seducción",
        "type": "consultorio",
        "niche": "Amor, seducción, citas, parejas y desamor",
        "banner_title": "~ EL SENSEI DEL AMOR ~",
        "banner_subtitle": "Conquista · Infidelidad · Parejas · Amor Propio",
        "voice": "es-MX-JorgeNeural",
        "estilo": "sabio_directo",
        "theme_color": "#ff2a6d",
        "accent_color": "#ffd700",
        "avatar": "/assets/logo_sensei.jpg",
        "bg_hex": "0x0f0214",
        "call_to_action": "🌹 Envía 1 Rosa para saltar la fila y consulta VIP en vivo",
        "keywords": [
            "crush", "ligar", "seduccion", "seducir", "friendzone", "hablarle",
            "historia", "storie", "instagram", "whatsapp", "cita", "misterio", "atraer",
            "ex", "infiel", "engaño", "engañó", "perdonar", "volver", "celos", "visto",
            "casi algo", "gusta", "gusto", "novio", "novia", "sensei", "consejo", "amor"
        ],
        "featured_products": [],
        "system_prompt": """Eres el legendario 'Sensei del Amor y la Seducción', un maestro místico, sabio, carismático y con una personalidad vibrante y pícara en un live de TikTok.
Tu estilo general: sabio, elegante, magnético y con alta autoestima.

REGLAS DE ORO:
1. Tu único universo es el amor, el desamor, la conquista, parejas y amor propio.
2. Responde directamente al nombre de la persona, con sabiduría certera, sin rodeos y con frases memorables.
3. Longitud: 2 a 4 oraciones impactantes.
"""
    },
    "madame_tarot": {
        "name": "Madame Luna · Tarot & Destino en Vivo",
        "type": "consultorio",
        "niche": "Lectura de cartas del tarot, horóscopos, destino y energías cósmicas",
        "banner_title": "~ TAROT Y DESTINO EN VIVO ~",
        "banner_subtitle": "Lecturas Místicas · Horóscopo · Deja tu Signo 🔮",
        "voice": "es-ES-ElviraNeural",
        "estilo": "mistica_reveladora",
        "theme_color": "#9d4edd",
        "accent_color": "#00f0ff",
        "avatar": "/assets/logo_sensei.jpg",
        "bg_hex": "0x120326",
        "call_to_action": "Escribe tu signo zodiacal y tu pregunta para abrir el oráculo en vivo",
        "keywords": [
            "tarot", "signo", "aries", "tauro", "geminis", "géminis", "cancer", "cáncer",
            "leo", "virgo", "libra", "escorpio", "sagitario", "capricornio", "acuario", "piscis",
            "cartas", "futuro", "destino", "energia", "energía", "lectura", "volverá", "volver", "sueño"
        ],
        "featured_products": [],
        "system_prompt": """Eres 'Madame Luna', una vidente y lectora de cartas del tarot mística, misteriosa y cautivadora en TikTok Live.
Interpretas la energía de los espectadores al instante basándote en su signo y su pregunta.
Siempre das un mensaje de poder espiritual y revelación."""
    },
    "fitness_titan": {
        "name": "Coach Titán · Fitness & Suplementos",
        "type": "tienda_ventas",
        "niche": "Entrenamiento, déficit calórico, masa muscular y suplementación",
        "banner_title": "~ COACH TITÁN · FITNESS LIVE ~",
        "banner_subtitle": "Rutinas · Suplementos · Asesorías en Vivo ⚡",
        "voice": "es-CO-GonzaloNeural",
        "estilo": "motivador_directo",
        "theme_color": "#ff5500",
        "accent_color": "#00ff66",
        "avatar": "/assets/logo_sensei.jpg",
        "bg_hex": "0x09140a",
        "store_name": "Titán Nutrition & Supplements",
        "call_to_action": "Pide tu proteína o creatina con descuento tocando el enlace de mi perfil.",
        "keywords": [
            "creatina", "proteina", "proteína", "suplemento", "gym", "rutina", "musculo",
            "grasa", "deficit", "volumen", "peso", "entrenar", "ejercicio", "brazos", "pecho"
        ],
        "featured_products": [
            {
                "id": "f1",
                "name": "Creatina Creapure Monohidratada (300g)",
                "price": "$29 USD",
                "notes": "100% pura, micronizada, máxima fuerza y recuperación celular.",
                "badge": "⚡ ESENCIAL"
            },
            {
                "id": "f2",
                "name": "Whey Isolate Protein (2 Libras)",
                "price": "$49 USD",
                "notes": "27g de proteína por scoop, cero azúcar, sabor chocolate suizo.",
                "badge": "💪 TOP VENTAS"
            }
        ],
        "system_prompt": """Eres 'Coach Titán', un entrenador personal de élite, disciplinado, enérgico y directo en TikTok Live.
Resuelves dudas de entrenamiento y recomiendas la mejor suplementación para los objetivos del espectador.
Cierra siempre motivando a entrenar duro y recomendando los suplementos disponibles en el enlace del perfil."""
    },
    "calzado_sneakers": {
        "name": "SneakerDrop · Calzado & Sneakers en Vivo",
        "type": "tienda_ventas",
        "sales_mode": "modo_bestia",
        "niche": "Calzado deportivo, sneakers urbanos, zapatillas de colección y streetwear",
        "banner_title": "~ SNEAKERDROP · CALZADO EN VIVO ~",
        "banner_subtitle": "Sneakers Prémium · Tallas 36 a 44 · Envíos Hoy 👟",
        "voice": "es-CO-GonzaloNeural",
        "estilo": "vendedor_experto",
        "theme_color": "#ff3366",
        "accent_color": "#00f0ff",
        "avatar": "/assets/logo_orb_gold.png",
        "bg_hex": "0x0a0c16",
        "store_name": "SneakerDrop Luxury & Streetwear",
        "call_to_action": "👟 Pide tus zapatillas favoritas en el link de mi perfil. Envíos gratis y tallas confirmadas hoy.",
        "keywords": [
            "zapatillas", "sneakers", "calzado", "tenis", "zapatos", "talla", "tallas",
            "jordan", "nike", "adidas", "yeezy", "air force", "comprar", "precio", "envio", "envío"
        ],
        "featured_products": [
            {
                "id": "shoe_1",
                "name": "Nike Air Jordan 1 Retro High OG",
                "price": "$85 USD",
                "sizes": "38, 39, 40, 41, 42, 43, 44",
                "notes": "Cuero prémium, amortiguación Air-Sole, combinaciones Panda y Chicago. Envío gratis hoy.",
                "badge": "🔥 BEST SELLER"
            },
            {
                "id": "shoe_2",
                "name": "Nike Air Force 1 '07 White",
                "price": "$65 USD",
                "sizes": "37, 38, 39, 40, 41, 42, 43, 44",
                "notes": "100% cuero blanco pulcro, estilo clásico urbano inconfundible, suela de goma cosida.",
                "badge": "👑 CLÁSICO INFALIBLE"
            },
            {
                "id": "shoe_3",
                "name": "Adidas Forum Low Classic",
                "price": "$70 USD",
                "sizes": "38, 39, 40, 41, 42, 43",
                "notes": "Silueta retro con correa extraíble de velcro, cuero acolchado y gran comodidad para diario.",
                "badge": "⚡ TENDENCIA URBANA"
            },
            {
                "id": "shoe_4",
                "name": "Yeezy Boost 350 V2 Onyx",
                "price": "$95 USD",
                "sizes": "38, 39, 40, 41, 42, 43, 44, 45",
                "notes": "Tejido Primeknit ultra flexible, entresuela con tecnología Boost para máxima amortiguación.",
                "badge": "🌟 MÁXIMA COMODIDAD"
            }
        ],
        "system_prompt": """Eres el presentador y experto en calzado y streetwear de 'SneakerDrop' en una transmisión en vivo de TikTok Live.
Tu estilo es urbano, enérgico, cercano, conocedor de la cultura sneaker y apasionado por las zapatillas.

REGLAS DE VENTA EN MODO BESTIA COMERCIAL (CALZADO & SNEAKERS):
1. Saluda con vibra y cercanía llamando al espectador por su nombre limpio (sin arrobas).
2. CONOCE TU CATÁLOGO Y CIERRA VENTAS CON OPCIONES:
   - Conecta la consulta del cliente con los modelos de tu catálogo (Jordan 1, Air Force 1, Forum Low, Yeezy Boost).
   - Habla de la comodidad, los materiales (cuero legítimo, amortiguación Air / Boost) y las tallas disponibles.
   - OFRECE SIEMPRE OPCIONES A/B: "¿Prefieres el estilo clásico del Air Force 1 o quieres dar el salto al Jordan 1 High que es más de colección?".
   - Menciona el precio accesible y la urgencia de pocas tallas en stock.
   - Cierra con el llamado a la acción: "Toca el enlace de mi perfil para apartar tu talla con envío gratis antes de que se agoten".
3. Longitud: 3 a 4 oraciones de alto impacto."""
    }
}

# ==================== CLASE GESTORA DE AGENTES ====================
class AgentManager:
    def __init__(self):
        self.agents = {}
        self.active_agent_id = "sensei-amor"
        self.load_agents()

    def load_agents(self):
        if AGENTS_FILE.exists():
            try:
                with open(AGENTS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.agents = data.get("agents", {})
                    self.active_agent_id = data.get("active_agent_id", "sensei-amor")
                    if "sensei-amor" in self.agents and not self.agents["sensei-amor"].get("tiktok_username"):
                        self.agents["sensei-amor"]["tiktok_username"] = os.environ.get("TIKTOK_USERNAME", "senseidelamor")
            except Exception as e:
                logger.error(f"Error cargando agents.json: {e}")

        # Si no hay agentes, inicializar con el Sensei, Salomé y Don Perfume
        if not self.agents:
            self.agents = {
                "sensei-amor": {
                    "id": "sensei-amor",
                    **AGENT_TEMPLATES["sensei_amor"],
                    "tiktok_username": os.environ.get("TIKTOK_USERNAME", "senseidelamor"),
                    "rtmp_url": os.environ.get("TIKTOK_RTMP_URL", ""),
                    "stream_key": os.environ.get("TIKTOK_STREAM_KEY", ""),
                    "gemini_api_key": "",
                    "client_name": "Sensei Propio (Principal)",
                    "client_pin": "1234",
                    "is_streaming": False,
                    "created_at": "2026-10-25"
                },
                "perfumes-elite": {
                    "id": "perfumes-elite",
                    **AGENT_TEMPLATES["tienda_perfumes"],
                    "tiktok_username": "",
                    "rtmp_url": "",
                    "stream_key": "",
                    "gemini_api_key": "",
                    "client_name": "Cliente Demo: Salomé Perfumes VIP",
                    "client_pin": "5678",
                    "is_streaming": False,
                    "created_at": "2026-10-25"
                },
                "sensei-perfumes": {
                    "id": "sensei-perfumes",
                    **AGENT_TEMPLATES["sensei_perfumes"],
                    "tiktok_username": "",
                    "rtmp_url": "",
                    "stream_key": "",
                    "gemini_api_key": "",
                    "client_name": "Don Perfume (Sensei Sin Ventas)",
                    "client_pin": "9999",
                    "is_streaming": False,
                    "created_at": "2026-10-25"
                }
            }
            self.save_agents()
        else:
            # Asegurar que el Sensei de los Perfumes (Sin Ventas) esté disponible
            if "sensei-perfumes" not in self.agents and "sensei_perfumes" in AGENT_TEMPLATES:
                self.agents["sensei-perfumes"] = {
                    "id": "sensei-perfumes",
                    **AGENT_TEMPLATES["sensei_perfumes"],
                    "tiktok_username": "",
                    "rtmp_url": "",
                    "stream_key": "",
                    "gemini_api_key": "",
                    "client_name": "Don Perfume (Sensei Sin Ventas)",
                    "client_pin": "9999",
                    "is_streaming": False,
                    "created_at": "2026-10-25"
                }
                self.save_agents()

            # Asegurar que el Agente de Calzado & Sneakers esté disponible
            if "calzado-sneakers" not in self.agents and "calzado_sneakers" in AGENT_TEMPLATES:
                self.agents["calzado-sneakers"] = {
                    "id": "calzado-sneakers",
                    **AGENT_TEMPLATES["calzado_sneakers"],
                    "tiktok_username": "",
                    "rtmp_url": "",
                    "stream_key": "",
                    "gemini_api_key": "",
                    "client_name": "Demo Calzado & Sneakers Urbanos",
                    "client_pin": "7777",
                    "is_streaming": False,
                    "created_at": "2026-10-25"
                }
                self.save_agents()

            # Asegurar sales_mode en agentes existentes
            for ag_id, ag in self.agents.items():
                if not ag.get("sales_mode"):
                    if ag_id == "sensei-perfumes" or ag.get("type") == "consultorio":
                        ag["sales_mode"] = "sensei_puro"
                    else:
                        ag["sales_mode"] = "modo_bestia"
                # Actualizar prompt y catálogo de Salomé a venta con opciones y catálogo colombiano en COP
                if ag_id == "perfumes-elite":
                    ag["system_prompt"] = AGENT_TEMPLATES["tienda_perfumes"]["system_prompt"]
                    ag["sales_mode"] = "modo_bestia"
                    ag["call_to_action"] = AGENT_TEMPLATES["tienda_perfumes"]["call_to_action"]
                    curr_prods = ag.get("featured_products", [])
                    if any("USD" in str(p.get("price", "")) for p in curr_prods) or len(curr_prods) < 5:
                        ag["featured_products"] = AGENT_TEMPLATES["tienda_perfumes"]["featured_products"]

                # Actualizar prompt del Sensei de los Perfumes con acceso a la enciclopedia
                if ag_id == "sensei-perfumes":
                    ag["system_prompt"] = AGENT_TEMPLATES["sensei_perfumes"]["system_prompt"]

            # Asegurar avatar_type y videos en agentes existentes
            for ag_id, ag in self.agents.items():
                if not ag.get("avatar_type"):
                    if ag_id == "perfumes-elite":
                        ag["avatar_type"] = "video_loop"
                        ag["video_idle"] = "/assets/salome_idle.mp4"
                        ag["video_talking"] = "/assets/salome_talking.mp4"
                    else:
                        ag["avatar_type"] = "image"
                        ag["video_idle"] = ""
                        ag["video_talking"] = ""

            # Asegurar campo sizes en productos de calzado existentes
            if "calzado-sneakers" in self.agents:
                for p in self.agents["calzado-sneakers"].get("featured_products", []):
                    if not p.get("sizes"):
                        p_nom = p.get("name", "").lower()
                        if "jordan" in p_nom:
                            p["sizes"] = "38, 39, 40, 41, 42, 43, 44"
                        elif "air force" in p_nom:
                            p["sizes"] = "37, 38, 39, 40, 41, 42, 43, 44"
                        elif "forum" in p_nom:
                            p["sizes"] = "38, 39, 40, 41, 42, 43"
                        elif "yeezy" in p_nom:
                            p["sizes"] = "38, 39, 40, 41, 42, 43, 44, 45"
                        else:
                            p["sizes"] = "38 al 44"
            self.save_agents()

    def save_agents(self):
        try:
            with open(AGENTS_FILE, "w", encoding="utf-8") as f:
                json.dump({
                    "active_agent_id": self.active_agent_id,
                    "agents": self.agents
                }, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error guardando agents.json: {e}")

    def get_all_agents(self):
        return list(self.agents.values())

    def get_agent(self, agent_id: str):
        return self.agents.get(agent_id)

    def get_active_agent(self):
        agent = self.agents.get(self.active_agent_id)
        if not agent and self.agents:
            self.active_agent_id = list(self.agents.keys())[0]
            agent = self.agents[self.active_agent_id]
        return agent

    def set_active_agent(self, agent_id: str):
        if agent_id in self.agents:
            self.active_agent_id = agent_id
            self.save_agents()
            return True
        return False

    def create_agent(self, data: dict) -> dict:
        import re
        nombre = data.get("name", "Nuevo Agente").strip()
        slug = re.sub(r'[^a-zA-Z0-9_-]', '', data.get("id", "").strip().lower())
        if not slug:
            slug = re.sub(r'[^a-zA-Z0-9_-]', '-', nombre.lower())[:24]

        # Evitar colisión de IDs
        base_slug = slug
        count = 1
        while slug in self.agents:
            slug = f"{base_slug}-{count}"
            count += 1

        template_key = data.get("template", "sensei_amor")
        preset = AGENT_TEMPLATES.get(template_key, AGENT_TEMPLATES["sensei_amor"])

        nuevo_agente = {
            "id": slug,
            "name": nombre,
            "type": data.get("type") or preset.get("type", "consultorio"),
            "niche": data.get("niche") or preset.get("niche", "Especialidad en vivo"),
            "banner_title": data.get("banner_title") or f"~ {nombre.upper()} ~",
            "banner_subtitle": data.get("banner_subtitle") or preset.get("banner_subtitle", ""),
            "voice": data.get("voice") or preset.get("voice", "es-MX-JorgeNeural"),
            "estilo": data.get("estilo") or preset.get("estilo", "sabio_directo"),
            "sales_mode": data.get("sales_mode") or preset.get("sales_mode", "modo_bestia" if (data.get("type") or preset.get("type")) == "tienda_ventas" else "sensei_puro"),
            "theme_color": data.get("theme_color") or preset.get("theme_color", "#ff2a6d"),
            "accent_color": data.get("accent_color") or preset.get("accent_color", "#ffd700"),
            "avatar": data.get("avatar") or preset.get("avatar", "/assets/logo_sensei.jpg"),
            "avatar_type": data.get("avatar_type") or preset.get("avatar_type", "image"),
            "video_idle": data.get("video_idle") or preset.get("video_idle", ""),
            "video_talking": data.get("video_talking") or preset.get("video_talking", ""),
            "bg_hex": data.get("bg_hex") or preset.get("bg_hex", "0x0f0214"),
            "store_name": data.get("store_name") or preset.get("store_name", ""),
            "call_to_action": data.get("call_to_action") or preset.get("call_to_action", "Pregunta en los comentarios"),
            "keywords": data.get("keywords") or preset.get("keywords", ["pregunta", "consejo"]),
            "featured_products": data.get("featured_products") or preset.get("featured_products", []),
            "system_prompt": data.get("system_prompt") or preset.get("system_prompt", ""),
            "tiktok_username": data.get("tiktok_username", "").strip(),
            "rtmp_url": data.get("rtmp_url", "").strip(),
            "stream_key": data.get("stream_key", "").strip(),
            "gemini_api_key": data.get("gemini_api_key", "").strip(),
            "client_name": data.get("client_name", "Cliente Alquiler").strip(),
            "client_pin": data.get("client_pin", "1234").strip(),
            "is_streaming": False,
            "created_at": "2026-10-25"
        }

        self.agents[slug] = nuevo_agente
        self.save_agents()
        return nuevo_agente

    def update_agent(self, agent_id: str, updates: dict) -> bool:
        if agent_id not in self.agents:
            return False

        agent = self.agents[agent_id]
        # Permitir actualizar campos configurables
        campos = [
            "name", "type", "niche", "banner_title", "banner_subtitle", "voice", "estilo",
            "sales_mode",
            "theme_color", "accent_color", "avatar", "avatar_type", "video_idle", "video_talking",
            "bg_hex", "store_name", "call_to_action",
            "keywords", "featured_products", "system_prompt", "tiktok_username", "rtmp_url",
            "stream_key", "tiktok_session_id", "gemini_api_key", "client_name", "client_pin"
        ]
        for c in campos:
            if c in updates:
                agent[c] = updates[c]

        self.save_agents()
        return True

    def delete_agent(self, agent_id: str) -> bool:
        if agent_id in self.agents:
            del self.agents[agent_id]
            if self.active_agent_id == agent_id:
                self.active_agent_id = list(self.agents.keys())[0] if self.agents else ""
            self.save_agents()
            return True
        return False

    def generar_alerta_venta(self, agent_id: str = None) -> dict:
        """Simula una venta real de la tienda para crear urgencia e interacción en el Live."""
        import random
        agent = self.get_agent(agent_id or self.active_agent_id)
        if not agent or agent.get("type") != "tienda_ventas":
            return None

        productos = agent.get("featured_products", [])
        if not productos:
            prod_nombre = "Fragancia de Lujo"
            prod_precio = "$40 USD"
        else:
            p = random.choice(productos)
            prod_nombre = p.get("name", "Producto")
            prod_precio = p.get("price", "$35 USD")

        nombres_compradores = [
            "Sofía R.", "Carlos M.", "Alejandro G.", "Valentina P.", "Mateo D.",
            "Camila S.", "Sebastián V.", "Daniela L.", "Andrés F.", "Mariana T."
        ]
        ciudades = ["Madrid", "Ciudad de México", "Bogotá", "Lima", "Buenos Aires", "Santiago", "Miami", "Guadalajara"]
        stock_restante = random.randint(1, 4)

        return {
            "cliente": random.choice(nombres_compradores),
            "ciudad": random.choice(ciudades),
            "producto": prod_nombre,
            "precio": prod_precio,
            "stock": stock_restante,
            "mensaje": f"🛍️ ¡NUEVA VENTA! {random.choice(nombres_compradores)} ({random.choice(ciudades)}) compró '{prod_nombre}'. ¡Solo quedan {stock_restante} en stock!"
        }

# Instancia global
agent_manager = AgentManager()
