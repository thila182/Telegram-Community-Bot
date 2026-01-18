import telebot
import json
import os
import requests
import pytz
import random
from datetime import datetime, timedelta

# --- CONFIGURACIÓN ---
TOKEN = "TU_TELEGRAM_TOKEN"
CLAVE_OWM = "TU_OPENWEATHER_KEY"
ADMIN_ID = 00000000  # <--- ID ACTUALIZADO

ARCHIVOS = {
    "pole": "datos_pole_v2.json",
    "gifs": "gifs_dinamicos.json"
}

bot = telebot.TeleBot(TOKEN)

# --- GESTIÓN DE DATOS (POLE) ---
def cargar_datos_pole():
    estructura = {
        "sistema": {"fecha_actual": "", "mes_actual": "", "ganadores_hoy": []},
        "usuarios": {},
        "variables": {}
    }
    if not os.path.exists(ARCHIVOS["pole"]): return estructura
    try:
        with open(ARCHIVOS["pole"], 'r', encoding='utf-8') as f:
            return json.load(f)
    except: return estructura

def guardar_datos_pole(datos):
    with open(ARCHIVOS["pole"], 'w', encoding='utf-8') as f:
        json.dump(datos, f, indent=4, ensure_ascii=False)

# --- GESTIÓN DE DATOS (GIFS) ---
def cargar_gifs():
    if not os.path.exists(ARCHIVOS["gifs"]): return {}
    try:
        with open(ARCHIVOS["gifs"], 'r', encoding='utf-8') as f:
            return json.load(f)
    except: return {}

def guardar_gifs(datos):
    with open(ARCHIVOS["gifs"], 'w', encoding='utf-8') as f:
        json.dump(datos, f, indent=4, ensure_ascii=False)

# =========================================================
#  1. LÓGICA DE ADMIN (SUBIDA DE GIFS - SOLO PRIVADO)
# =========================================================

@bot.message_handler(content_types=['animation'], func=lambda m: m.chat.type == 'private')
def detectar_gif_admin(message):
    # Verificamos que seas tú (el Admin)
    if message.from_user.id != ADMIN_ID:
        print(f"Intento de acceso denegado de: {message.from_user.id}")
        return 

    file_id = message.animation.file_id
    
    # Enviamos mensaje preguntando categoría
    msg = bot.reply_to(message, "📥 **GIF detectado.**\n¿En qué categoría lo guardo?\n(Escribe solo el nombre, ej: zarigueya)")
    
    # Pasamos al siguiente paso (esperar tu respuesta de texto)
    bot.register_next_step_handler(msg, guardar_categoria_gif, file_id)

def guardar_categoria_gif(message, file_id):
    if not message.text:
        bot.send_message(message.chat.id, "❌ Cancelado. Debías enviar texto.")
        return

    # Limpiamos el texto (quitamos espacios, barras, mayúsculas)
    categoria = message.text.strip().lower().replace('/', '')
    
    # Cargar archivo de gifs
    gifs_db = cargar_gifs()
    
    # Si la categoría no existe, se crea
    if categoria not in gifs_db:
        gifs_db[categoria] = []
        
    # Evitar duplicados
    if file_id in gifs_db[categoria]:
        bot.send_message(message.chat.id, f"⚠️ Este GIF ya existe en la categoría **{categoria}**.")
    else:
        gifs_db[categoria].append(file_id)
        guardar_gifs(gifs_db)
        bot.send_message(message.chat.id, f"✅ Guardado en **{categoria}**.\nYa puedes usar el comando: `/{categoria}`", parse_mode="Markdown")

# =========================================================
#  2. COMANDOS DEL JUEGO DE LA POLE
# =========================================================

def obtener_titulo(puntos):
    if puntos < 10: return "Dominguero 🛵"
    if puntos < 50: return "Conductor Novel 🚗"
    if puntos < 100: return "Shurmano de Bronce 🥉"
    if puntos < 300: return "Piloto de F1 🏎️"
    return "Ilitri Supremo 👑"

@bot.message_handler(commands=['pole'])
def comando_pole(message):
    user_id = str(message.from_user.id)
    name = message.from_user.first_name
    chat_id = message.chat.id
    
    tz_spain = pytz.timezone('Europe/Madrid')
    ahora = datetime.now(tz_spain)
    fecha_hoy = ahora.strftime("%Y-%m-%d")
    mes_actual = ahora.strftime("%Y-%m")
    
    datos = cargar_datos_pole()
    
    # Resets
    if datos["sistema"].get("mes_actual") != mes_actual:
        datos["sistema"]["mes_actual"] = mes_actual
        for uid in datos["usuarios"]:
            datos["usuarios"][uid]["puntos"] = 0
            datos["usuarios"][uid]["racha"] = 0
        bot.send_message(chat_id, "📅 ¡NUEVA TEMPORADA! Puntos reseteados.")

    if datos["sistema"]["fecha_actual"] != fecha_hoy:
        datos["sistema"]["fecha_actual"] = fecha_hoy
        datos["sistema"]["ganadores_hoy"] = []
        guardar_datos_pole(datos)

    ganadores = datos["sistema"]["ganadores_hoy"]

    if len(ganadores) >= 3:
        bot.send_message(chat_id, f"🐢 Llegas tarde, {name}.")
        return
    if user_id in ganadores:
        bot.send_message(chat_id, f"⛔ {name}, ya tienes medalla hoy.")
        return

    puesto = len(ganadores) + 1
    puntos_base = {1: 3, 2: 2, 3: 1}.get(puesto, 0)
    
    if user_id not in datos["usuarios"]:
        datos["usuarios"][user_id] = {"nombre": name, "puntos": 0, "racha": 0, "logros": [], "ultima_pole": ""}
    
    usuario = datos["usuarios"][user_id]
    usuario["nombre"] = name 
    
    # Bonus
    bonus_precision = 2 if puesto == 1 and ahora.second < 2 else 0
    msg_precision = "\n🎯 ¡POLE MILIMÉTRICA! (+2 pts)" if bonus_precision else ""
    if bonus_precision and "Francotirador" not in usuario["logros"]: usuario["logros"].append("Francotirador")

    ayer = (ahora - timedelta(days=1)).strftime("%Y-%m-%d")
    bonus_racha = 0
    msg_racha = ""
    if usuario["ultima_pole"] == ayer:
        usuario["racha"] += 1
        if usuario["racha"] >= 3:
            bonus_racha = 1
            msg_racha = f"\n🔥 ¡Racha de {usuario['racha']} días! (+1 pt)"
    else:
        usuario["racha"] = 1
    
    usuario["ultima_pole"] = fecha_hoy
    total = puntos_base + bonus_precision + bonus_racha
    usuario["puntos"] += total
    
    datos["sistema"]["ganadores_hoy"].append(user_id)
    guardar_datos_pole(datos)

    medalla = ["🥇", "🥈", "🥉"][puesto-1]
    bot.send_message(chat_id, f"{medalla} **{name}** suma +{total} pts.{msg_precision}{msg_racha}", parse_mode="Markdown")

@bot.message_handler(commands=['ranking'])
def comando_ranking(message):
    datos = cargar_datos_pole()
    lista = sorted(datos["usuarios"].values(), key=lambda x: x['puntos'], reverse=True)
    if not lista:
        bot.send_message(message.chat.id, "Sin datos.")
        return
    msg = "🏆 **CLASIFICACIÓN** 🏆\n\n"
    for i, u in enumerate(lista[:10], 1):
        msg += f"{i}. **{u['nombre']}**: {u['puntos']} pts | {obtener_titulo(u['puntos'])}\n"
    bot.send_message(message.chat.id, msg, parse_mode="Markdown")

@bot.message_handler(commands=['logros'])
def comando_logros(message):
    datos = cargar_datos_pole()
    user_id = str(message.from_user.id)
    if user_id in datos["usuarios"] and datos["usuarios"][user_id]["logros"]:
        bot.send_message(message.chat.id, f"🏅 Logros: {', '.join(datos['usuarios'][user_id]['logros'])}")
    else:
        bot.send_message(message.chat.id, "Sin logros aún.")

# =========================================================
#  3. MANEJADOR CENTRAL (GIFS DINÁMICOS Y TEXTO)
# =========================================================

@bot.message_handler(func=lambda message: True)
def gestionar_todo(message):
    if not message.text: return
    text = message.text.strip()
    chat_id = message.chat.id
    
    # --- A) DETECTOR DE COMANDOS DE GIFS (/zarigueya, /loquesea) ---
    if text.startswith('/'):
        # Si pones /zarigueya, extrae 'zarigueya'
        comando = text[1:].lower().split()[0]
        gifs_db = cargar_gifs() 
        
        # Si esa categoría existe en el JSON de GIFs...
        if comando in gifs_db:
            lista = gifs_db[comando]
            if lista:
                bot.send_animation(chat_id, random.choice(lista))
            else:
                bot.reply_to(message, "Categoría vacía.")
            return # Detenemos aquí para que no busque comandos como !tiempo

    # --- B) RESTO DE UTILIDADES (Usan datos_pole_v2.json) ---
    datos = cargar_datos_pole()

    # !tiempo
    if text.lower().startswith("!tiempo"):
        try:
            cp = text.split()[1]
            url = f"https://api.openweathermap.org/data/2.5/weather?zip={cp},es&appid={CLAVE_OWM}&units=metric&lang=es"
            r = requests.get(url).json()
            if r.get("cod") != 200: 
                bot.send_message(chat_id, "Error: CP no encontrado o fallo API.")
                return
            bot.send_message(chat_id, f"🌤️ {r['name']}: {r['main']['temp']}ºC, {r['weather'][0]['description']}")
        except: bot.send_message(chat_id, "Error procesando tiempo.")
        return

    # Hola China
    if "hola china" in text.lower():
        hora = datetime.now(pytz.timezone('Asia/Shanghai')).strftime("%H:%M")
        bot.send_message(chat_id, f"🇨🇳 Hora en China: {hora}")
        return

    # !set (Variables de texto)
    if text.lower().startswith("!set "):
        try:
            _, clave, valor = text.split(" ", 2)
            datos["variables"][clave.lower()] = valor
            guardar_datos_pole(datos)
            bot.send_message(chat_id, f"✅ Guardado: {clave.lower()}")
        except: bot.send_message(chat_id, "Uso: !set <nombre> <texto>")
        return

    # !get
    if text.lower().startswith("!get "):
        clave = text.split()[1].lower() if len(text.split()) > 1 else ""
        if clave in datos["variables"]:
            bot.send_message(chat_id, datos["variables"][clave])
        else:
            bot.send_message(chat_id, "No existe esa variable.")

# --- ARRANQUE ---
print("🤖 BOT INICIADO. Esperando GIFs en privado del Admin...")
bot.infinity_polling()