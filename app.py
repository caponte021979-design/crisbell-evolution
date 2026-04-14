"""
CRISBELL CARGO EXPRESS — WhatsApp Bot DEFINITIVO v8
Evolution API + Firebase Firestore
"""

import os, json, re, unicodedata, requests
from flask import Flask, request, jsonify
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime

app = Flask(__name__)

# ── EVOLUTION API CONFIG ───────────────────────────────────────
EVOLUTION_URL     = os.getenv("EVOLUTION_URL")       # https://tu-evolution.railway.app
EVOLUTION_API_KEY = os.getenv("EVOLUTION_API_KEY")   # tu api key
INSTANCE_NAME     = os.getenv("INSTANCE_NAME", "crisbell")
NUMERO_CRISTHIAN  = os.getenv("NUMERO_CRISTHIAN", "34642887582")

# ── ZONAS ──────────────────────────────────────────────────────
ZONA = ["asturias","gijon","oviedo","aviles","mieres","langreo","llanes",
        "cangas","navia","pola de siero","siero","pola","lugones",
        "pais vasco","bilbao","san sebastian","vitoria","donostia",
        "barakaldo","getxo","irun","eibar","santurtzi","basauri","durango",
        "cantabria","santander","torrelavega","castro","laredo","reinosa",
        "noja","solares","camargo","astillero","colindres",
        "valladolid","zamora","salamanca","medina","benavente","ciudad rodrigo"]

FUERA_ZONA = ["madrid","barcelona","valencia","sevilla","malaga","murcia",
              "alicante","zaragoza","granada","cordoba","palma","vigo",
              "coruña","cadiz","burgos","logroño","pamplona","toledo",
              "albacete","benidorm","tarragona","castellon","badajoz",
              "caceres","huelva","jaen","almeria","pontevedra","lugo",
              "orense","la bañeza","bañeza","santoña"]

DATOS_BANCARIOS = (
    "💳 *Datos para pagar:*\n\n"
    "💫 *CaixaBank:*\n"
    "ES26 2100 4312 0122 0012 8871\n\n"
    "🔥 *Banco Santander:*\n"
    "ES58 0049 5865 5323 1610 1317\n\n"
    "👤 *Titular:*\n"
    "CYG EXPORTACIONES E IMPORTACIONES S.L.\n"
    "_(Crisbell Cargo Express)_\n\n"
    "🇩🇴 *Banreservas RD:*\n"
    "Cuenta: 250-059955-3 (Ahorros)\n"
    "Titular: Cristhian Aponte\n\n"
    "📌 Pon tu nombre en el concepto\n"
    "y envíanos el comprobante aquí 😊"
)

PRECIOS_RD = (
    "🇩🇴 *República Dominicana — Marítimo:*\n\n"
    "📦 Mini (33×37×39 cm): *40€*\n"
    "📦 Pequeña (40×45×65 cm): *80€*\n"
    "📦 Mediana (50×50×73 cm): *120€*\n"
    "📦 Grande (50×50×100 cm): *150€*\n\n"
    "⭐ *Ofertas:*\n"
    "🔥 Mini + Grande: *170€*\n"
    "🔥 Mini + Mediana: *150€*\n\n"
    "⏱️ Entrega en ~30 días\n"
    "📦 Envío mínimo: 50€\n\n"
    "🚫 No se puede enviar:\n"
    "Pilas • Artículos comerciales\n"
    "Máx. 6 uds: cremas, colonias, medicinas\n\n"
    "¿Qué tamaño te interesa? 😊"
)

PRECIOS_VE = (
    "🇻🇪 *Venezuela:*\n\n"
    "✈️ *Por avión:* 16€/kg\n"
    "   Mínimo 3 kg\n"
    "   Entrega en oficina MRW\n\n"
    "🚢 *Por barco:*\n"
    "📦 Caja mini (33×37×39 cm)\n"
    "   Hasta 25 kg: *95€*\n"
    "📦 Caja estándar (40×45×65 cm)\n"
    "   Hasta 40 kg: *205€*\n"
    "   Entrega en oficina Aerocav\n\n"
    "¿Cuánto tienes para enviar? 😊"
)

INSTRUCCIONES_ENVIO = (
    "📦 *Antes de entregar tu caja:*\n\n"
    "📸 Fotografía el paquete con la etiqueta\n"
    "📦 Embálalo muy bien\n"
    "✍️ Escribe los datos de quien envía\n"
    "   y quien recibe\n\n"
    "💪 Entre los dos cuidamos tu envío\n"
    "¡Gracias por confiar en nosotros! 🙌"
)

# ── FIREBASE ───────────────────────────────────────────────────
cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred)
db = firestore.client()


# ══════════════════════════════════════════════════════════════
#  ENVIAR MENSAJE — Evolution API
# ══════════════════════════════════════════════════════════════
def enviar(tel, texto):
    # Evolution API usa formato diferente
    numero = tel.replace("@s.whatsapp.net","").replace("+","").replace(" ","")
    url = f"{EVOLUTION_URL}/message/sendText/{INSTANCE_NAME}"
    headers = {
        "Content-Type": "application/json",
        "apikey": EVOLUTION_API_KEY
    }
    payload = {
        "number": numero,
        "text": texto
    }
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=10)
        print(f"✅ {numero}: {r.status_code}")
    except Exception as e:
        print(f"❌ {e}")


# ══════════════════════════════════════════════════════════════
#  AVISAR A CRISTHIAN
# ══════════════════════════════════════════════════════════════
def avisar(motivo, tel, msg):
    t = tel.replace("@s.whatsapp.net","").replace("+","").replace(" ","")
    m = motivo.lower()
    if any(p in m for p in ["recogida","direccion","zona","ciudad"]):
        tipo = "📦 RECOGIDA"
    elif any(p in m for p in ["precio","tarifa","cotiza","colombia","venezuela","ecuador","bolivia","rd"]):
        tipo = "💰 PRECIO"
    elif any(p in m for p in ["salida","fecha","cuando"]):
        tipo = "📅 FECHA SALIDA"
    elif any(p in m for p in ["pago","cuenta","transfer","consign"]):
        tipo = "💳 PAGO"
    elif "audio" in m:
        tipo = "🎤 AUDIO"
    elif "agente" in m:
        tipo = "👤 AGENTE"
    else:
        tipo = "❓ CONSULTA"
    link = f"https://api.whatsapp.com/send?phone={t}"
    texto = (
        f"🔔 *{tipo}*\n"
        f"━━━━━━━━━━━━━━\n"
        f"📱 +{t}\n"
        f"💬 {msg[:200]}\n"
        f"━━━━━━━━━━━━━━\n"
        f"👆 Toca para responder:\n"
        f"{link}"
    )
    enviar(NUMERO_CRISTHIAN, texto)


# ══════════════════════════════════════════════════════════════
#  FIRESTORE
# ══════════════════════════════════════════════════════════════
def guardar(tel, msg_c, resp, agente=False):
    try:
        db.collection("whatsapp_chats").add({
            "telefono":tel,"mensaje_cliente":msg_c,"respuesta_bot":resp,
            "timestamp":datetime.utcnow(),
            "atendido_por":"pendiente" if agente else "bot",
            "requiere_agente":agente})
    except: pass

def buscar_exp(tel):
    t = tel.replace("@s.whatsapp.net","").replace("+","").replace(" ","")
    try:
        docs = db.collection("expediciones").where("telefonoCliente","==",t)\
                  .order_by("fecha",direction=firestore.Query.DESCENDING).limit(1).stream()
        for d in docs: return d.to_dict()
    except: pass
    return None

def buscar_cli(tel):
    t = tel.replace("@s.whatsapp.net","").replace("+","").replace(" ","")
    try:
        docs = db.collection("clientes").where("telefono","==",t).limit(1).stream()
        for d in docs: return d.to_dict()
    except: pass
    return None

def tarifas():
    try:
        d = db.collection("config").document("tarifas").get()
        if d.exists: return d.to_dict()
    except: pass
    return {}

def fechas_salida():
    try:
        d = db.collection("config").document("salidas").get()
        if d.exists: return d.to_dict()
    except: pass
    return {}

def colombia(t):
    a = t.get("co_aereo_ventaKg","—")
    m = t.get("co_mar_ventaDm3","—")
    return (
        "🇨🇴 *Colombia:*\n\n"
        f"✈️ *Por avión:* {a}€/kg\n"
        "   De 3 a 10 kg todo incluido\n"
        "   Llega en 8-10 días\n\n"
        f"🚢 *Por barco:* {m}€/dm³\n"
        "   Caja hasta 40 kg\n"
        "   Llega en 45-60 días\n\n"
        "¿Cuántos kilos tienes? 😊"
    )

def ecuador(t):
    e = t.get("ecu_ventaKg","—")
    return f"🇪🇨 *Ecuador por avión:* {e}€/kg\n\nDinos el peso y ciudad destino 😊"


# ══════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════
def limpiar(t):
    t = t.lower().strip()
    t = ''.join(c for c in unicodedata.normalize('NFKD',t) if not unicodedata.combining(c))
    return re.sub(r'\s+',' ',t)

def contiene(msg, palabras):
    return any(p in msg for p in palabras)

def detectar_pais(msg):
    if re.search(r'colom|medell|bogot|cali\b|barranq|cartagen', msg): return "colombia"
    if re.search(r'venezu|venezo|caracas|maracay|maracaib|barquisi', msg): return "venezuela"
    if re.search(r'\brd\b|dominicana|dominicna|santo domingo|rep.?dom|republica dom|la romana|san pedro', msg): return "rd"
    if re.search(r'ecuador|ecuad|quito|guayaquil', msg): return "ecuador"
    if re.search(r'bolivia|bolivi|la paz|santa cruz|cochabamba', msg): return "bolivia"
    return None

def en_zona(msg):
    return next((c for c in ZONA if limpiar(c) in msg), None)

def fuera_zona(msg):
    return next((c for c in FUERA_ZONA if limpiar(c) in msg), None)


# ══════════════════════════════════════════════════════════════
#  MOTOR DE RESPUESTAS
# ══════════════════════════════════════════════════════════════
def responder(tel, mensaje_orig):
    msg = limpiar(mensaje_orig)
    cli = buscar_cli(tel)
    nom = cli.get("nombre","").split()[0] if cli else ""
    sal = f"Hola {nom}! 😊\n" if nom else "Hola! 😊\n"
    T   = tarifas()
    p   = detectar_pais(msg)

    # BIENVENIDA
    if contiene(msg,["hola","buenas","buenos","buen dia","buen tarde","bendicion",
                     "saludos","ola ","que tal","como estan","buenos dias",
                     "buenas tardes","buenas noch","dios los","dios le"]):
        return (
            f"{sal}Bienvenido a *Crisbell Cargo Express* 🚢\n"
            "Acercándote a los tuyos 💚\n\n"
            "¿En qué te ayudamos?\n\n"
            "1️⃣ Ver mi envío\n"
            "2️⃣ Precios de envío\n"
            "3️⃣ Quiero enviar una caja\n"
            "4️⃣ Pedir caja vacía\n"
            "5️⃣ ¿Cuándo recogen?\n"
            "6️⃣ Datos para pagar\n"
            "7️⃣ Hablar con alguien\n\n"
            "Escribe el número o cuéntanos 👇"
        ), False

    # YA PAGUÉ
    if contiene(msg,["ya pague","ya pague","consigne","consigna","ya ingrese",
                     "ya ingrese","hice el pago","hice la transf","ya deposite",
                     "ya transferi","mande el dinero","ya mande"]):
        avisar("💳 Pago confirmado", tel, mensaje_orig)
        return (
            "✅ *¡Perfecto, gracias!*\n\n"
            "Ya avisamos al equipo.\n"
            "Te confirmamos en cuanto\n"
            "verifiquemos el pago 😊\n\n"
            "Puedes enviarnos el comprobante\n"
            "aquí mismo 📄"
        ), False

    # DATOS BANCARIOS
    if contiene(msg,["cuenta","iban","transferencia","deposito","depositar",
                     "pagar","numero de cuenta","como pago","donde pago",
                     "banco","caixa","santander","banreservas","6"]):
        return DATOS_BANCARIOS, False

    # CAJA VACÍA
    if contiene(msg,["caja vacia","caja vacia","quiero una caja","me trae",
                     "me manda una caja","necesito una caja","caja para llenar",
                     "cajas vacias","solicitar caja","pedir caja","4"]):
        return (
            "📦 *Solicitar caja vacía:*\n\n"
            "1️⃣ Haz un depósito de *15€*\n"
            "2️⃣ Envíanos el justificante aquí\n"
            "3️⃣ Dinos tu dirección completa\n\n"
            "También puedes pedirla en:\n"
            "🌐 crisbellcargoexpress.com/cajas\n\n"
            "¿Necesitas los datos bancarios?\n"
            "Escribe *6* 😊"
        ), False

    # VER ENVÍO
    if contiene(msg,["mi caja","mi envio","llego","no ha llegado",
                     "cuando llega","donde esta","mi paquete","referencia",
                     "cbce","1","seguimiento","tracking","saber del envio"]):
        exp = buscar_exp(tel)
        if exp:
            return (
                f"📦 *Tu último envío:*\n\n"
                f"🔖 Número: `{exp.get('referencia',exp.get('id',''))}`\n"
                f"📍 Destino: {exp.get('destino','')}\n"
                f"🔄 Estado: *{exp.get('estado','En camino')}*\n"
                f"📅 Salió: {exp.get('fechaSalida','Pendiente')}\n\n"
                "Rastrear en:\n"
                "🌐 crisbellcargoexpress.com/rastrear\n\n"
                "¿Más info? Escribe *7* 😊"
            ), False
        avisar("Pregunta por su envío", tel, mensaje_orig)
        return (
            f"{sal}No encontré envíos con tu número.\n\n"
            "Puedes rastrear en:\n"
            "🌐 crisbellcargoexpress.com/rastrear\n\n"
            "O dinos tu número CBCE-XXXX 😊"
        ), False

    # CUÁNDO RECOGEN
    if contiene(msg,["cuando recogen","cuando pasan","cuando van","cuando vienen",
                     "a que hora","que hora pasan","recogida","recojer","recoger",
                     "5","van a pasar","me recogen","cuanto tiempo"]):
        zona  = en_zona(msg)
        fuera = fuera_zona(msg)
        if fuera and not zona:
            avisar(f"Recogida fuera de zona: {fuera}", tel, mensaje_orig)
            return (
                f"📍 En *{fuera.title()}* no tenemos\n"
                "recogida habitual.\n\n"
                "Nuestras zonas:\n"
                "• Asturias · País Vasco · Cantabria\n"
                "• Valladolid · Zamora · Salamanca\n\n"
                "Ya avisamos al equipo para\n"
                "buscar solución 😊"
            ), True
        return (
            "🚚 *Recogidas a domicilio:*\n\n"
            "Cuando tengas la caja lista\n"
            "dinos tu dirección y te decimos\n"
            "qué día pasamos 📅\n\n"
            "O rellena:\n"
            "🌐 crisbellcargoexpress.com/formulario\n\n"
            "¿En qué ciudad estás? 😊"
        ), False

    # FECHAS DE SALIDA
    if contiene(msg,["cuando salen","cuando sale","fecha de salida","proxima salida",
                     "proximo envio","proximo barco","cuando envian","para cuando",
                     "que fecha sale","esta salida","siguiente salida","proximo embarque",
                     "para que mes","este mes","llegar antes","llegar para",
                     "antes del","cuanto tarda","tiempo de llegada"]):
        fs = fechas_salida()
        if p == "rd" or contiene(msg,["dominicana","rd","santo domingo"]):
            avisar("Pregunta fecha salida RD", tel, mensaje_orig)
            proxima = fs.get("rd_proxima_salida","principios de mayo")
            llegada = fs.get("rd_llegada_estimada","principios de junio")
            return (
                "🇩🇴 *República Dominicana:*\n\n"
                f"📦 Próxima salida: *{proxima}* 🚢\n"
                "Ya estamos recogiendo cajas.\n\n"
                f"⏱️ Llega a destino: *{llegada}* ✅\n\n"
                "¿Quieres que recojamos tu caja?\n"
                "Escribe *5* y te lo coordinamos 😊"
            ), True
        avisar("Pregunta fecha próxima salida", tel, mensaje_orig)
        return (
            "📅 Las salidas dependen del destino.\n\n"
            "Un agente te confirma la fecha\n"
            "exacta para tu envío 😊\n\n"
            "¿A qué país quieres enviar?"
        ), True

    # TARIFAS
    if contiene(msg,["tarifa","precio","costo","cuanto","quanto","cuanto cuesta",
                     "cuanto vale","presupuesto","cotiza","cuanto es","2","3",
                     "que precio","valor del envio","cuanto cobran"]):
        if p == "rd":        return PRECIOS_RD, False
        if p == "venezuela": return PRECIOS_VE, False
        if p == "colombia":  return colombia(T), False
        if p == "ecuador":   return ecuador(T), False
        if p == "bolivia":
            avisar("Consulta Bolivia", tel, mensaje_orig)
            return ("🇧🇴 Para *Bolivia* un agente te da\nel precio exacto 😊\nEscribe *7*"), True
        return (
            "💰 *¿A qué país quieres enviar?*\n\n"
            "🇩🇴 República Dominicana\n"
            "🇨🇴 Colombia\n"
            "🇻🇪 Venezuela\n"
            "🇪🇨 Ecuador\n"
            "🇧🇴 Bolivia\n\n"
            "Dinos el país y te damos\n"
            "el precio al momento 😊"
        ), False

    # SOLO MENCIONA PAÍS
    if p:
        if p == "rd":        return PRECIOS_RD, False
        if p == "venezuela": return PRECIOS_VE, False
        if p == "colombia":  return colombia(T), False
        if p == "ecuador":   return ecuador(T), False
        if p == "bolivia":
            avisar("Consulta Bolivia", tel, mensaje_orig)
            return ("🇧🇴 Para *Bolivia* un agente te da\nel precio 😊\nEscribe *7*"), True

    # QUÉ PUEDO ENVIAR
    if contiene(msg,["puedo enviar","se puede","prohibido","puedo mandar",
                     "gel","crema","medicamento","medicina","pila","bateria",
                     "telefono","celular","liquido","comida","alimento"]):
        return (
            "📋 *¿Qué se puede enviar?*\n\n"
            "✅ Ropa, zapatos, electrodomésticos,\n"
            "comida seca, cremas (máx. 6),\n"
            "medicinas (máx. 5-6 uds)\n\n"
            "🚫 No: pilas, baterías, líquidos,\n"
            "artículos para vender sin declarar\n\n"
            "🌐 crisbellcargoexpress.com\n\n"
            "¿Tienes duda de algo concreto? 😊"
        ), False

    # DIRECCIÓN DIRECTAMENTE
    if (contiene(msg,["calle","avenida","carrera","paseo","cll"]) and
        contiene(msg,["piso","portal","puerta","bajo","numero","num","bloque","apto"])):
        avisar("Cliente envió dirección", tel, mensaje_orig)
        return (
            "📍 *¡Gracias, apuntado!*\n\n"
            "Ya avisamos al equipo.\n"
            "Te decimos el día de recogida\n"
            "muy pronto 😊\n\n"
            + INSTRUCCIONES_ENVIO
        ), True

    # HORARIOS
    if contiene(msg,["horario","hora","abierto","cerrado","cuando abren"]):
        return (
            "🕐 *Horarios:*\n\n"
            "📅 Lunes-Viernes:\n"
            "   10:00-15:00 y 17:00-21:00\n"
            "📅 Sábados: 10:00-15:00\n"
            "🚫 Domingos y festivos: Cerrado\n\n"
            "📍 C. Jerónimo Sáinz de la Maza 1\n"
            "Santander · 📞 +34 942 32 30 50"
        ), False

    # OFICINA
    if contiene(msg,["donde estan","donde estais","oficina","direccion de","ubicacion"]):
        return (
            "📍 *Nuestra oficina:*\n\n"
            "C. Jerónimo Sáinz de la Maza 1\n"
            "Local 6, Santander (Cantabria)\n\n"
            "📞 +34 942 32 30 50\n"
            "📱 +34 653 70 02 34\n\n"
            "🕐 L-V: 10:00-15:00 y 17:00-21:00\n"
            "Sáb: 10:00-15:00"
        ), False

    # AGENTE
    if contiene(msg,["agente","persona","hablar","llamar","ayuda","7","cristian"]):
        avisar("Cliente solicita agente", tel, mensaje_orig)
        return (
            "👤 *Ya avisamos al equipo...*\n\n"
            "En breve te escribimos 😊\n\n"
            "⏰ L-V: 10:00-15:00 y 17:00-21:00\n"
            "Sábados: 10:00-15:00\n\n"
            "📞 +34 942 32 30 50"
        ), True

    # GRACIAS
    if contiene(msg,["gracias","gracia","muchas gracia","ok","vale",
                     "perfecto","de acuerdo","listo","entendido","adios","bendicion"]):
        return "😊 ¡Con mucho gusto!\nCualquier cosa, aquí estamos 💚", False

    # CIUDAD FUERA ZONA
    fuera = fuera_zona(msg)
    if fuera:
        avisar(f"Ciudad fuera de zona: {fuera}", tel, mensaje_orig)
        return (
            f"📍 Veo que estás en *{fuera.title()}*.\n\n"
            "Nuestras zonas habituales:\n"
            "Asturias · País Vasco · Cantabria\n"
            "Valladolid · Zamora · Salamanca\n\n"
            "Ya avisamos al equipo para\n"
            "buscarte solución 😊"
        ), True

    # GENÉRICA
    avisar("Mensaje no entendido", tel, mensaje_orig)
    return (
        f"{sal}Perdona, no entendí bien 😅\n\n"
        "1️⃣ Ver mi envío\n"
        "2️⃣ Precios de envío\n"
        "3️⃣ Quiero enviar una caja\n"
        "4️⃣ Pedir caja vacía\n"
        "5️⃣ ¿Cuándo recogen?\n"
        "6️⃣ Datos para pagar\n"
        "7️⃣ Hablar con alguien\n\n"
        "O llámanos: 📞 +34 942 32 30 50"
    ), False


# ══════════════════════════════════════════════════════════════
#  WEBHOOK — Evolution API
# ══════════════════════════════════════════════════════════════
@app.route("/webhook", methods=["POST"])
def webhook():
    raw = request.get_data(as_text=True)
    print(f"📥 {raw[:300]}")
    try:
        data = json.loads(raw)

        # Evolution API envía eventos distintos
        evento = data.get("event","")

        # Solo procesar mensajes entrantes
        if evento not in ["messages.upsert","message.new",""]:
            return jsonify({"status":"ok"}), 200

        # Extraer mensaje
        msg_data = data.get("data",{})
        if not msg_data:
            msg_data = data

        # Ignorar mensajes propios
        from_me = msg_data.get("key",{}).get("fromMe", False) or msg_data.get("fromMe", False)
        if from_me:
            return jsonify({"status":"ok"}), 200

        # Obtener número y mensaje
        telefono = (msg_data.get("key",{}).get("remoteJid","") or
                   msg_data.get("remoteJid","") or
                   msg_data.get("from",""))

        # Ignorar grupos y status
        if "@g.us" in telefono or "status" in telefono:
            return jsonify({"status":"ok"}), 200

        # Tipo de mensaje
        tipo = msg_data.get("messageType","") or msg_data.get("type","")
        mensaje_content = msg_data.get("message",{})

        # Audio
        if tipo in ["audioMessage","pttMessage","audio","ptt"]:
            avisar("🎤 AUDIO recibido", telefono, "[nota de voz]")
            resp = (
                "🎤 *Recibimos tu nota de voz.*\n\n"
                "Todavía no podemos escuchar\n"
                "audios aquí 😅\n\n"
                "Por favor escríbenos lo que\n"
                "necesitas y te ayudamos 😊\n\n"
                "O llámanos: 📞 +34 942 32 30 50"
            )
            enviar(telefono, resp)
            guardar(telefono, "[audio]", resp, True)
            return jsonify({"status":"ok"}), 200

        # Imagen
        if tipo in ["imageMessage","image","videoMessage","video"]:
            avisar("📸 FOTO recibida", telefono, "[imagen]")
            enviar(telefono,
                "📸 *Recibimos tu foto.*\n\n"
                "El equipo la revisa\n"
                "y te responde pronto 😊"
            )
            return jsonify({"status":"ok"}), 200

        # Documento
        if tipo in ["documentMessage","document"]:
            avisar("📄 DOCUMENTO recibido", telefono, "[documento]")
            enviar(telefono,
                "📄 *Recibimos tu documento.*\n\n"
                "El equipo lo revisa\n"
                "y te responde pronto 😊"
            )
            return jsonify({"status":"ok"}), 200

        # Extraer texto
        mensaje = (
            mensaje_content.get("conversation","") or
            mensaje_content.get("extendedTextMessage",{}).get("text","") or
            msg_data.get("body","") or
            msg_data.get("text","") or ""
        )

        if not mensaje:
            return jsonify({"status":"ok"}), 200

        print(f"📩 {telefono}: {mensaje[:60]}")
        resp, agente = responder(telefono, mensaje)
        enviar(telefono, resp)
        guardar(telefono, mensaje, resp, agente)
        return jsonify({"status":"ok"}), 200

    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"status":"error","detail":str(e)}), 500


@app.route("/", methods=["GET"])
def health():
    return jsonify({"status":"Crisbell Bot v8 — Evolution API"}), 200

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    print(f"🚀 Crisbell Bot v8 Evolution API")
    app.run(host="0.0.0.0", port=port, debug=False)
