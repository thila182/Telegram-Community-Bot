# 🤖 Telegram Pole & IA Bot

![Python](https://img.shields.io/badge/python-3.10+-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)
![Telegram](https://img.shields.io/badge/Telegram-26A5E4?style=for-the-badge&logo=telegram&logoColor=white)
![Ollama](https://img.shields.io/badge/Ollama-LLM-000000?style=for-the-badge) 
![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=for-the-badge&logo=docker&logoColor=white)

---

**Telegram Pole & IA Bot** es una solución robusta diseñada para dinamizar comunidades mediante gamificación e inteligencia artificial. Integra un sistema de puntos ("La Pole"), gestión dinámica de contenido y resúmenes automáticos usando modelos LLM locales (Ollama).

---

## 🛠️ Stack Tecnológico

| Herramienta | Función |
|---|---|
| **Python 3.10+** | Lenguaje base con tipado estático. |
| **pyTelegramBotAPI** | Librería principal de interacción con Telegram. |
| **Ollama** | Motor de IA local para resúmenes (Llama3, Mistral, etc). |
| **Docker** | Despliegue en contenedores para producción. |
| **JSON** | Persistencia de datos ligera (Puntos, Historial, GIFs). |

---

## 🚀 Funcionalidades Principales

| Categoría | Descripción |
|---|---|
| **Juego: La Pole** | Detección natural (Regex). Puntos, medallas, rachas y logros ("Francotirador"). |
| **Resumen con IA** | Comando `!resumen` que usa **Ollama** para generar un resumen gracioso de las últimas horas. |
| **GIFs Dinámicos** | Subida de GIFs por el Admin (privado) e invocación natural por palabra clave en el grupo. |
| **Utilidades** | Clima (`!tiempo`), hora en China, variables dinámicas (`!set`/`!get`). |

---

## 📦 Instalación y Configuración

### Prerrequisitos

1.  **Ollama**: Debes tener Ollama instalado y un modelo descargado.
    ```bash
    # Ejemplo para descargar el modelo ligero
    ollama pull llama3.2
    ```
2.  **Docker** (opcional pero recomendado).

### Pasos

1.  **Clona el repositorio:**
    ```bash
    git clone https://github.com/tu_usuario/tu_repo.git
    cd tu_repo
    ```

2.  **Genera los archivos de entorno:**
    Ejecuta el script de configuración automática:
    ```bash
    python setup_environment.py
    ```

3.  **Configura las credenciales:**
    Edita el archivo `.env` generado con tus claves reales:
    ```env
    TELEGRAM_TOKEN=tu_token_de_botfather
    ADMIN_ID=tu_id_numerica
    ```

4.  **Despliegue con Docker:**
    ```bash
    docker-compose up -d --build
    ```

---

## 🎮 Comandos y Uso

El bot funciona mediante lenguaje natural y comandos específicos:

| Comando / Acción | Descripción |
|---|---|
| `pole` (en una frase) | Intenta hacer la pole del día. No requiere `/`. |
| `!resumen` | Genera un resumen gracioso de la conversación reciente (Cooldown: 2h). |
| `/ranking` | Muestra la clasificación mensual. |
| `!tiempo <cp>` | Muestra el clima para el código postal indicado. |
| `Admin (Privado)` | Envía un GIF al bot y este pedirá la categoría para guardarlo. |
| `[Palabra Clave]` | Si alguien escribe una categoría de GIF guardada, el bot responderá con el GIF. |

---

## 📁 Estructura del Proyecto

```text
.
├── bot.py               # Lógica principal y handlers
├── requirements.txt     # Dependencias Python
├── Dockerfile           # Imagen Docker
├── docker-compose.yml   # Orquestación
├── setup_environment.py # Script de configuración inicial
├── .env                 # Claves secretas (No subir a Git)
├── datos_pole_v2.json   # Datos de usuarios y puntos (Auto-generado)
├── gifs_dinamicos.json  # IDs de GIFs guardados (Auto-generado)
└── historial.json       # Memoria a corto plazo para IA (Auto-generado)
```

---

## 🤝 Contribuciones

Las contribuciones son bienvenidas. Por favor, asegúrate de actualizar los tests según corresponda.

1. Haz un **Fork**.
2. Crea tu rama (`git checkout -b feature/NuevaMejora`).
3. Commit tus cambios (`git commit -m 'Añade nueva funcionalidad'`).
4. Push a la rama (`git push origin feature/NuevaMejora`).
5. Abre un **Pull Request**.

---

## 📄 Licencia

Este proyecto está bajo la Licencia MIT.

Hecho con ❤️ y Python.