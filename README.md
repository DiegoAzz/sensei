# ⛩️ Sensei del Amor — Agente IA para TikTok Live 24/7 (VPS / Coolify)

El formato del **"Sensei del Amor"** (o Consultorio de Parejas con IA) es uno de los conceptos más virales y de mayor retención de audiencia en TikTok Live. Los espectadores comentan continuamente situaciones de desamor, infidelidades, dudas sobre sus ex parejas o "casi algos", y el agente les responde por voz en vivo con sabiduría, dignidad y verdades directas.

Este paquete está diseñado específicamente para correr **24/7 en tu VPS con Coolify de forma 100% headless (sin necesidad de OBS ni de una PC encendida)**.

---

## 🎭 Personalidad y Estilo del Sensei

El agente tiene dos modos de respuesta configurables desde el panel web:
1. **Sabio y Firme (Amor propio):** Consejos reflexivos, empáticos y contundentes que priorizan la paz mental y la dignidad ("El amor no se mendiga", "Quien te engaña una vez, te demuestra su falta de respeto").
2. **Verdades sin Filtro (Picante / Directo):** Humor realista, verdades sin anestesia y cero tolerancia al drama tóxico.

---

## 📂 Estructura del Proyecto

```
tiktok-sensei-del-amor/
├── Dockerfile           # Imagen Docker ligera con Python 3.11 y FFmpeg
├── docker-compose.yml   # Archivo listo para importar en Coolify
├── server.py            # Motor principal: FFmpeg streaming, TikTokLive y TTS
├── web_dashboard.html   # Panel web para controlar el live desde tu celular o PC
├── config.json          # Configuración inicial del agente
└── requirements.txt     # Dependencias de Python
```

---

## 🚀 Despliegue en tu VPS con Coolify

### Paso 1: Crear el servicio en Coolify
1. En tu panel de **Coolify**, haz clic en **+ New Resource** $\rightarrow$ **Docker Compose**.
2. Pega el contenido de [`docker-compose.yml`](docker-compose.yml):
   ```yaml
   version: '3.8'

   services:
     sensei-del-amor:
       build: .
       container_name: tiktok-sensei-amor
       restart: unless-stopped
       ports:
         - "8080:8080"
       environment:
         - PORT=8080
         - TIKTOK_USERNAME=tu_usuario_de_tiktok
         - VOICE=es-MX-JorgeNeural
         - ESTILO_CONSEJO=sabio_directo
         # - GEMINI_API_KEY=tu_clave_opcional
   ```
3. Asigna un dominio en Coolify (ej. `https://sensei.tudominio.com`) o usa el puerto directo `http://IP_DE_TU_VPS:8080`.
4. Haz clic en **Deploy**.

---

## 🎛️ Cómo Usar el Panel Web del Sensei

1. Entra a `http://IP_DE_TU_VPS:8080` desde cualquier navegador (PC o celular).
2. Verás el **Panel de Control del Sensei del Amor** (estilo templo oriental y neón carmesí).
3. Introduce:
   - **Tu usuario de TikTok** (ej: `sensei_del_amor`).
   - La **URL RTMP** y tu **Stream Key** de TikTok.
   - Elige el estilo de consejo y la voz (por defecto `es-MX-JorgeNeural`, voz masculina profunda).
4. Haz clic en **🏮 Iniciar Transmisión del Sensei en TikTok**.

---

## 💡 Temáticas que Responde en Vivo Automáticamente

El motor local y la IA vienen calibrados para responder consultas sobre:
- **Infidelidades:** ¿Perdonar o no perdonar? ¿Por qué la gente engaña?
- **El/La Ex:** ¿Volver con el ex? ¿Aplicar contacto cero? ¿Por qué me busca después de meses?
- **Falta de interés:** ¿Por qué me deja en visto? ¿Por qué tarda horas en contestar?
- **Los "Casi Algo":** ¿Por qué no quiere formalizar después de meses saliendo?
- **Celos y Red Flags:** ¿Revisar el teléfono? ¿Amistades íntimas que generan dudas?
- **Amor Propio:** Cómo superar una ruptura y recuperar la paz mental.
