#!/usr/bin/env python3
"""
Motor Sommelier de Perfumería Fina y Fragancias Árabes
Conocimiento enciclopédico de esencias, notas olfativas, clones de diseñador,
rendimiento y recomendaciones en vivo para transmisiones de TikTok Live Shopping.
"""

import re
import random

PERFUMES_DB = {
    "sauvage": {
        "nombre": "Sauvage / Sauvage Elixir (Dior)",
        "salida": "Pimienta de Sichuan, bergamota de Calabria y cardamomo",
        "corazon": "Lavanda francesa, nuez moscada y canela tibia",
        "fondo": "Regaliz rico, ambroxan, pachulí y maderas de sándalo",
        "clon_arabe": "Asad de Lattafa",
        "estilo": "Bestia nocturna de cumplidos masculinos, magnético e imponente.",
        "ocasion": "Citas nocturnas, eventos formales y salidas de conquista.",
        "duracion": "10 a 14 horas con estela pesada"
    },
    "khamrah": {
        "nombre": "Khamrah / Khamrah Qahwa (Lattafa)",
        "salida": "Canela dulce, nuez moscada y bergamota",
        "corazon": "Dátiles maduros, praliné crujiente, nardos y café árabe tostado",
        "fondo": "Vainilla embriagadora, haba tonka, benjuí y madera de akigalawood",
        "clon_arabe": "Inspirado en el ADN licoroso de Angels' Share de Kilian",
        "estilo": "El rey gourmand más viral de TikTok: dulce, cálido, comestible y adictivo.",
        "ocasion": "Climas fríos, citas románticas de invierno y cenas íntimas.",
        "duracion": "Más de 12 horas en piel y días en ropa"
    },
    "asad": {
        "nombre": "Asad de Lattafa (100ml)",
        "salida": "Pimienta negra picante, piña ahumada y tabaco rubio",
        "corazon": "Café espresso oscuro, iris sedoso y pachulí terroso",
        "fondo": "Vainilla bourbon, ámbar seco, benjuí y maderas nobles",
        "clon_arabe": "Hermano gemelo árabe y clon directo de Sauvage Elixir",
        "estilo": "Masculino, potente, licoroso y especiado. Cuesta una fracción del diseñador.",
        "ocasion": "Noche, climas templados o fríos y cuando quieras que todo el mundo te voltee a ver.",
        "duracion": "10 a 12 horas de duración garantizada"
    },
    "club de nuit": {
        "nombre": "Club de Nuit Intense Man (Armaf)",
        "salida": "Limón chispeante ahumado, grosellas negras, manzana verde y piña",
        "corazon": "Abedul ahumado oscuro, jazmín silvestre y rosa",
        "fondo": "Ámbar gris mineral, almizcle blanco, pachulí y vainilla sutil",
        "clon_arabe": "El clon indiscutible y más respetado de Creed Aventus",
        "estilo": "La mayor bestia de cumplidos del mundo; proyecta estatus, liderazgo y poder.",
        "ocasion": "Uso diario, oficina, reuniones de negocios, eventos y citas casuales.",
        "duracion": "8 a 10 horas con proyección fuerte"
    },
    "yara": {
        "nombre": "Yara Rosa / Yara Tous / Yara Candy (Lattafa)",
        "salida": "Orquídeas suaves, heliotropo, frutos rojos y mango tropical (en Yara Tous)",
        "corazon": "Acorde goloso de malvavisco, frutas exóticas, jazmín y leche de coco",
        "fondo": "Vainilla cremosa de Madagascar, almizcle blanco y sándalo suave",
        "clon_arabe": "Creación original árabe viral de Lattafa",
        "estilo": "Femenino, dulce, tierno, coqueto e irresistiblemente adictivo.",
        "ocasion": "Diario, salidas con amigas, citas y cuando quieras recibir halagos constantes.",
        "duracion": "7 a 9 horas de fijación sedosa"
    },
    "baccarat": {
        "nombre": "Baccarat Rouge 540 (Maison Francis Kurkdjian)",
        "salida": "Azafrán oriental exquisito y jazmín sambac blanco",
        "corazon": "Amberwood (madera ambarada) y ámbar gris mineral hipnótico",
        "fondo": "Resina de abeto y cedro recién cortado",
        "clon_arabe": "Inspiración presente en Baroque Satin Oud y Club de Nuit Untold",
        "estilo": "El perfume del dinero y la alta alcurnia; secado de algodón de azúcar cristalizado ultra lujoso.",
        "ocasion": "Gala, eventos de etiqueta negra y momentos inolvidables.",
        "duracion": "Estela infinita que llena una habitación"
    },
    "creed aventus": {
        "nombre": "Creed Aventus",
        "salida": "Piña asada ahumada, bergamota italiana, grosellas negras y manzana",
        "corazon": "Abedul oscuro, pachulí seco, jazmín y bayas de enebro",
        "fondo": "Musgo de roble, ámbar gris, almizcle y vainilla",
        "clon_arabe": "Capturado magistralmente en Club de Nuit Intense Man",
        "estilo": "El aroma de los reyes y empresarios exitosos; éxito puro.",
        "ocasion": "Reuniones de alto impacto, trabajo y firmas de contratos.",
        "duracion": "Proyección limpia y distinguida"
    },
    "tobacco vanille": {
        "nombre": "Tobacco Vanille (Tom Ford)",
        "salida": "Hojas de tabaco rubio curado y especias aromáticas de oriente",
        "corazon": "Vainilla dulce bourbon, cacao amargo, flor de tabaco y haba tonka",
        "fondo": "Frutos secos confitados y savia de maderas ricas",
        "clon_arabe": "ADN presente en Charuto Tobacco Vanille y Al Haramain Amber Oud Tobacco",
        "estilo": "Oscuro, aristocrático, cálido, seductor y opulento.",
        "ocasion": "Otoño, invierno, noche y citas románticas elegantes.",
        "duracion": "Más de 12 horas en piel"
    },
    "ombre leather": {
        "nombre": "Ombré Leather (Tom Ford)",
        "salida": "Cardamomo especiado negro",
        "corazon": "Cuero negro curtido refinado y jazmín sambac",
        "fondo": "Ámbar cálido, musgo blanco y pachulí terroso",
        "clon_arabe": "Aficionado en Rare Carbon de Afnan",
        "estilo": "Pura chaqueta de cuero fina, misterio, moto de lujo y presencia ruda pero elegante.",
        "ocasion": "Noche, climas templados o fríos y eventos exclusivos.",
        "duracion": "10 a 12 horas con aura penetrante"
    },
    "jean paul gaultier": {
        "nombre": "Jean Paul Gaultier (Le Male Elixir / Ultra Male / Scandal)",
        "salida": "Menta crujiente fresca, bergamota, lavanda y pera confitada (en Ultra Male)",
        "corazon": "Miel dorada líquida, canela aromática, haba tonka tostada y flor de azahar",
        "fondo": "Vainilla negra de Madagascar, benjuí resinoso y tabaco",
        "clon_arabe": "Capturado a la perfección en 9PM de Afnan y Glacier Le Noir",
        "estilo": "El rey absoluto de las fiestas y discotecas; dulzor magnético e hiper atractivo.",
        "ocasion": "Fiestas, salidas nocturnas, boliches y conquista.",
        "duracion": "10 horas de fiesta sin apagarse"
    },
    "acqua di gio": {
        "nombre": "Acqua Di Gio / Profondo (Giorgio Armani)",
        "salida": "Notas marinas del Mediterráneo, bergamota verde calabresa y mandarina",
        "corazon": "Romero fresco, lavanda aromática, ciprés y lentisco",
        "fondo": "Pachulí mineral limpio, almizcle blanco y ámbar mineral",
        "clon_arabe": "Su vibra fresca la encuentras en Suqraat de Lattafa",
        "estilo": "El estándar mundial de la frescura acuática y la limpieza masculina implacable.",
        "ocasion": "Calor extremo, verano, playa, gimnasio y uso diario en oficina.",
        "duracion": "6 a 8 horas de brisa marina revitalizante"
    },
    "versace eros": {
        "nombre": "Versace Eros / Eros Flame",
        "salida": "Menta fresca triturada, manzana verde ácida, cáscara de limón italiano y mandarina (en Flame)",
        "corazon": "Haba tonka venezolana, ambroxan mineral, geranio y pimienta negra",
        "fondo": "Vainilla de Madagascar, cedro de Virginia, vetiver y musgo de roble",
        "clon_arabe": "Inspiración en Glacier Bold y Victorioso Nero",
        "estilo": "Pasión juvenil, alegría, seducción radiante y brillo en discotecas.",
        "ocasion": "Salidas nocturnas con amigos, citas informales y fiestas.",
        "duracion": "8 a 10 horas de energía pura"
    },
    "9pm": {
        "nombre": "9PM de Afnan (100ml)",
        "salida": "Manzana crujiente verde, canela salvaje, lavanda silvestre y bergamota",
        "corazon": "Flor de azahar del naranjo y lirio de los valles",
        "fondo": "Vainilla cremosa, haba tonka dulce, ámbar dorado y pachulí",
        "clon_arabe": "El clon mejorado y más famoso de Ultra Male de Jean Paul Gaultier",
        "estilo": "Dulce, juvenil, fiestero y versátil; abre con una manzana deliciosa y seca en vainilla.",
        "ocasion": "Noche, citas, fiestas y salidas donde quieras destacar.",
        "duracion": "8 a 10 horas con excelente proyección"
    },
    "hawas": {
        "nombre": "Hawas for Him (Rasasi)",
        "salida": "Manzana ácida, ciruela dulce madura, cardamomo, bergamota y limón",
        "corazon": "Notas acuáticas frescas, canela aromática, flor de azahar y romero",
        "fondo": "Ámbar gris mineral marino, almizcle blanco, pachulí y madera flotante",
        "clon_arabe": "Inspirado en el espíritu acuático especiado de Invictus Aqua pero con ciruela dulce",
        "estilo": "Bestia acuática marina con toque afrutado dulce que resiste sudor y calor extremo.",
        "ocasion": "Verano, playa, piscina, calor y diario.",
        "duracion": "Más de 9 horas de frescura garantizada"
    },
    "bade'e al oud": {
        "nombre": "Bade'e Al Oud (Honor & Glory / Oud for Glory de Lattafa)",
        "salida": "Piña caramelizada braseada, crème brûlée y canela (en Honor & Glory) / Azafrán y nuez moscada (en Oud for Glory)",
        "corazon": "Benjuí resinoso, cúrcuma cálida, pimienta negra y lavanda",
        "fondo": "Vainilla bourbon, sándalo cremoso, madera de oud ahumada y pachulí",
        "clon_arabe": "Oud for Glory es el clon de Oud for Greatness de Initio; Honor & Glory es una creación gourmet",
        "estilo": "Misterio árabe, opulencia, sofisticación dulce y estela imponente.",
        "ocasion": "Noches especiales, eventos formales, frío y citas exclusivas.",
        "duracion": "10 a 14 horas de longevidad brutal"
    },
    "fakhar black": {
        "nombre": "Fakhar Black de Lattafa (100ml)",
        "salida": "Manzana crujiente verde, jengibre fresco picante y bergamota",
        "corazon": "Salvia esclarea aromática, bayas de enebro y geranio silvestre",
        "fondo": "Madera de ámbar seco, haba tonka, vetiver y cedro",
        "clon_arabe": "El clon directo más elogiado de Y Eau de Parfum de Yves Saint Laurent",
        "estilo": "El rey todoterreno de la elegancia moderna; limpio, varonil, sofisticado y fresco.",
        "ocasion": "Oficina, universidad, reuniones, citas de día o noche. Sirve para todo el año.",
        "duracion": "7 a 9 horas de cumplidos constantes"
    },
    "nebras": {
        "nombre": "Nebras de Lattafa (100ml)",
        "salida": "Frutos rojos oscuros, mandarina y azúcar moreno",
        "corazon": "Cacao puro en polvo, rosa delicada y vainilla cremosa",
        "fondo": "Haba tonka dulce, ámbar tibio y almizcle blanco",
        "clon_arabe": "El clon idéntico de Eilish de Billie Eilish",
        "estilo": "Un chocolate caliente con frutos rojos y vainilla sedosa; adictivo y sensual.",
        "ocasion": "Citas íntimas, frío, noches románticas y cuando quieras oler a postre de lujo.",
        "duracion": "8 a 10 horas de abrazo acogedor"
    },
    "bleu de chanel": {
        "nombre": "Bleu de Chanel",
        "salida": "Pomelo chispeante, limón, menta fresca y pimienta rosa",
        "corazon": "Jengibre, nuez moscada, jazmín y cedro",
        "fondo": "Incienso ahumado misterioso, sándalo de Nueva Caledonia y pachulí",
        "clon_arabe": "Capturado en Club de Nuit Blue Iconic de Armaf",
        "estilo": "El rey de los perfumes azules: versatilidad suprema, elegancia ejecutiva y masculinidad pulcra.",
        "ocasion": "Cualquier ocasión, clima y hora del día. Imposible fallar con este ADN.",
        "duracion": "8 horas de aura limpia y refinada"
    }
}

def obtener_sommelier_experto(usuario: str, pregunta: str, agent: dict) -> tuple:
    """
    Analiza la pregunta del cliente con ojos y nariz de Maestro Sommelier.
    Distingue con elegancia entre preguntas de curiosidad/opinión vs intención de compra.
    """
    q = pregunta.lower().strip()
    nombre = usuario.split("_")[0].capitalize()
    if nombre.lower().startswith("user") and any(c.isdigit() for c in nombre):
        nombre = "amigo"

    nombre_agente = agent.get("name", "Salomé")
    if "salome" in nombre_agente.lower():
        presentador = "Salomé"
    elif "don perfume" in nombre_agente.lower():
        presentador = "Don Perfume"
    else:
        presentador = nombre_agente.split("·")[0].strip()

    cta = agent.get("call_to_action", "Toca el enlace de mi biografía para pedir el tuyo con envío gratis hoy.")
    prods_destacados = agent.get("featured_products", [])
    cat_names = [p.get("name", "") for p in prods_destacados]

    # Detector de intención de compra
    quiere_comprar = any(k in q for k in [
        "comprar", "precio", "cuanto", "cuánto", "vale", "vendes", "venden", "costo", "cuesta",
        "donde", "dónde", "envio", "envío", "pedido", "pedir", "adquirir", "tienen", "stock",
        "disponible", "disponibles", "catalogo", "catálogo", "link", "enlace", "quiero uno", "quiero comprar"
    ])

    # 1. BÚSQUEDA DE PERFUMES ESPECÍFICOS POR NOMBRE / MARCA
    for key, p in PERFUMES_DB.items():
        # Match directo de la clave o palabras clave asociadas (incluyendo errores ortográficos comunes)
        matches = [key]
        if key == "sauvage": matches.extend(["sauvage", "elixir", "dior sauvage", "sauvage elixir", "sauvach", "sauvaj", "sauvaje"])
        elif key == "club de nuit": matches.extend(["club de nuit", "cdnim", "armaf", "club de nuit intense", "club denuit", "intense man"])
        elif key == "khamrah": matches.extend(["khamrah", "qahwa", "kamrah", "cahwa", "lattafa khamrah"])
        elif key == "asad": matches.extend(["asad", "asad de lattafa", "asad lattafa", "azad"])
        elif key == "yara": matches.extend(["yara", "yara tous", "yara rosa", "yara candy", "yara moi"])
        elif key == "baccarat": matches.extend(["baccarat", "bacarat", "bakarat", "baccarat rouge", "br540", "rouge 540"])
        elif key == "creed aventus": matches.extend(["creed", "aventus", "abentus", "creed aventus"])
        elif key == "jean paul gaultier": matches.extend(["jean paul", "gaultier", "gultier", "jean pol", "jpg", "le male", "ultra male", "le male elixir", "scandal"])
        elif key == "acqua di gio": matches.extend(["acqua", "aqua", "adg", "gio", "profondo", "armani gio", "acqua di"])
        elif key == "versace eros": matches.extend(["versace", "eros", "versache", "eros flame"])
        elif key == "9pm": matches.extend(["afnan 9pm", "9 pm", "9pm"])
        elif key == "hawas": matches.extend(["rasasi hawas", "hawas rasasi", "hawas"])
        elif key == "bade'e al oud": matches.extend(["honor and glory", "honor & glory", "oud for glory", "bade e al oud", "badee al oud", "bade'e"])
        elif key == "fakhar black": matches.extend(["fakhar", "fakhar de lattafa", "fakhar black"])
        elif key == "nebras": matches.extend(["nebras", "nebras lattafa", "eilish"])
        elif key == "bleu de chanel": matches.extend(["chanel bleu", "bleu", "chanel", "blue de chanel"])
        elif key == "tobacco vanille": matches.extend(["tobacco vanille", "tobaco", "tom ford tobacco"])
        elif key == "ombre leather": matches.extend(["ombre leather", "leather", "cuero tom ford"])

        if any(m in q for m in matches):
            if quiere_comprar:
                texto = (
                    f"¡Excelente elección, {nombre}! {p['nombre']} lo tenemos disponible en nuestra boutique con máxima fijación garantizada y envío prioritario. "
                    f"Abre con notas de {p['salida']}, corazón de {p['corazon']} y una duración épica de {p['duracion']}. {cta}"
                )
                return (texto, "VENTA")
            else:
                texto = (
                    f"¡Excelente gusto, {nombre}! {p['nombre']} es una obra maestra olfativa. "
                    f"Abre con notas de {p['salida']}, corazón seductor de {p['corazon']} y seca en un fondo cálido de {p['fondo']}. "
                    f"Es ideal para {p['ocasion']} con una duración de {p['duracion']}. "
                    f"Dime, {nombre}, ¿tú prefieres fragancias así de intensas y cumplidoras, o buscas algo más discreto para el día a día?"
                )
                return (texto, "RECOMENDACION")

    # 2. CONSULTAS POR OCASIÓN Y CONQUISTA
    # A) Cita nocturna / Seducción / Romance
    if any(k in q for k in ["cita", "romance", "conquistar", "seducir", "novia", "novio", "pareja", "crush", "noche", "íntimo", "intimo"]):
        if quiere_comprar:
            texto = (
                f"Para citas inolvidables, {nombre}, mis recomendaciones de boutique son **Khamrah de Lattafa** y **Asad**: "
                f"notas de canela dulce, maderas ahumadas y vainilla cremosa. "
                f"Disponibles con envío inmediato tocando el enlace de mi biografía. {cta}"
            )
            return (texto, "VENTA")
        else:
            texto = (
                f"Para una cita donde quieras dejar una huella imborrable, {nombre}, necesitas notas cálidas, licorosas y golosas que inviten al abrazo: "
                f"canela dulce, dátiles maduros, vainilla cremosa o maderas ahumadas. "
                f"Joyas como **Khamrah de Lattafa** o **Asad** son imanes de cumplidos que proyectan magnetismo puro. "
                f"Cuéntame, {nombre}, ¿a qué tipo de cita vas a ir? ¿Cena elegante, noche de fiesta o algo más íntimo?"
            )
            return (texto, "SABIO")

    # B) Oficina / Trabajo / Universidad / Diario
    if any(k in q for k in ["oficina", "trabajo", "diario", "universidad", "firma", "reunión", "reunion", "elegante", "formal"]):
        if quiere_comprar:
            texto = (
                f"Para oficina y trabajo, {nombre}, te recomiendo **Club de Nuit Intense Man** o **Fakhar Black**: "
                f"proyectan pulcritud ejecutiva y estatus. Pide el tuyo en el enlace de mi perfil con envío rápido. {cta}"
            )
            return (texto, "VENTA")
        else:
            texto = (
                f"Para tu jornada diaria o entorno profesional, {nombre}, buscas un aroma con presencia ejecutiva pero sin saturar: "
                f"bergamota chispeante, manzana verde, abedul ahumado y ambroxan limpio. "
                f"Tus mejores aliados son **Club de Nuit Intense Man** o **Fakhar Black de Lattafa**; proyectan liderazgo y pulcritud. "
                f"Oye, {nombre}, ¿en tu trabajo pasas el día con aire acondicionado o estás más tiempo en movimiento?"
            )
            return (texto, "RECOMENDACION")

    # C) Calor / Verano / Playa / Gimnasio
    if any(k in q for k in ["calor", "verano", "playa", "sol", "fresco", "frescura", "sudor", "gym", "gimnasio", "deporte", "mar"]):
        if quiere_comprar:
            texto = (
                f"Para calor y alta frescura, {nombre}, te sugiero **Hawas de Rasasi** o **Acqua Di Giò Profondo**: "
                f"notas acuáticas y cítricas que duran todo el día. Consíguelo en el enlace de nuestra boutique hoy mismo. {cta}"
            )
            return (texto, "VENTA")
        else:
            texto = (
                f"En climas cálidos o para entrenar, {nombre}, jamás uses perfumes dulces pesados porque marean. "
                f"La clave está en acordes acuáticos salinos, ciruela helada, pomelo amargo y almizcle blanco. "
                f"**Rasasi Hawas** o **Acqua Di Giò Profondo** son reyes acuáticos: duran horas en el calor con un halo de limpieza deportiva insuperable. "
                f"¿Prefieres los cítricos marinos estilo playa o algo más aromático jabonoso?"
            )
            return (texto, "RECOMENDACION")

    # D) Fiesta / Boliche / Discoteca / Antro
    if any(k in q for k in ["fiesta", "discoteca", "antro", "boliche", "rumba", "salir", "destacar"]):
        if quiere_comprar:
            texto = (
                f"Para destacar en la discoteca, {nombre}, las bestias son **9PM de Afnan** o **Le Male Elixir**. "
                f"Pídelo ya antes de que se agoten en el link de la biografía. {cta}"
            )
            return (texto, "VENTA")
        else:
            texto = (
                f"Para salir de fiesta donde compites contra aire acondicionado, humo y multitudes, {nombre}, necesitas proyección explosiva: "
                f"manzana dulce, canela, miel dorada y vainilla negra. "
                f"Tus armas secretas son **9PM de Afnan** o **Le Male Elixir**; cortan el aire al instante y hacen que todas las miradas giren hacia ti. "
                f"¿A ti te gusta ser el centro de atención que proyecta modo bestia en la pista, o buscas algo más seductor de cerca?"
            )
            return (texto, "SABIO")

    # E) Perfumes Femeninos Dulces y Virales
    if any(k in q for k in ["mujer", "femenino", "chica", "dulce mujer", "para mi novia", "para dama", "dama"]):
        if quiere_comprar:
            texto = (
                f"Para dama, {nombre}, las joyas más pedidas son **Yara Rosa de Lattafa** y **Nebras**: "
                f"vainilla, malvavisco y mango tropical. Disponibles con empaque de lujo en el enlace de mi biografía. {cta}"
            )
            return (texto, "VENTA")
        else:
            texto = (
                f"¡Para mujeres radiantes y magnéticas, {nombre}! En perfumería femenina la tendencia viral número uno es el acorde de "
                f"orquídeas suaves, malvavisco esponjoso, mango tropical y vainilla cremosa. "
                f"**Yara Rosa de Lattafa** y **Nebras** son verdaderas joyas que despiertan halagos donde sea que vayas; huelen a postre fino de boutique. "
                f"¿Te gustan los aromas dulces gourmand tipo postre o prefieres algo más floral y delicado?"
            )
            return (texto, "RECOMENDACION")

    # 3. CONSULTAS POR NOTAS O FAMILIAS OLFATIVAS
    if any(k in q for k in ["tabaco", "cigar", "smoke"]) and any(k in q for k in ["vainilla", "vanille"]):
        if quiere_comprar:
            texto = (
                f"Esa combinación de tabaco y vainilla bourbon la encuentras en nuestra bestia **Asad de Lattafa**, {nombre}. "
                f"Pide el tuyo en el enlace de nuestra biografía con envío inmediato. {cta}"
            )
            return (texto, "VENTA")
        else:
            texto = (
                f"¡Esa combinación es de las más sensuales y aristocráticas del mundo, {nombre}! "
                f"El tabaco curado combinado con vainilla bourbon crea un aura oscura, cálida y de puro millonario. "
                f"Te recomiendo fragancias como **Tobacco Vanille de Tom Ford** o **Asad de Lattafa**, con tabaco rubio, café y vainilla. "
                f"¿Has probado la vainilla combinada con licor o café? Es de las experiencias olfativas más adictivas que existen."
            )
            return (texto, "SABIO")

    if any(k in q for k in ["vainilla", "vanille", "dulce", "gourmand"]):
        if quiere_comprar:
            texto = (
                f"Si buscas vainilla gourmand de máxima fijación, {nombre}, tenemos **Khamrah de Lattafa** y **Nebras**. "
                f"Revisa nuestro catálogo en el enlace de la bio para ordenar el tuyo. {cta}"
            )
            return (texto, "VENTA")
        else:
            texto = (
                f"Si amas la vainilla, {nombre}, debes buscar vainilla bourbon de Madagascar combinada con haba tonka o café para que no huela infantil sino ultra sensual. "
                f"**Khamrah de Lattafa** y **Nebras** tienen esa vainilla cremosa y embriagadora que se funde en la piel como una caricia. "
                f"¿A ti te gustan las vainillas esponjosas tipo postre o prefieres una vainilla amaderada más madura?"
            )
            return (texto, "RECOMENDACION")

    if any(k in q for k in ["tabaco", "cigar", "smoke"]):
        if quiere_comprar:
            texto = (
                f"En notas de tabaco y especias finas, {nombre}, nuestra estrella es **Asad de Lattafa**. "
                f"Ordena el tuyo tocando el enlace de mi biografía antes de que vuelen. {cta}"
            )
            return (texto, "VENTA")
        else:
            texto = (
                f"Las notas de tabaco rubio curado, {nombre}, aportan una vibra madura, masculina y sumamente aristocrática, especialmente cuando se mezclan con vainilla, café y especias. "
                f"Fragancias como **Asad de Lattafa** destacan con su corazón de café espresso, tabaco y pimienta negra. "
                f"¿Prefieres el tabaco dulce con miel y vainilla o el tabaco seco y ahumado más rudo?"
            )
            return (texto, "SABIO")

    if any(k in q for k in ["oud", "madera", "amaderado", "cedro", "sandalo", "sándalo"]):
        if quiere_comprar:
            texto = (
                f"Para maderas nobles y Oud oriental de más de 12 horas, {nombre}, te sugiero **Bade'e Al Oud** o **Club de Nuit**. "
                f"Pídelo en el link de la biografía con envío gratis hoy. {cta}"
            )
            return (texto, "VENTA")
        else:
            texto = (
                f"Las maderas nobles y el Oud oriental, {nombre}, son el sello indiscutible de la alta perfumería árabe: aportan profundidad, misterio y una fijación de más de 12 horas. "
                f"Fragancias como **Bade'e Al Oud** o **Club de Nuit Intense Man** secan con maderas ahumadas y ámbar mineral que imponen respeto y elegancia pura. "
                f"¿Buscas un oud oriental profundo y oscuro de jeque, o prefieres maderas más suaves y ejecutivas?"
            )
            return (texto, "RECOMENDACION")

    # 4. PREGUNTAS DE RENDIMIENTO / DURACIÓN / FIJACIÓN
    if any(k in q for k in ["duracion", "duración", "dura", "estela", "fijacion", "fijación", "proyeccion", "proyección", "horas", "piel"]):
        if quiere_comprar:
            texto = (
                f"Todas nuestras fragancias son concentración Eau de Parfum y Extracto de Perfume, {nombre}, con aceites macerados de 10 a 14 horas de fijación. "
                f"¡Pide tu fragancia árabe favorita en el enlace de nuestra biografía! {cta}"
            )
            return (texto, "VENTA")
        else:
            texto = (
                f"En perfumería árabe de calidad, {nombre}, la duración se logra con aceites macerados de alta pureza y bases de ámbar y resinas. "
                f"Fragancias como **Asad**, **Club de Nuit** y **Khamrah** entregan fácilmente entre 10 y 14 horas en piel y días en ropa. "
                f"Dime, {nombre}, ¿en tu piel los perfumes suelen durar poco o tienes buena fijación natural?"
            )
            return (texto, "SABIO")

    # 5. PREGUNTAS SOBRE CLONES / ÁRABES VS ORIGINALES
    if any(k in q for k in ["clon", "clones", "arabe", "árabe", "dupe", "inspiracion", "inspiración", "original"]):
        if quiere_comprar:
            texto = (
                f"¡Los mejores clones árabes de alta calidad los tenemos en catálogo, {nombre}! "
                f"Descubre todas las joyas inspiradas en diseñadores tocando el enlace de nuestra biografía. {cta}"
            )
            return (texto, "VENTA")
        else:
            texto = (
                f"¡Es la gran revolución olfativa, {nombre}! Casas árabes como Lattafa, Armaf, Afnan y Rasasi utilizan los mismos aceites esenciales franceses que marcas de $300 USD pero sin el sobreprecio del marketing. "
                f"Por ejemplo, **Asad** te da el 95% de Sauvage Elixir, y **Club de Nuit** el ADN exacto de Creed Aventus, pero con mayor duración. "
                f"¿Tú ya has probado fragancias árabes en tu piel, o sería tu primera experiencia con ellas?"
            )
            return (texto, "SABIO")

    # 6. RESPUESTA GENERAL Y CALUROSA DE BIENVENIDA A LA BOUTIQUE
    if quiere_comprar:
        texto = (
            f"¡Con todo gusto, {nombre}! Puedes explorar nuestro catálogo completo y pedir con envío prioritario en el enlace de mi biografía. {cta}"
        )
        return (texto, "VENTA")
    else:
        texto = (
            f"¡Bienvenido a nuestra boutique en vivo, {nombre}! Aquí somos apasionados de la alta perfumería de nicho, fragancias árabes y bestias de cumplidos. "
            f"Cuéntame, {nombre}, ¿qué perfume usas actualmente o cuál ha sido tu aroma favorito de todos los tiempos?"
        )
        return (texto, "RECOMENDACION")

