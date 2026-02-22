import os
import json
import logging
import random
import shutil
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, TypedDict

import pytz
import requests
import telebot
from telebot import types
from dotenv import load_dotenv
# NUEVA DEPENDENCIA
import ollama 

# --- 1. CARGA DE CONFIGURACIÓN ---
load_dotenv()

# --- 2. LOGGING PROFESIONAL ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot_errors.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# --- 3. CONFIGURACIÓN Y CONSTANTES ---
class Config:
    TOKEN: str = os.getenv("TELEGRAM_TOKEN", "")
    OWM_KEY: str = os.getenv("OPENWEATHER_KEY", "")
    ADMIN_ID: int = int(os.getenv("ADMIN_ID", "0"))
    TIMEZONE: str = os.getenv("TIMEZONE", "Europe/Madrid")
    # NUEVO: Modelo de IA a usar (ej: llama3, mistral)
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3") 
    
    @classmethod
    def validate(cls):
        if not cls.TOKEN or cls.ADMIN_ID == 0:
            raise EnvironmentError("Faltan variables de entorno críticas")

# --- 4. MODELOS DE DATOS ---
class UserData(TypedDict):
    nombre: str
    puntos: int
    racha: int
    logros: List[str]
    ultima_pole: str

class SystemData(TypedDict):
    fecha_actual: str
    mes_actual: str
    ganadores_hoy: List[str]
    # NUEVO: Para guardar cuándo fue el último resumen
    ultimo_resumen: Optional[str] 

class PoleData(TypedDict):
    sistema: SystemData
    usuarios: Dict[str, UserData]
    variables: Dict[str, str]

# --- 5. GESTOR DE DATOS ---
class DataManager:
    def __init__(self, filename: str):
        self.filename = filename
    
    def _default_structure(self) -> PoleData:
        return {
            "sistema": {
                "fecha_actual": "", 
                "mes_actual": "", 
                "ganadores_hoy": [], 
                "ultimo_resumen": None # Formato ISO string
            },
            "usuarios": {},
            "variables": {}
        }

    def load(self) -> PoleData:
        if not os.path.exists(self.filename):
            return self._default_structure()
        try:
            with open(self.filename, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Ensure keys exist for backward compatibility
                if "ultimo_resumen" not in data["sistema"]:
                    data["sistema"]["ultimo_resumen"] = None
                return data
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Error cargando datos: {e}")
            return self._default_structure()

    def save(self, data: PoleData) -> None:
        temp_file = f"{self.filename}.tmp"
        try:
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            shutil.move(temp_file, self.filename)
        except IOError as e:
            logger.critical(f"Error guardando datos: {e}")

# --- NUEVO: GESTOR DE HISTORIAL (MEMORIA A CORTO PLAZO) ---
class HistoryManager:
    """
    Guarda mensajes en un JSON separado y limpia los antiguos automáticamente.
    """
    def __init__(self, filename: str, retention_hours: int = 3):
        self.filename = filename
        self.retention_seconds = retention_hours * 3600
    
    def _load_history(self) -> Dict[str, List[dict]]:
        if not os.path.exists(self.filename): return {}
        try:
            with open(self.filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        except: return {}

    def _save_history(self, data: Dict[str, List[dict]]):
        temp_file = f"{self.filename}.tmp"
        try:
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            shutil.move(temp_file, self.filename)
        except IOError as e:
            logger.error(f"Error guardando historial: {e}")

    def add_message(self, chat_id: int, user_name: str, text: str, timestamp: datetime):
        data = self._load_history()
        cid_str = str(chat_id)
        
        if cid_str not in data: data[cid_str] = []
        
        # Añadir mensaje
        data[cid_str].append({
            "user": user_name,
            "text": text,
            "time": timestamp.isoformat()
        })
        
        # LIMPIEZA AUTOMÁTICA: Borramos mensajes viejos antes de guardar
        cutoff = timestamp - timedelta(seconds=self.retention_seconds)
        data[cid_str] = [
            msg for msg in data[cid_str] 
            if datetime.fromisoformat(msg['time']) > cutoff
        ]
        
        self._save_history(data)

    def get_recent_text(self, chat_id: int, hours: int = 2) -> str:
        """Devuelve el texto formateado de las últimas X horas para la IA."""
        data = self._load_history()
        cid_str = str(chat_id)
        if cid_str not in data: return "No ha habido conversación reciente."

        cutoff = datetime.now(pytz.timezone(Config.TIMEZONE)) - timedelta(hours=hours)
        
        lines = []
        for msg in data[cid_str]:
            msg_time = datetime.fromisoformat(msg['time'])
            if msg_time > cutoff:
                lines.append(f"{msg['user']}: {msg['text']}")
        
        return "\n".join(lines) if lines else "No hay mensajes suficientes."

# --- NUEVO: SERVICIO OLLAMA (IA LOCAL) ---
class OllamaService:
    def __init__(self, model: str):
        self.model = model
        # Verificar conexión al inicio
        try:
            ollama.list()
            logger.info(f"Ollama conectado. Modelo activo: {self.model}")
        except Exception as e:
            logger.warning(f"No se pudo conectar a Ollama: {e}. La función de resumen fallará.")

    def generate_summary(self, conversation_text: str) -> str:
        prompt = (
            "Eres un bot de Telegram simpático y sarcástico. Tu misión es resumir la siguiente conversación "
            "de un grupo de amigos en un párrafo breve, gracioso y con un toque de guasa. "
            "Usa emojis. Si la conversación está vacía o es aburrida, inventa una excusa graciosa.\n\n"
            f"CONVERSACIÓN:\n{conversation_text}\n\nRESUMEN GRACIOSO:"
        )
        
        try:
            response = ollama.chat(model=self.model, messages=[
                {'role': 'user', 'content': prompt}
            ])
            return response['message']['content']
        except Exception as e:
            logger.error(f"Error generando resumen Ollama: {e}")
            return "🤖 Mi cerebro de IA ha fallado. A lo mejor los servidores están patata."

# --- SERVICIOS EXISTENTES (POLE, CLIMA, GIF) ---
# (Se omiten por brevedad, pero se incluyen en el archivo final completo al final)
# ... (Clases PoleService, WeatherService, GifManager igual que antes) ...

class PoleService:
    TITLES = [(300, "Ilitri Supremo 👑"), (100, "Piloto de F1 🏎️"), (50, "Shurmano de Bronce 🥉"), (10, "Conductor Novel 🚗"), (0, "Dominguero 🛵")]
    def __init__(self, data_manager: DataManager, timezone: str): self.dm = data_manager; self.tz = pytz.timezone(timezone)
    def _get_now(self) -> datetime: return datetime.now(self.tz)
    def _get_title(self, points: int) -> str:
        for threshold, title in self.TITLES:
            if points >= threshold: return title
        return "Dominguero 🛵"
    def _check_resets(self, data: PoleData, now: datetime) -> PoleData:
        fecha_hoy = now.strftime("%Y-%m-%d"); mes_actual = now.strftime("%Y-%m")
        if data["sistema"]["mes_actual"] != mes_actual:
            for uid in data["usuarios"]: data["usuarios"][uid]["puntos"] = 0; data["usuarios"][uid]["racha"] = 0
            data["sistema"]["mes_actual"] = mes_actual
        if data["sistema"]["fecha_actual"] != fecha_hoy:
            data["sistema"]["fecha_actual"] = fecha_hoy; data["sistema"]["ganadores_hoy"] = []
        return data
    def attempt_pole(self, user_id: int, name: str) -> Dict[str, Any]:
        now = self._get_now(); data = self.dm.load(); data = self._check_resets(data, now)
        uid_str = str(user_id); ganadores = data["sistema"]["ganadores_hoy"]; response = {"success": False, "message": ""}
        if len(ganadores) >= 3: response["message"] = f"🐢 Llegas tarde, {name}."; return response
        if uid_str in ganadores: response["message"] = f"⛔ {name}, ya tienes medalla hoy."; return response
        puesto = len(ganadores) + 1; puntos_base = {1: 3, 2: 2, 3: 1}.get(puesto, 0)
        if uid_str not in data["usuarios"]: data["usuarios"][uid_str] = {"nombre": name, "puntos": 0, "racha": 0, "logros": [], "ultima_pole": ""}
        user = data["usuarios"][uid_str]; user["nombre"] = name
        bonus_precision = 2 if puesto == 1 and now.second < 2 else 0; logro_msg = ""
        if bonus_precision and "Francotirador" not in user["logros"]: user["logros"].append("Francotirador"); logro_msg = "\n🎯 ¡POLE MILIMÉTRICA! (+2 pts)"
        ayer = (now - timedelta(days=1)).strftime("%Y-%m-%d"); bonus_racha = 0; racha_msg = ""
        if user["ultima_pole"] == ayer:
            user["racha"] += 1
            if user["racha"] >= 3: bonus_racha = 1; racha_msg = f"\n🔥 ¡Racha de {user['racha']} días! (+1 pt)"
        else: user["racha"] = 1
        user["ultima_pole"] = now.strftime("%Y-%m-%d"); total = puntos_base + bonus_precision + bonus_racha; user["puntos"] += total
        data["sistema"]["ganadores_hoy"].append(uid_str); self.dm.save(data)
        medalla = ["🥇", "🥈", "🥉"][puesto-1]; response["success"] = True; response["message"] = f"{medalla} **{name}** suma +{total} pts.{logro_msg}{racha_msg}"
        return response
    def get_ranking(self) -> str:
        data = self.dm.load(); sorted_users = sorted(data["usuarios"].values(), key=lambda x: x['puntos'], reverse=True)
        if not sorted_users: return "Sin datos aún."
        msg = "🏆 **CLASIFICACIÓN** 🏆\n\n"
        for i, u in enumerate(sorted_users[:10], 1): msg += f"{i}. **{u['nombre']}**: {u['puntos']} pts | {self._get_title(u['puntos'])}\n"
        return msg

class WeatherService:
    BASE_URL = "https://api.openweathermap.org/data/2.5/weather"
    def __init__(self, api_key: str): self.api_key = api_key; self.session = requests.Session(); retry_adapter = requests.adapters.HTTPAdapter(max_retries=3); self.session.mount("https://", retry_adapter)
    def get_weather(self, zip_code: str) -> str:
        if not self.api_key: return "❌ Clima no configurado."
        params = {"zip": f"{zip_code},es", "appid": self.api_key, "units": "metric", "lang": "es"}
        try:
            response = self.session.get(self.BASE_URL, params=params, timeout=5); response.raise_for_status(); r = response.json()
            return f"🌤️ {r['name']}: {r['main']['temp']}ºC, {r['weather'][0]['description']}"
        except: return "❌ Error obteniendo el clima."

class GifManager:
    def __init__(self, filename: str): self.filename = filename
    def load(self) -> Dict[str, List[str]]:
        if not os.path.exists(self.filename): return {}
        try: return json.load(open(self.filename, 'r', encoding='utf-8'))
        except: return {}
    def add_gif(self, category: str, file_id: str) -> bool:
        data = self.load()
        if category not in data: data[category] = []
        if file_id in data[category]: return False
        data[category].append(file_id)
        try: json.dump(data, open(self.filename, 'w', encoding='utf-8'), indent=4, ensure_ascii=False); return True
        except: return False

# --- CONTROLADOR PRINCIPAL (BOT) ---

def main():
    try: Config.validate()
    except EnvironmentError as e: logger.critical(e); return

    bot = telebot.TeleBot(Config.TOKEN)
    
    # Inicializar Servicios
    pole_dm = DataManager("datos_pole_v2.json")
    pole_service = PoleService(pole_dm, Config.TIMEZONE)
    weather_service = WeatherService(Config.OWM_KEY)
    gif_manager = GifManager("gifs_dinamicos.json")
    
    # NUEVO: Inicializar Historial y Ollama
    history_manager = HistoryManager("historial.json", retention_hours=3)
    ollama_service = OllamaService(Config.OLLAMA_MODEL)

    # --- Manejadores Admin ---
    def is_admin(message: types.Message): return message.from_user.id == Config.ADMIN_ID

    @bot.message_handler(content_types=['animation'], func=lambda m: m.chat.type == 'private' and is_admin(m))
    def handle_admin_gif(message: types.Message):
        file_id = message.animation.file_id
        msg = bot.reply_to(message, "📥 **GIF detectado.**\n¿Categoría?", parse_mode="Markdown")
        bot.register_next_step_handler(msg, process_gif_step, file_id)

    def process_gif_step(message: types.Message, file_id: str):
        if not message.text: return
        cat = message.text.strip().lower()
        if gif_manager.add_gif(cat, file_id): bot.send_message(message.chat.id, f"✅ Guardado en {cat}.")
        else: bot.send_message(message.chat.id, "⚠️ Error o duplicado.")

    # --- Manejadores Comandos ---
    @bot.message_handler(commands=['ranking'])
    def cmd_ranking(message: types.Message):
        bot.send_message(message.chat.id, pole_service.get_ranking(), parse_mode="Markdown")

    # --- Manejador Central ---
    @bot.message_handler(func=lambda m: True)
    def handle_all(message: types.Message):
        text = message.text
        if not text: return
        
        # FILTRO IMPORTANTE: Ignorar bots y canales
        if message.from_user.is_bot:
            return

        chat_id = message.chat.id
        user_name = message.from_user.first_name
        text_lower = text.lower()
        
        # NUEVO: Guardar mensaje en historial (solo si no es comando privado)
        if not text.startswith('/') and message.chat.type != 'private':
            history_manager.add_message(chat_id, user_name, text, datetime.now(pytz.timezone(Config.TIMEZONE)))

        # --- NUEVO: COMANDO RESUMEN ---
        if text_lower == "!resumen":
            # 1. Check Cooldown
            data = pole_dm.load()
            last_summary_str = data["sistema"].get("ultimo_resumen")
            
            can_summarize = True
            wait_msg = ""
            
            if last_summary_str:
                last_time = datetime.fromisoformat(last_summary_str)
                cooldown_end = last_time + timedelta(hours=2)
                
                if datetime.now(pytz.timezone(Config.TIMEZONE)) < cooldown_end:
                    can_summarize = False
                    remaining = cooldown_end - datetime.now(pytz.timezone(Config.TIMEZONE))
                    minutes = int(remaining.total_seconds() / 60)
                    wait_msg = f"⏳ ¡Paciencia! El resumen está recargando. Quedan unos {minutes} minutos."
            
            if not can_summarize:
                bot.send_message(chat_id, wait_msg)
                return

            # 2. Ejecutar Resumen
            bot.send_message(chat_id, "🧠 Procesando memoria de grupo... (esto puede tardar unos segundos)")
            
            history_text = history_manager.get_recent_text(chat_id, hours=2)
            summary = ollama_service.generate_summary(history_text)
            
            bot.send_message(chat_id, f"📝 **RESUMEN DE LA SITUACIÓN:**\n\n{summary}", parse_mode="Markdown")
            
            # 3. Guardar nuevo timestamp
            data["sistema"]["ultimo_resumen"] = datetime.now(pytz.timezone(Config.TIMEZONE)).isoformat()
            pole_dm.save(data)
            return

        # --- Lógica estándar ---
        if text_lower.startswith("!tiempo"):
            try:
                cp = text.split()[1]
                bot.send_message(chat_id, weather_service.get_weather(cp))
            except: bot.send_message(chat_id, "Uso: !tiempo <cp>")
            return

        if "hola china" in text_lower:
            hora = datetime.now(pytz.timezone('Asia/Shanghai')).strftime("%H:%M")
            bot.send_message(chat_id, f"🇨🇳 Hora en China: {hora}")
            return

        # POLE (Regex)
        if re.search(r'\bpole\b', text_lower):
            result = pole_service.attempt_pole(message.from_user.id, message.from_user.first_name)
            bot.send_message(chat_id, result["message"], parse_mode="Markdown")
            return

        # GIFS
        gifs = gif_manager.load()
        for keyword in sorted(gifs.keys(), key=len, reverse=True):
            if re.search(rf'\b{re.escape(keyword)}\b', text_lower):
                bot.send_animation(chat_id, random.choice(gifs[keyword]))
                return

    logger.info("🤖 BOT INICIADO (v3.0 con IA y Memoria)")
    bot.infinity_polling(timeout=10, long_polling_timeout=5)

if __name__ == "__main__":
    main()
