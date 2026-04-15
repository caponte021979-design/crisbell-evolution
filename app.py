"""
CRISBELL CARGO EXPRESS — WhatsApp Bot v9
Optimizado para personas mayores — lenguaje simple y directo
"""

import os, json, re, unicodedata, requests
from flask import Flask, request, jsonify
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime

app = Flask(__name__)

INSTANCE_ID      = "instance170032"
ULTRAMSG_TOKEN   = "8yqqjnlqjx0ic5n6"
NUMERO_CRISTHIAN = "34642887582"

ZONA = ["asturias","gijon","oviedo","aviles","mieres","langreo","llanes",
        "cangas","navia","pola de siero","siero","pola","lugones",
        "pais vasco","bilbao","san sebastian","vitoria","donostia",
        "barakaldo","getxo","irun","eibar","santurtzi","basauri","durango",
        "cantabria","santander","torrelavega","castro","laredo","reinosa",
        "noja","solares","camargo","astillero","colindres",
        "valladolid","zamora","salamanca","medina","benavente"]

FUERA_ZONA = ["madrid","barcelona","valencia","sevilla","malaga","murcia",
              "alicante","zaragoza","granada","cordoba","palma","vigo",
              "coruña","cadiz","burgos","logroño","pamplona","toledo",
              "albacete","benidorm","tarragona","castellon","badajoz",
              "caceres","huelva","jaen","almeria","pontevedra","lugo",
              "orense","la bañeza","bañeza","santoña","leon"]

DATOS_BANCARIOS = (
    "💳 *Para pagar:*\n\n"
    "🏦 *CaixaBank:*\n"
    "ES26 2100 4312 0122 0012 8871\n\n"
    "🏦 *Santander:*\n"
    "ES58 0049 5865 5323 1610 1317\n\n"
    "👤 A nombre de:\n"
    "CYG EXPORTACIONES E IMPORTACIONES S.L.\n\n"
    "🇩🇴 *Banreservas (RD):*\n"
    "Cuenta: 250-059955-3\n"
    "Titular: Cristhian Aponte\n\n"
    "📌 Pon tu nombre cuando hagas la transferencia\n"
    "y mándanos el comprobante por aquí 😊"
)

# ── FIREBASE ───────────────────────────────────────────────────
cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

def enviar(tel, texto):
    numero = tel.replace("@c.us","").replace("+","").replace(" ","")
    url = (f"https://api.ultramsg.com/{INSTANCE_ID}/messages/chat"
           f"?token={ULTRAMSG_TOKEN}&to={requests.utils.quote(tel)}&body={requests.utils.quote(texto)}&priority=10")
    try: requests.get(url, timeout=10)
    except Exception as e: print(f"❌ {e}")

def avisar(motivo, tel, msg):
    t = tel.replace("@c.us","").replace("+","").replace(" ","")
    m = motivo.lower()
    if any(p in m for p in ["recogida","direccion","zona","ciudad"]): tipo="📦 RECOGIDA"
    elif any(p in m for p in ["precio","tarifa","cotiza","colombia","venezuela","ecuador","bolivia","rd"]): tipo="💰 PRECIO"
    elif any(p in m for p in ["salida","fecha","cuando"]): tipo="📅 FECHA"
    elif any(p in m for p in ["pago","cuenta","transfer","consign"]): tipo="💳 PAGO"
    elif "audio" in m: tipo="🎤 AUDIO"
    elif "agente" in m: tipo="👤 AGENTE"
    elif "tele" in m or "television" in m or "tv" in m: tipo="📺 TELEVISIÓN"
    else: tipo="❓ CONSULTA"
    link = f"https://api.whatsapp.com/send?phone={t}"
    enviar(NUMERO_CRISTHIAN,
        f"🔔 *{tipo}*\n━━━━━━━━━━━━\n📱 +{t}\n💬 {msg[:200]}\n━━━━━━━━━━━━\n👆 Responder:\n{link}")

def guardar(tel, msg_c, resp, agente=False):
    try:
        db.collection("whatsapp_chats").add({
            "telefono":tel,"mensaje_cliente":msg_c,"respuesta_bot":resp,
            "timestamp":datetime.utcnow(),
            "atendido_por":"pendiente" if agente else "bot",
            "requiere_agente":agente})
    except: pass

# ══════════════════════════════════════════════════════════════
#  MODO HUMANO — bot se calla cuando Cristhian responde
# ══════════════════════════════════════════════════════════════
def esta_en_modo_humano(tel):
    """True si Cristhian respondió en las últimas 2 horas"""
    t = tel.replace("@c.us","").replace("+","").replace(" ","")
    try:
        doc = db.collection("bot_pausa").document(t).get()
        if doc.exists:
            data = doc.to_dict()
            hasta = data.get("hasta")
            if hasta and hasta.tzinfo is None:
                from datetime import timezone
                hasta = hasta.replace(tzinfo=timezone.utc)
            from datetime import timezone
            if hasta and datetime.now(timezone.utc) < hasta:
                return True
            # Caducó — limpiar
            db.collection("bot_pausa").document(t).delete()
    except: pass
    return False

def activar_modo_humano(tel, horas=2):
    """Pausa el bot para este chat durante X horas"""
    t = tel.replace("@c.us","").replace("+","").replace(" ","")
    from datetime import timedelta, timezone
    hasta = datetime.now(timezone.utc) + timedelta(hours=horas)
    try:
        db.collection("bot_pausa").document(t).set({
            "hasta": hasta,
            "activado": datetime.now(timezone.utc)
        })
    except: pass

def zonas_recogida():
    """Lee el calendario de recogidas desde Firestore"""
    try:
        doc = db.collection("config").document("agenda_recogidas").get()
        if doc.exists: return doc.to_dict()
    except: pass
    return {}

def dia_recogida_zona(ciudad, agenda):
    """Devuelve el próximo día de recogida para una ciudad"""
    ciudad = ciudad.lower().strip()
    # Buscar en zonas
    for zona, datos in agenda.items():
        ciudades = [c.lower().strip() for c in datos.get("ciudades", [])]
        if any(ciudad in c or c in ciudad for c in ciudades):
            dia = datos.get("proximo_dia", "")
            nombre_zona = datos.get("nombre", zona)
            return dia, nombre_zona
    return None, None

def buscar_exp(tel):
    t = tel.replace("@c.us","").replace("+","").replace(" ","")
    try:
        docs = db.collection("expediciones").where("telefonoCliente","==",t)\
                  .order_by("fecha",direction=firestore.Query.DESCENDING).limit(1).stream()
        for d in docs: return d.to_dict()
    except: pass
    return None

def buscar_cli(tel):
    t = tel.replace("@c.us","").replace("+","").replace(" ","")
    try:
        docs = db.collection("clientes").where("telefono","==",t).limit(1).stream()
        for d in docs: return d.to_dict()
    except: pass
    return None

def tarifas():
    try:
        # CRM guarda en 'configuracion/tarifas'
        d = db.collection("configuracion").document("tarifas").get()
        if d.exists: return d.to_dict()
    except: pass
    return {}

def fechas():
    try:
        d = db.collection("config").document("salidas").get()
        if d.exists: return d.to_dict()
    except: pass
    return {}

def limpiar(t):
    t = t.lower().strip()
    t = ''.join(c for c in unicodedata.normalize('NFKD',t) if not unicodedata.combining(c))
    return re.sub(r'\s+',' ',t)

def tiene(msg, palabras):
    return any(p in msg for p in palabras)

def pais(msg):
    if re.search(r'colom|medell|bogot|cali\b|barranq|cartagen', msg): return "colombia"
    if re.search(r'venezu|venezo|caracas|maracay|maracaib|barquisi|merida', msg): return "venezuela"
    if re.search(r'\brd\b|dominicana|dominicna|santo domingo|rep.?dom|villa mella|santiago rd|san pedro|san crrist|la romana', msg): return "rd"
    if re.search(r'ecuador|ecuad|quito|guayaquil', msg): return "ecuador"
    if re.search(r'bolivia|bolivi|la paz|santa cruz|cochabamba', msg): return "bolivia"
    return None

def en_zona(msg):
    return next((c for c in ZONA if limpiar(c) in msg), None)

def fuera_zona(msg):
    return next((c for c in FUERA_ZONA if limpiar(c) in msg), None)

def resp_rd():
    return (
        "🇩🇴 *Envíos a República Dominicana:*\n\n"
        "📦 *Cajas y precios:*\n"
        "Mini (33×37×39 cm) → *40€*\n"
        "Pequeña (40×45×65 cm) → *80€*\n"
        "Mediana (50×50×73 cm) → *120€*\n"
        "Grande (50×50×100 cm) → *150€*\n\n"
        "🔥 *Ofertas:*\n"
        "Mini + Grande → *170€*\n"
        "Mini + Mediana → *150€*\n\n"
        "⏱️ Llega en unos *30 días*\n\n"
        "🚫 No se puede enviar: pilas\n"
        "Máximo 6 cremas, colonias o medicinas\n\n"
        "¿Te recogemos la caja? Dinos tu dirección 😊"
    )

def resp_colombia(T):
    a = T.get("co_aereo_ventaKg", T.get("aereo_colombia_kg","11.00"))
    m = T.get("co_mar_ventaDm3", T.get("maritimo_colombia_dm3","1.28"))
    return (
        "🇨🇴 *Envíos a Colombia:*\n\n"
        f"✈️ *Por avión:* {a}€ el kilo\n"
        "   De 3 a 10 kg — todo incluido\n"
        "   Llega en *8 a 10 días*\n\n"
        f"🚢 *Por barco:* {m}€/dm³\n"
        "   Caja hasta 40 kilos\n"
        "   Llega en *45 a 60 días*\n\n"
        "🚫 No se puede enviar: teléfonos móviles\n\n"
        "¿Cuántos kilos tienes para enviar? 😊"
    )

def resp_venezuela(T):
    ve_oe = T.get("ve_oe_ventaCuft","50")
    ve_m1 = T.get("ve_mar_caja1_venta","205")
    ve_m2 = T.get("ve_mar_caja2_venta","95")
    return (
        "🇻🇪 *Envíos a Venezuela:*\n\n"
        f"✈️ *Por avión:* 16€ el kilo\n"
        "   Mínimo 3 kilos\n"
        "   Llega en *8 a 12 días*\n"
        "   Se entrega en oficina MRW\n\n"
        "🚢 *Por barco:*\n"
        f"   Caja mini (33×37×39 cm) → *{ve_m2}€*\n"
        f"   Caja grande (40×45×65 cm) → *{ve_m1}€*\n"
        "   Se entrega en oficina Aerocav\n\n"
        "¿Cuánto tienes para enviar? 😊"
    )

def resp_ecuador(T):
    e = T.get("ecu_ventaKg","0")
    if str(e) == "0" or not e:
        return (
            "🇪🇨 *Envíos a Ecuador:*\n\n"
            "✈️ *Por avión* — precio según el peso\n\n"
            "Dinos cuántos kilos tienes\n"
            "y un agente te da el precio 😊"
        )
    return (
        f"🇪🇨 *Envíos a Ecuador:*\n\n"
        f"✈️ *Por avión:* {e}€ el kilo\n\n"
        "Dinos cuántos kilos tienes 😊"
    )

def resp_tele(pais_dest, T):
    """Respuesta específica para televisores y electrodomésticos grandes"""
    avisar_texto = f"Cliente pregunta por televisor para {pais_dest}"
    if "rd" in pais_dest or "dominicana" in pais_dest:
        return (
            "📺 *Televisores a República Dominicana:*\n\n"
            "Los televisores van por *precio por pulgada*.\n\n"
            "Dinos el tamaño de tu tele (ej: 55 pulgadas)\n"
            "y te calculamos el precio al momento 😊\n\n"
            "También necesitamos saber:\n"
            "📍 ¿En qué ciudad estás en España?"
        )
    return (
        "📺 *Para televisores y electrodomésticos:*\n\n"
        "El precio depende del tamaño y el peso.\n\n"
        "Dinos:\n"
        "📺 Tamaño de la tele (pulgadas)\n"
        "📍 Tu ciudad en España\n"
        "🌍 País de destino\n\n"
        "Un agente te da el precio exacto 😊"
    )


# ══════════════════════════════════════════════════════════════
#  MOTOR DE RESPUESTAS — simple, directo, para personas mayores
# ══════════════════════════════════════════════════════════════
def responder(tel, mensaje_orig):
    msg = limpiar(mensaje_orig)
    cli = buscar_cli(tel)
    nom = cli.get("nombre","").split()[0] if cli else ""
    sal = f"Hola {nom}! 😊\n" if nom else "Hola! 😊\n"
    T   = tarifas()
    p   = pais(msg)

    # ── BIENVENIDA ─────────────────────────────────────────────
    if tiene(msg,["hola","buenas","buenos","buen dia","buen tarde","bendicion",
                  "saludos","buenos dias","buenas tardes","buenas noch","dios"]):
        return (
            f"{sal}Soy el asistente de *Crisbell Cargo Express* 🚢\n\n"
            "Cuéntame qué necesitas 👇\n\n"
            "📦 ¿Quieres enviar algo?\n"
            "💰 ¿Preguntar un precio?\n"
            "📍 ¿Saber cuándo recogemos?\n"
            "💳 ¿Datos para pagar?\n\n"
            "O escribe directamente tu pregunta 😊"
        ), False

    # ── TELEVISORES / ELECTRODOMÉSTICOS ───────────────────────
    if tiene(msg,["tele","television","televisor","tv","pulgada","electrodomestico",
                  "nevera","lavadora","microondas","aire acondicionado"]):
        pais_dest = p or "rd"
        avisar("📺 Consulta televisor/electrodoméstico", tel, mensaje_orig)
        return resp_tele(pais_dest, T), True

    # ── YA PAGUÉ ───────────────────────────────────────────────
    if tiene(msg,["ya pague","ya pague","consigne","consigna","ya ingrese",
                  "ya ingrese","hice el pago","hice la transf","ya deposite",
                  "ya transferi","mande el dinero","ya mande","te mande","mande la"]):
        avisar("💳 Pago confirmado", tel, mensaje_orig)
        return (
            "✅ *¡Gracias, recibido!*\n\n"
            "Ya avisamos al equipo.\n"
            "En cuanto lo verifiquemos\n"
            "te confirmamos 😊\n\n"
            "Si tienes el comprobante\n"
            "puedes mandárnoslo aquí 📄"
        ), False

    # ── DATOS BANCARIOS ────────────────────────────────────────
    if tiene(msg,["cuenta","iban","numero de cuenta","como pago","donde pago",
                  "datos para pagar","banco","transferencia","depositar","deposito",
                  "cuanto tengo que pagar","cuanto debo","que debo","lo que debo"]):
        return DATOS_BANCARIOS, False

    # ── CUÁNTO TENGO QUE PAGAR (cuando ya recogieron) ─────────
    if tiene(msg,["cuanto es","cuanto tengo","cuanto hay que","cuanto cuesta mi",
                  "que tengo que pagar","lo que tengo que pagar","mi factura","mi precio"]):
        exp = buscar_exp(tel)
        if exp and exp.get("precio"):
            return (
                f"📋 *Tu envío:*\n\n"
                f"🔖 Guía: {exp.get('guia',exp.get('referencia',''))}\n"
                f"💰 Total a pagar: *{exp.get('precio','')}€*\n\n"
                "Puedes pagar por transferencia.\n"
                "¿Quieres los datos del banco? 😊"
            ), False
        avisar("Pregunta cuánto tiene que pagar", tel, mensaje_orig)
        return (
            "Para decirte el importe exacto\n"
            "necesito tu número de guía\n"
            "(empieza por CBCE-)\n\n"
            "Si no lo tienes, un agente\n"
            "te lo dice en un momento 😊"
        ), True

    # ── VER MI ENVÍO ───────────────────────────────────────────
    if tiene(msg,["mi caja","mi envio","mi paquete","llego","no ha llegado",
                  "cuando llega","donde esta","seguimiento","tracking","cbce","estado"]):
        exp = buscar_exp(tel)
        if exp:
            return (
                f"📦 *Tu último envío:*\n\n"
                f"🔖 Número: {exp.get('guia',exp.get('referencia',''))}\n"
                f"📍 Va para: {exp.get('destino','')}\n"
                f"🔄 Estado: *{exp.get('estado','En camino')}*\n"
                f"📅 Salió: {exp.get('fechaSalida','Pendiente')}\n\n"
                "También puedes verlo en:\n"
                "🌐 crisbellcargoexpress.com/rastrear"
            ), False
        avisar("Pregunta por su envío", tel, mensaje_orig)
        return (
            f"{sal}No encontré envíos con tu número.\n\n"
            "Dime tu número de envío\n"
            "(algo como CBCE-1234)\n\n"
            "O llámanos y te buscamos 😊\n"
            "📞 +34 942 32 30 50"
        ), False

    # ── CUÁNDO RECOGEN ─────────────────────────────────────────
    if tiene(msg,["cuando recogen","cuando pasan","cuando van","cuando vienen",
                  "a que hora","que hora pasan","recogida","recojer","recoger",
                  "van a pasar","me recogen","cuanto tiempo","la recojida","recojida"]):
        zona  = en_zona(msg)
        fuera = fuera_zona(msg)
        if fuera and not zona:
            avisar(f"Recogida fuera de zona: {fuera}", tel, mensaje_orig)
            return (
                f"📍 En *{fuera.title()}* no tenemos\n"
                "recogida habitual.\n\n"
                "Nuestras zonas son:\n"
                "• Asturias · País Vasco · Cantabria\n"
                "• Valladolid · Zamora · Salamanca\n\n"
                "Ya avisamos a un agente\n"
                "para buscar solución 😊"
            ), True
        # Buscar en agenda de recogidas
        agenda = zonas_recogida()
        zona_encontrada = en_zona(msg)
        if zona_encontrada and agenda:
            dia, nombre_zona = dia_recogida_zona(zona_encontrada, agenda)
            if dia:
                avisar("Pregunta recogida — zona en agenda", tel, mensaje_orig)
                return (
                    f"🚚 *Recogemos en {zona_encontrada.title()}*\n\n"
                    f"📅 Próxima recogida: *{dia}*\n\n"
                    "Para confirmarlo dinos:\n"
                    "📍 Tu dirección completa\n"
                    "📦 Qué vas a enviar 😊"
                ), False
        avisar("Pregunta cuándo recogen", tel, mensaje_orig)
        return (
            "🚚 *Recogemos a domicilio.*\n\n"
            "Un agente te confirma el día\n"
            "en cuanto pueda 😊\n\n"
            "Para agilizar, dinos:\n"
            "📍 Tu dirección completa\n"
            "📦 Qué vas a enviar\n"
            "🌍 País de destino"
        ), True

    # ── FECHAS DE SALIDA ───────────────────────────────────────
    if tiene(msg,["cuando salen","cuando sale","fecha de salida","proxima salida",
                  "proximo envio","proximo barco","cuando envian","para cuando",
                  "que fecha sale","esta salida","siguiente","llegar antes","antes del",
                  "cuanto tarda","tiempo de llegada","para el dia","para la madre",
                  "para el dia de la madre","para las madres"]):
        fs = fechas()
        if p == "rd" or tiene(msg,["dominicana","rd","santo domingo","villa mella"]):
            avisar("Pregunta fecha salida RD", tel, mensaje_orig)
            proxima = fs.get("rd_proxima_salida","principios de mayo")
            llegada = fs.get("rd_llegada_estimada","principios de junio")
            return (
                "🇩🇴 *República Dominicana:*\n\n"
                f"📦 Próxima salida: *{proxima}* 🚢\n"
                "Ya estamos recogiendo cajas.\n\n"
                f"⏱️ Llega a destino: *{llegada}* ✅\n\n"
                "¿Quieres que recojamos tu caja?\n"
                "Dinos tu dirección 😊"
            ), False
        avisar("Pregunta fecha salida", tel, mensaje_orig)
        return (
            "📅 Un agente te confirma\n"
            "la fecha exacta de salida 😊\n\n"
            "¿A qué país quieres enviar?"
        ), True

    # ── PRECIOS ────────────────────────────────────────────────
    if tiene(msg,["precio","cuanto","quanto","cuanto cuesta","cuanto vale",
                  "tarifa","costo","cotiza","presupuesto","cuanto cobra","cuanto es",
                  "que precio","cuanto seria","el monto","el precio"]):
        if p == "rd":        return resp_rd(), False
        if p == "venezuela": return resp_venezuela(T), False
        if p == "colombia":  return resp_colombia(T), False
        if p == "ecuador":   return resp_ecuador(T), False
        if p == "bolivia":
            avisar("Consulta Bolivia", tel, mensaje_orig)
            return (
                "🇧🇴 *Bolivia — por avión*\n\n"
                "Un agente te da el precio\n"
                "según el peso que tengas 😊\n\n"
                "📞 +34 942 32 30 50"
            ), True
        # Sin país — preguntar de forma simple
        return (
            "¿A qué país quieres enviar?\n\n"
            "🇩🇴 República Dominicana\n"
            "🇨🇴 Colombia\n"
            "🇻🇪 Venezuela\n"
            "🇪🇨 Ecuador\n"
            "🇧🇴 Bolivia\n\n"
            "Dime el país y te doy el precio 😊"
        ), False

    # ── SOLO MENCIONA PAÍS ─────────────────────────────────────
    if p:
        if p == "rd":        return resp_rd(), False
        if p == "venezuela": return resp_venezuela(T), False
        if p == "colombia":  return resp_colombia(T), False
        if p == "ecuador":   return resp_ecuador(T), False
        if p == "bolivia":
            avisar("Consulta Bolivia", tel, mensaje_orig)
            return ("🇧🇴 Para Bolivia un agente te da\nel precio 😊\n📞 +34 942 32 30 50"), True

    # ── QUÉ PUEDO ENVIAR ───────────────────────────────────────
    if tiene(msg,["puedo enviar","se puede","puedo mandar","puedo meter",
                  "gel","crema","medicamento","medicina","pila","bateria",
                  "telefono","celular","movil","liquido","comida","alimento","prohibido"]):
        return (
            "📋 *¿Qué se puede enviar?*\n\n"
            "✅ *Sí:*\n"
            "Ropa, zapatos, juguetes\n"
            "Comida seca y enlatada\n"
            "Electrodomésticos\n"
            "Cremas y colonias (máx. 6)\n"
            "Medicinas (máx. 5 ó 6)\n\n"
            "🚫 *No:*\n"
            "Pilas ni baterías\n"
            "Teléfonos móviles (Colombia)\n"
            "Líquidos sueltos\n"
            "Cosas para vender sin declarar\n\n"
            "¿Tienes duda de algo? Dímelo 😊"
        ), False

    # ── CAJA VACÍA ─────────────────────────────────────────────
    if tiene(msg,["caja vacia","caja vacia","quiero una caja","me trae una caja",
                  "necesito una caja","caja para llenar","pedir caja","solicitar caja"]):
        return (
            "📦 *Pedir caja vacía:*\n\n"
            "1️⃣ Haz una transferencia de *15€*\n"
            "2️⃣ Mándanos el comprobante aquí\n"
            "3️⃣ Dinos tu dirección\n\n"
            "¿Quieres los datos del banco? 😊"
        ), False

    # ── HORARIOS ───────────────────────────────────────────────
    if tiene(msg,["horario","hora","abierto","cerrado","cuando abren","atienden"]):
        return (
            "🕐 *Horarios:*\n\n"
            "Lunes a Viernes:\n"
            "   Mañanas: 10:00 a 15:00\n"
            "   Tardes: 17:00 a 21:00\n\n"
            "Sábados: 10:00 a 15:00\n"
            "Domingos: Cerrado\n\n"
            "📞 +34 942 32 30 50"
        ), False

    # ── UBICACIÓN ──────────────────────────────────────────────
    if tiene(msg,["donde estan","donde estais","oficina","donde queda","como llego"]):
        return (
            "📍 *Nuestra oficina:*\n\n"
            "C. Jerónimo Sáinz de la Maza 1\n"
            "Local 6 — Santander\n\n"
            "📞 +34 942 32 30 50\n"
            "📱 +34 653 70 02 34\n\n"
            "Lunes-Viernes: 10:00-15:00\n"
            "y 17:00-21:00\n"
            "Sábados: 10:00-15:00"
        ), False

    # ── AGENTE ─────────────────────────────────────────────────
    if tiene(msg,["agente","hablar","persona","cristian","ayuda","llamar","7"]):
        avisar("Cliente quiere hablar con agente", tel, mensaje_orig)
        return (
            "👤 *Ya avisamos...*\n\n"
            "En breve te llamamos\n"
            "o te escribimos 😊\n\n"
            "También puedes llamarnos:\n"
            "📞 +34 942 32 30 50\n\n"
            "Horario: L-V 10:00-15:00\n"
            "y 17:00-21:00"
        ), True

    # ── DIRECCIÓN DEL CLIENTE ─────────────────────────────────
    if (tiene(msg,["calle","avenida","carrera","paseo","avda"]) and
        tiene(msg,["piso","portal","puerta","bajo","numero","bloque","apto","letra"])):
        avisar("Cliente envió su dirección", tel, mensaje_orig)
        return (
            "📍 *¡Apuntado!*\n\n"
            "Ya avisamos al equipo.\n"
            "Te decimos el día de recogida\n"
            "muy pronto 😊"
        ), True

    # ── GRACIAS / DESPEDIDA ───────────────────────────────────
    if tiene(msg,["gracias","gracia","grcias","ok","vale","perfecto",
                  "de acuerdo","listo","entendido","igualmente","igual","ygual",
                  "adios","hasta luego","bendicion","bendiciones"]):
        return (
            "😊 ¡Con mucho gusto!\n\n"
            "Cualquier cosa que necesites\n"
            "aquí estamos 💚"
        ), False

    # ── CIUDAD FUERA ZONA ──────────────────────────────────────
    fuera = fuera_zona(msg)
    if fuera:
        avisar(f"Ciudad fuera de zona: {fuera}", tel, mensaje_orig)
        return (
            f"📍 En *{fuera.title()}* no tenemos\n"
            "recogida habitual.\n\n"
            "Nuestras zonas:\n"
            "Asturias · País Vasco · Cantabria\n"
            "Valladolid · Zamora · Salamanca\n\n"
            "Ya avisamos a un agente\n"
            "para buscar solución 😊"
        ), True

    # ── NÚMEROS SOLOS (teléfono, DNI, etc) ────────────────────
    if re.match(r'^[\d\s\+\-]+$', mensaje_orig.strip()):
        avisar("Cliente envió número/dato suelto", tel, mensaje_orig)
        return (
            "Recibido 😊\n\n"
            "Un agente lo revisará\n"
            "y te responde en breve."
        ), True

    # ── GENÉRICA — avisar siempre ─────────────────────────────
    avisar("No entendido", tel, mensaje_orig)
    return (
        f"{sal}No entendí bien 😅\n\n"
        "Cuéntame qué necesitas:\n\n"
        "📦 Enviar algo\n"
        "💰 Saber un precio\n"
        "📍 Cuándo recogen\n"
        "💳 Datos para pagar\n\n"
        "O llámanos directamente:\n"
        "📞 +34 942 32 30 50"
    ), False


# ══════════════════════════════════════════════════════════════
#  WEBHOOK
# ══════════════════════════════════════════════════════════════
@app.route("/webhook", methods=["POST"])
def webhook():
    raw = request.get_data(as_text=True)
    print(f"📥 {raw[:300]}")
    try:
        try: data = json.loads(raw)
        except:
            from urllib.parse import parse_qs
            data = {k: v[0] for k, v in parse_qs(raw).items()}

        d = data.get("data", data)
        if isinstance(d, str):
            try: d = json.loads(d)
            except: d = data

        tipo    = d.get("type","")
        tel     = d.get("from","")
        msg     = d.get("body","")
        from_me = d.get("fromMe", False)

        if not tel: return jsonify({"status":"ok"}), 200
        if tel == "status@broadcast" or "@g.us" in tel: return jsonify({"status":"ok"}), 200

        # IGNORAR mensajes propios — pero activar modo humano
        if from_me:
            if tel and "@g.us" not in tel and tel != "status@broadcast":
                activar_modo_humano(tel, horas=2)
                print(f"🤫 Modo humano activado para {tel} — 2 horas")
            return jsonify({"status":"ok"}), 200

        # AUDIO
        if tipo in ["ptt","audio"]:
            avisar("🎤 AUDIO", tel, "[nota de voz]")
            resp = (
                "🎤 Recibimos tu nota de voz.\n\n"
                "No podemos escuchar audios 😅\n\n"
                "Por favor escríbenos lo que\n"
                "necesitas y te ayudamos 😊\n\n"
                "O llámanos:\n"
                "📞 +34 942 32 30 50"
            )
            enviar(tel, resp)
            guardar(tel, "[audio]", resp, True)
            return jsonify({"status":"ok"}), 200

        # FOTO / VIDEO
        if tipo in ["image","video"]:
            avisar("📸 FOTO/VIDEO", tel, "[imagen]")
            enviar(tel, "📸 Recibimos tu foto.\nEl equipo la revisa y te responde 😊")
            return jsonify({"status":"ok"}), 200

        # DOCUMENTO
        if tipo == "document":
            avisar("📄 DOCUMENTO", tel, "[documento]")
            enviar(tel, "📄 Recibimos tu documento.\nEl equipo lo revisa 😊")
            return jsonify({"status":"ok"}), 200

        if tipo == "sticker" or not msg:
            return jsonify({"status":"ok"}), 200

        # MODO HUMANO: si Cristhian respondió recientemente, bot se calla
        if esta_en_modo_humano(tel):
            print(f"🤫 Modo humano activo para {tel} — bot callado")
            guardar(tel, msg, "[BOT CALLADO — modo humano activo]", False)
            return jsonify({"status":"ok"}), 200

        print(f"📩 {tel}: {msg[:60]}")
        resp, agente = responder(tel, msg)
        enviar(tel, resp)
        guardar(tel, msg, resp, agente)
        return jsonify({"status":"ok"}), 200

    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"status":"error","detail":str(e)}), 500


@app.route("/", methods=["GET"])
def health():
    return jsonify({"status":"Crisbell Bot v9 — Optimizado"}), 200

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
