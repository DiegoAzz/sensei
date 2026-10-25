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
from pathlib import Path
from aiohttp import web

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("SenseiSeduccion")

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
CONFIG_FILE = DATA_DIR / "config.json"

# Estado del sistema
estado = {
    "is_streaming": False,
    "tiktok_username": os.environ.get("TIKTOK_USERNAME", ""),
    "rtmp_url": os.environ.get("TIKTOK_RTMP_URL", ""),
    "stream_key": os.environ.get("TIKTOK_STREAM_KEY", ""),
    "voice": os.environ.get("VOICE", "es-MX-JorgeNeural"),
    "gemini_api_key": os.environ.get("GEMINI_API_KEY", ""),
    "agent_name": os.environ.get("AGENT_NAME", "Sensei del Amor y la Seducción"),
    "estilo": os.environ.get("ESTILO_CONSEJO", "sabio_directo"),
    "active_user": "",
    "active_question": "Esperando consultas de amor y seducción...",
    "active_answer": "Deja en el chat tu caso sobre tu crush, ligar, pareja o desamor."
}

if CONFIG_FILE.exists():
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            saved = json.load(f)
            estado.update(saved)
    except Exception as e:
        logger.warning(f"No se pudo cargar config.json previo: {e}")

cola_preguntas = asyncio.Queue()
buffer_logs = []
ffmpeg_process = None
tiktok_task = None
worker_task = None

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
async def responder_con_ia(usuario: str, pregunta: str) -> str:
    api_key = estado.get("gemini_api_key") or os.environ.get("GEMINI_API_KEY")

    if api_key:
        try:
            import aiohttp
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
            
            tono = "sabio, elegante, magnético y con alta autoestima" if estado["estilo"] == "sabio_directo" else "picante, directo a la llaga y con verdades sin anestesia"
            
            prompt = f"""Eres el 'Sensei del Amor y la Seducción', un maestro y mentor de relaciones, seducción, psicología de la atracción, cómo hablarle a un crush, salir de la friendzone, mensajes de texto e infidelidades en un live de TikTok.
Tu estilo: {tono}.
Reglas estrictas:
1. Responde SIEMPRE en español en máximo 2 a 3 frases breves y de alto impacto.
2. Saluda brevemente al usuario @{usuario} por su nombre al comenzar.
3. Enseña que la atracción nace de la seguridad, el misterio y el amor propio, nunca de mendigar atención o rogar.

Pregunta del espectador en TikTok: "{pregunta}"
Respuesta del Sensei:"""

            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.8, "maxOutputTokens": 140}
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                    if resp.status == 200:
                        d = await resp.json()
                        return d["candidates"][0]["content"]["parts"][0]["text"].strip()
        except Exception as e:
            logger.warning(f"Error al consultar Gemini API: {e}. Usando oráculo local de seducción.")

    # Oráculo de Sabiduría Local de Seducción y Relaciones
    q = pregunta.lower()
    nombre = usuario.split("_")[0].capitalize()

    # 1. Salir de la Friendzone
    if any(k in q for k in ["friendzone", "amigo", "amiga", "hermano", "zona de amigos"]):
        return f"Escucha bien, {nombre}. Para salir de la friendzone debes romper el papel de 'amigo incondicional': toma distancia, deja de estar disponible a toda hora y demuestra intención clara sin miedo al rechazo."

    # 2. Cómo hablarle a la crush / Iniciar conversación
    elif any(k in q for k in ["hablarle", "iniciar", "acercarme", "que le digo", "qué le digo", "romper el hielo"]):
        return f"Hola {nombre}. Nunca empieces con un soso 'hola, qué haces'. Haz una observación divertida sobre lo que está pasando a su alrededor o hazle un cumplido genuino a su actitud; la naturalidad siempre conquista."

    # 3. Responder historias de Instagram / WhatsApp
    elif any(k in q for k in ["historia", "storie", "responderle", "instagram", "mensaje", "escribirle"]):
        return f"Atento, {nombre}. Jamás respondas con un fueguito o un 'qué hermosa'. Comenta algo ingenioso que abra debate o hazle una pregunta que despierte su curiosidad; dale una razón real para querer contestarte."

    # 4. Generar misterio y atracción
    elif any(k in q for k in ["misterio", "atraer", "atractivo", "interesar", "gustarle"]):
        return f"El secreto de la seducción, {nombre}, es no entregar todo el libro en la primera página. Deja las charlas en su punto más alto y ten metas apasionantes; lo que es escaso se valora, lo regalado aburre."

    # 5. Primera cita
    elif any(k in q for k in ["primera cita", "cita", "invitarla", "invitarlo", "adonde", "a dónde"]):
        return f"Para tu primera cita, {nombre}, evita cenas formales y aburridas. Elige un plan dinámico donde puedan caminar, reírse y compartir un café; el objetivo no es impresionarle con dinero, sino conectar con tu personalidad."

    # 6. Saber si le gustas / Señales
    elif any(k in q for k in ["le gusto", "señal", "señales", "interesada", "interesado"]):
        return f"Aprende esto, {nombre}: quien tiene interés verdadero busca pretextos para hablarte y facilita verse. Si tienes que dudar o siempre hay una excusa para no salir, la respuesta ya es un no."

    # 7. Infidelidades
    elif any(k in q for k in ["infiel", "engañó", "engaño", "cuerno", "traicion", "traición", "otra"]):
        return f"Escucha, {nombre}. La infidelidad no es un descuido, es una decisión consciente. Quien te traiciona una vez te demuestra que no respeta tu valor; ten dignidad y sal de ahí."

    # 8. Volver con el ex
    elif any(k in q for k in ["volver", "ex", "regresar", "extraño", "bloqueo", "bloquear"]):
        return f"Querido {nombre}, volver con tu ex es como comprar tu propia ropa usada esperando que huela a nuevo. Recuerda por qué terminó la historia y aplica contacto cero absoluto."

    # 9. Dejar en visto / Ghosting
    elif any(k in q for k in ["visto", "ignora", "escribe", "tarda", "frio", "fría"]):
        return f"Aprende esto, {nombre}: la falta de interés también es una respuesta clara. Quien te quiere te busca, quien no, te pone pretextos. No mendigues la atención de nadie."

    # 10. Los "Casi Algo"
    elif any(k in q for k in ["casi algo", "formalizar", "amigos con derecho", "etiqueta"]):
        return f"Atento, {nombre}. Si ya llevan meses y te dice que 'no busca nada serio', lo que te dice es que no lo busca contigo. Retira tu cariño de donde no hay compromiso."

    else:
        return f"Recuerda esto, {nombre}: en el amor y en la seducción, tu mayor atractivo siempre será tu seguridad y tu amor propio. Camina firme y nunca te conformes con migajas."

# ==================== SÍNTESIS DE VOZ (TTS) ====================
async def sintetizar_audio(texto: str, salida_path: str):
    import edge_tts
    voz = estado.get("voice", "es-MX-JorgeNeural")
    comunicador = edge_tts.Communicate(texto, voz, rate="+0%", pitch="-2Hz")
    await comunicador.save(salida_path)

# ==================== MOTOR DE STREAMING FFMPEG ====================
def iniciar_proceso_ffmpeg(rtmp_destino: str):
    """
    Genera un stream vertical 720x1280 estilo Templo Oriental Neón
    con el Sensei del Amor levitando suavemente en el aire de forma continua y misteriosa.
    """
    logo_file = BASE_DIR / "assets" / "logo_circle.png"
    if not logo_file.exists():
        logo_file = BASE_DIR / "assets" / "logo_sensei.jpg"

    has_logo = logo_file.exists()

    cmd = [
        "ffmpeg",
        "-re",
        "-f", "lavfi",
        # Fondo oscuro carmesí / ciruela místico
        "-i", "color=c=0x0f0214:s=720x1280:r=30",
        "-f", "lavfi",
        "-i", "anullsrc=r=44100:cl=stereo"
    ]

    if has_logo:
        cmd.extend(["-loop", "1", "-i", str(logo_file)])
        filter_complex = (
            # 1. Fondo base del templo y marco
            "[0:v]drawbox=x=30:y=100:w=660:h=1060:color=0x180420@0.95:t=fill,"
            "drawbox=x=30:y=100:w=660:h=1060:color=0xff2a6d@0.45:t=2,"
            # Título principal
            "drawtext=text='~ EL SENSEI DEL AMOR ~':fontcolor=0xffd700:fontsize=28:x=(w-text_w)/2:y=140,"
            "drawtext=text='Conquista · Infidelidad · Parejas · Amor Propio':fontcolor=0xff7597:fontsize=16:x=(w-text_w)/2:y=185[bg];"
            # 2. Escalar el avatar circular
            "[2:v]scale=320:320[avatar];"
            # 3. Superponer el avatar LEVITANDO en el aire continuamente
            "[bg][avatar]overlay=x=(W-w)/2:y='235+14*sin(2*PI*t/3.2)'[v1];"
            # 4. Caja de consulta en vivo del chat
            "[v1]drawbox=x=60:y=600:w=600:h=260:color=0x09010e@0.9:t=fill,"
            "drawbox=x=60:y=600:w=600:h=260:color=0xff7597@0.3:t=1,"
            "drawtext=text='● CONSULTORIO EN VIVO · TIKTOK LIVE':fontcolor=0xff2a6d:fontsize=14:x=80:y=620,"
            "drawtext=text='Escribe tu pregunta sobre tu crush o pareja':fontcolor=0xedf4f9@0.9:fontsize=18:x=80:y=660,"
            # 5. Llamado a la acción inferior
            "drawbox=x=60:y=1040:w=600:h=65:color=0xff2a6d@0.25:t=fill,"
            "drawbox=x=60:y=1040:w=600:h=65:color=0xff2a6d@0.8:t=2,"
            "drawtext=text='★ Pregunta al Sensei: Tu crush, ligar, ex parejas o celos ★':fontcolor=0xffd700:fontsize=16:x=(w-text_w)/2:y=1063"
        )
        cmd.extend(["-filter_complex", filter_complex])
    else:
        vf = (
            "drawbox=x=30:y=130:w=660:h=1000:color=0x1a0720@0.95:t=fill,"
            "drawbox=x=30:y=130:w=660:h=1000:color=0xff2a6d@0.55:t=2,"
            "drawtext=text='SENSEI DEL AMOR Y LA SEDUCCION':fontcolor=0xffd700:fontsize=28:x=(w-text_w)/2:y=170,"
            "drawtext=text='Conquista · Parejas · Salir de la Friendzone':fontcolor=0xff7597:fontsize=17:x=(w-text_w)/2:y=215,"
            "drawbox=x=60:y=270:w=600:h=230:color=0x0c0110@0.9:t=fill,"
            "drawbox=x=60:y=270:w=600:h=230:color=0xff7597@0.3:t=1,"
            "drawtext=text='CONSULTA EN VIVO DEL CHAT':fontcolor=0xff2a6d:fontsize=14:x=80:y=290,"
            "drawtext=text='Deja tu pregunta sobre tu crush o pareja':fontcolor=0xedf4f9@0.9:fontsize=19:x=80:y=330,"
            "drawbox=x=60:y=1040:w=600:h=60:color=0xff2a6d@0.25:t=fill,"
            "drawtext=text='🏮 Pregunta al Sensei: Tu crush, ligar, ex parejas o celos 🏮':fontcolor=0xffd700:fontsize=16:x=(w-text_w)/2:y=1060"
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
    return subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

# ==================== WORKER DE PREGUNTAS ====================
async def worker_preguntas():
    while estado["is_streaming"]:
        usuario, pregunta = await cola_preguntas.get()
        estado["active_user"] = usuario
        estado["active_question"] = pregunta

        registrar_log(f"🏮 Consulta de @{usuario}: \"{pregunta}\"", "hl")

        respuesta = await responder_con_ia(usuario, pregunta)
        estado["active_answer"] = respuesta
        registrar_log(f"📿 Sensei responde: \"{respuesta}\"", "green")

        audio_tmp = DATA_DIR / "consejo_sensei.mp3"
        try:
            await sintetizar_audio(respuesta, str(audio_tmp))
            registrar_log(f"Voz del Sensei ({estado['voice']}) sintetizada.", "hl")
        except Exception as e:
            registrar_log(f"Error generando TTS: {e}", "err")

        # Pausa natural para la audiencia
        await asyncio.sleep(7)
        cola_preguntas.task_done()

# ==================== CLIENTE TIKTOK LIVE ====================
async def escuchar_tiktok():
    from TikTokLive import TikTokLiveClient
    from TikTokLive.types.events import CommentEvent, ConnectEvent

    usuario = estado["tiktok_username"].replace("@", "").strip()
    if not usuario:
        return

    client = TikTokLiveClient(unique_id=f"@{usuario}")

    @client.on(ConnectEvent)
    async def on_connect(event: ConnectEvent):
        registrar_log(f"✅ ¡Conectado al Live de TikTok de @{usuario}!", "green")

    @client.on(CommentEvent)
    async def on_comment(event: CommentEvent):
        u = event.user.unique_id
        c = event.comment

        # Palabras clave de amor, seducción, ligoteo y relaciones
        palabras = [
            "?", "¿", "crush", "ligar", "seduccion", "seducir", "friendzone", "hablarle",
            "historia", "storie", "instagram", "whatsapp", "cita", "misterio", "atraer",
            "ex", "infiel", "engaño", "engañó", "perdonar", "volver", "celos", "visto",
            "casi algo", "gusta", "gusto", "novio", "novia", "sensei", "consejo"
        ]

        if any(k in c.lower() for k in palabras) and len(c) >= 5:
            registrar_log(f"📥 Pregunta recibida de @{u}: {c}")
            await cola_preguntas.put((u, c))

    try:
        await client.start()
    except Exception as e:
        registrar_log(f"Conexión TikTokLive: {e}", "warn")

# ==================== ENDPOINTS DE LA API WEB ====================
async def handle_status(request):
    return web.json_response(estado)

async def handle_start(request):
    global ffmpeg_process, tiktok_task, worker_task

    data = await request.json()
    estado["tiktok_username"] = data.get("tiktok_username", estado["tiktok_username"])
    estado["rtmp_url"] = data.get("rtmp_url", estado["rtmp_url"])
    estado["stream_key"] = data.get("stream_key", estado["stream_key"])
    estado["voice"] = data.get("voice", estado["voice"])
    estado["estilo"] = data.get("estilo", estado["estilo"])
    if data.get("gemini_api_key"):
        estado["gemini_api_key"] = data.get("gemini_api_key")

    guardar_configuracion()

    if not estado["rtmp_url"] or not estado["stream_key"]:
        return web.json_response({"ok": False, "error": "Debes ingresar la URL RTMP y la Stream Key de TikTok"})

    rtmp_completo = f"{estado['rtmp_url'].rstrip('/')}/{estado['stream_key']}"

    try:
        ffmpeg_process = iniciar_proceso_ffmpeg(rtmp_completo)
        estado["is_streaming"] = True

        worker_task = asyncio.create_task(worker_preguntas())
        tiktok_task = asyncio.create_task(escuchar_tiktok())

        registrar_log("Transmisión en vivo del Sensei del Amor y la Seducción iniciada.", "green")
        return web.json_response({"ok": True})
    except Exception as e:
        return web.json_response({"ok": False, "error": str(e)})

async def handle_stop(request):
    global ffmpeg_process, tiktok_task, worker_task
    estado["is_streaming"] = False

    if ffmpeg_process:
        ffmpeg_process.terminate()
        ffmpeg_process = None

    if tiktok_task:
        tiktok_task.cancel()
    if worker_task:
        worker_task.cancel()

    registrar_log("Transmisión finalizada por el usuario.", "warn")
    return web.json_response({"ok": True})

async def handle_logs(request):
    logs_a_enviar = list(buffer_logs)
    buffer_logs.clear()
    return web.json_response(logs_a_enviar)

async def handle_test_comment(request):
    data = await request.json()
    user = data.get("user", "discipulo_test")
    comment = data.get("comment", "")

    if comment:
        await cola_preguntas.put((user, comment))
        ans = await responder_con_ia(user, comment)
        return web.json_response({"ok": True, "answer": ans})
    return web.json_response({"ok": False})

async def handle_index(request):
    html_file = BASE_DIR / "web_dashboard.html"
    return web.FileResponse(html_file)

# ==================== MAIN ====================
async def start_dual_servers():
    app = web.Application()
    app.router.add_get("/", handle_index)
    app.router.add_get("/api/status", handle_status)
    app.router.add_post("/api/start", handle_start)
    app.router.add_post("/api/stop", handle_stop)
    app.router.add_get("/api/logs", handle_logs)
    app.router.add_post("/api/test-comment", handle_test_comment)

    # Servir archivos estáticos (Logo del Sensei, imágenes, audio)
    assets_dir = BASE_DIR / "assets"
    assets_dir.mkdir(exist_ok=True)
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
