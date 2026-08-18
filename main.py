from fastapi import FastAPI, HTTPException, Form, Response, Cookie, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
import os
import json
import hashlib
from pydantic import BaseModel
import pymysql
from openai import OpenAI

# Cargar automáticamente variables de .env
def _load_env_file(filepath=".env"):
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip("'\"")
                if k and k not in os.environ:
                    os.environ[k] = v

_load_env_file()

app = FastAPI(title="API de Análisis de Sentimientos con MySQL")


@app.get("/health")
def health_check():
    """Endpoint de salud para Docker healthcheck y monitoreo."""
    return {"status": "ok", "service": "construccion-fastapi"}


# Ruta del archivo JSON de usuarios locales
USERS_JSON_PATH = "usuarios.json"

def init_users_file():
    # Inicializa el archivo usuarios.json con el admin por defecto si no existe
    if not os.path.exists(USERS_JSON_PATH):
        admin_pass = "12345"
        admin_hash = hashlib.sha256(admin_pass.encode()).hexdigest()
        default_users = {
            "admin": {
                "email": "admin@lasallistas.org.mx",
                "password_hash": admin_hash
            }
        }
        with open(USERS_JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(default_users, f, indent=4, ensure_ascii=False)

def load_users() -> dict:
    init_users_file()
    try:
        with open(USERS_JSON_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_users(users: dict):
    with open(USERS_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=4, ensure_ascii=False)

# Inicializar el archivo de usuarios al arrancar el modulo
init_users_file()

# Configuración de conexión exclusiva al contenedor MariaDB
def get_db_connection():
    import os

    # 1. Variables de entorno configuradas en .env o Docker
    host = os.getenv("DB_HOST", "127.0.0.1")
    port = int(os.getenv("DB_PORT", 3308))
    user = os.getenv("DB_USER", "root")
    password = os.getenv("DB_PASSWORD", "lasalle")
    database = os.getenv("DB_NAME", "db_sentimientos")

    try:
        return pymysql.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            connect_timeout=5,
            cursorclass=pymysql.cursors.DictCursor
        )
    except Exception as e:
        print(f"[ERROR] Error al conectar al contenedor MariaDB ({host}:{port}, usuario: {user}): {e}")

    # 2. Fallback de contenedor MariaDB si se ejecuta dentro de red Docker (host: mariadb, puerto: 3306)
    try:
        return pymysql.connect(
            host="mariadb",
            port=3306,
            user=user,
            password=password,
            database=database,
            connect_timeout=3,
            cursorclass=pymysql.cursors.DictCursor
        )
    except Exception:
        pass

    raise HTTPException(
        status_code=503,
        detail=f"No se pudo establecer conexión con el contenedor MariaDB en {host}:{port}. Verifica que el contenedor 'construccion_mariadb' esté corriendo."
    )


# Inicializar cliente compatible con la API de OpenAI para LM Studio
# En Docker usa LLM_BASE_URL=http://host.docker.internal:1234/v1
# En local usa http://127.0.0.1:1234/v1 como fallback
client = OpenAI(
    base_url=os.getenv("LLM_BASE_URL", "http://127.0.0.1:1234/v1"),
    api_key="lm-studio",
    timeout=3.0,
    max_retries=1
)

def get_model_name() -> str:
    # 1. Si se define la variable de entorno, tiene prioridad
    env_model = os.getenv("LLM_MODEL")
    if env_model:
        return env_model
    # 2. De lo contrario, intentamos detectar dinámicamente el modelo cargado en LM Studio
    try:
        models = client.models.list(timeout=2.0)
        if models.data:
            return models.data[0].id
    except Exception:
        pass
    # 3. Fallback final por defecto
    return "sentiment-model"

def clasificar_sentimiento_lmstudio(texto: str) -> dict:
    """
    Clasifica el sentimiento de un texto usando el LLM local en LM Studio.
    Retorna un diccionario con 'label' y 'score' (confianza).
    """
    system_prompt = (
        "You are an expert sentiment analysis AI. Analyze the sentiment of the user's text.\n"
        "You MUST respond with EXACTLY ONE of these labels: Positive, Negative, Neutral, Irrelevant.\n"
        "Do not write any introductory text, explanation, punctuation, or any other words. Just write the label."
    )
    
    try:
        model_name = get_model_name()
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Text: {texto}"}
            ],
            temperature=0.0, # Temperatura 0 para mayor determinismo y consistencia
            max_tokens=5,
            timeout=2.0
        )
        
        raw_reply = response.choices[0].message.content.strip()
        # Limpiar y normalizar la respuesta
        clean_pred = raw_reply.strip('"').strip("'").strip(".").strip().lower()
        
        if "positive" in clean_pred:
            label = "Positive"
        elif "negative" in clean_pred:
            label = "Negative"
        elif "neutral" in clean_pred:
            label = "Neutral"
        elif "irrelevant" in clean_pred:
            label = "Irrelevant"
        else:
            label = "Neutral"
            
        return {"label": label, "score": 1.0}
    except Exception as e:
        print(f"Error en inferencia de LM Studio: {e}")
        # Retornar una clasificación por defecto en caso de error
        return {"label": "Neutral", "score": 0.0}


class PredictRequest(BaseModel):
    id_tweet: int

class LivePredictRequest(BaseModel):
    text: str

@app.get("/login", response_class=HTMLResponse)
def vista_login(error: str = None, success: str = None):
    alert_msg = ''
    if error:
        alert_msg = f"""
        <div class="w-full p-4 mb-4 text-sm text-error bg-error-container/30 border border-error/20 rounded-xl text-center font-bold text-error">
            {error}
        </div>
        """
    elif success:
        alert_msg = f"""
        <div class="w-full p-4 mb-4 text-sm text-secondary bg-secondary-container/30 border border-secondary/20 rounded-xl text-center font-bold text-on-secondary-container">
            {success}
        </div>
        """
        
    return f"""
    <!DOCTYPE html>
    <html class="light" lang="es">
    <head>
        <meta charset="utf-8"/>
        <meta content="width=device-width, initial-scale=1.0" name="viewport"/>
        <title>Serene Pulse - Iniciar Sesión</title>
        <script>
            if (localStorage.getItem('theme') === 'dark') {{
                document.documentElement.classList.add('dark');
                document.documentElement.classList.remove('light');
            }} else {{
                document.documentElement.classList.add('light');
                document.documentElement.classList.remove('dark');
            }}
        </script>
        <script src="https://cdn.tailwindcss.com?plugins=forms,container-queries"></script>
        <link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&amp;display=swap" rel="stylesheet"/>
        <link href="https://fonts.googleapis.com" rel="preconnect"/>
        <link crossorigin="" href="https://fonts.gstatic.com" rel="preconnect"/>
        <link href="https://fonts.googleapis.com/css2?family=Quicksand:wght@400;500;600;700&amp;display=swap" rel="stylesheet"/>
        <script id="tailwind-config">
            tailwind.config = {{
              darkMode: "class",
              theme: {{
                extend: {{
                  "colors": {{
                          "surface-dim": "#d9dadb",
                          "surface-bright": "#f8f9fa",
                          "outline-variant": "#c9c5cf",
                          "on-secondary-fixed": "#01201c",
                          "inverse-primary": "#c8c1f0",
                          "surface-container-highest": "#e1e3e4",
                          "on-primary-fixed-variant": "#474269",
                          "inverse-on-surface": "#f0f1f2",
                          "on-primary-fixed": "#1b163b",
                          "on-error": "#ffffff",
                          "tertiary-container": "#eccecb",
                          "surface-container": "#edeeef",
                          "on-surface-variant": "var(--color-on-surface-variant)",
                          "secondary-fixed": "#c8e9e2",
                          "on-error-container": "#93000a",
                          "secondary-container": "#c8e9e2",
                          "on-primary-container": "#5c5780",
                          "on-tertiary-container": "#6d5654",
                          "on-tertiary-fixed-variant": "#574240",
                          "on-surface": "var(--color-on-surface)",
                          "inverse-surface": "#2e3132",
                          "on-tertiary": "#ffffff",
                          "on-secondary": "#ffffff",
                          "on-secondary-fixed-variant": "#2f4c47",
                          "surface-container-low": "var(--color-surface-container-low)",
                          "secondary-fixed-dim": "#adcdc7",
                          "primary": "#5e5983",
                          "on-background": "var(--color-on-background)",
                          "on-secondary-container": "#4c6a65",
                          "on-tertiary-fixed": "#281716",
                          "primary-container": "#d6cfff",
                          "background": "var(--color-background)",
                          "surface-tint": "#5e5983",
                          "tertiary-fixed-dim": "#ddc0bd",
                          "secondary": "#46645f",
                          "surface": "var(--color-surface)",
                          "outline": "var(--color-outline)",
                          "tertiary": "#705957",
                          "surface-variant": "#e1e3e4",
                          "error": "#ba1a1a",
                          "surface-container-lowest": "var(--color-surface-container-lowest)",
                          "primary-fixed-dim": "#c8c1f0",
                          "error-container": "#ffdad6",
                          "on-primary": "#ffffff",
                          "tertiary-fixed": "#fadbd8",
                          "primary-fixed": "#e5deff",
                          "surface-container-high": "#e7e8e9"
                  }},
                  "borderRadius": {{
                          "DEFAULT": "1rem",
                          "lg": "2rem",
                          "xl": "3rem",
                          "full": "9999px"
                  }},
                  "spacing": {{
                          "unit": "8px",
                          "stack-lg": "48px",
                          "stack-sm": "12px",
                          "container-padding": "32px",
                          "stack-md": "24px",
                          "gutter": "24px"
                  }},
                  "fontFamily": {{
                          "display-lg": [
                                  "Quicksand"
                          ],
                          "body-lg": [
                                  "Quicksand"
                          ],
                          "label-sm": [
                                  "Quicksand"
                          ],
                          "display-lg-mobile": [
                                  "Quicksand"
                          ],
                          "headline-md": [
                                  "Quicksand"
                          ],
                          "body-md": [
                                  "Quicksand"
                          ]
                  }},
                  "fontSize": {{
                          "display-lg": [
                                  "48px",
                                  {{
                                          "lineHeight": "1.2",
                                          "letterSpacing": "-0.02em",
                                          "fontWeight": "700"
                                  }}
                          ],
                          "body-lg": [
                                  "18px",
                                  {{
                                          "lineHeight": "1.6",
                                          "fontWeight": "500"
                                  }}
                          ],
                          "label-sm": [
                                  "12px",
                                  {{
                                          "lineHeight": "1",
                                          "letterSpacing": "0.05em",
                                          "fontWeight": "600"
                                  }}
                          ],
                          "display-lg-mobile": [
                                  "32px",
                                  {{
                                          "lineHeight": "1.2",
                                          "fontWeight": "700"
                                  }}
                          ],
                          "headline-md": [
                                  "24px",
                                  {{
                                          "lineHeight": "1.4",
                                          "fontWeight": "600"
                                  }}
                          ],
                          "body-md": [
                                  "16px",
                                  {{
                                          "lineHeight": "1.6",
                                          "fontWeight": "400"
                                  }}
                          ]
                  }}
                }},
              }},
            }}
        </script>
        <style>
            :root {{
                --color-background: #f8f9fa;
                --color-on-background: #191c1d;
                --color-surface-container-lowest: #ffffff;
                --color-surface-container-low: #f3f4f5;
                --color-surface: #f8f9fa;
                --color-on-surface: #191c1d;
                --color-on-surface-variant: #48464e;
                --color-outline: #78767f;
            }}
            .dark {{
                --color-background: #121016;
                --color-on-background: #e0dbec;
                --color-surface-container-lowest: #151221;
                --color-surface-container-low: #1c192b;
                --color-surface: #121016;
                --color-on-surface: #ffffff;
                --color-on-surface-variant: #b0a9c0;
                --color-outline: #8d8a9a;
            }}

            body {{
                background-color: var(--color-background);
                color: var(--color-on-background);
            }}

            .glass-panel {{
                background: rgba(255, 255, 255, 0.6);
                backdrop-filter: blur(20px);
                -webkit-backdrop-filter: blur(20px);
                border: 1px solid rgba(255, 255, 255, 0.4);
            }}
            
            .input-hollow {{
                background-color: #F1F3F5;
                border: 1px solid transparent;
                transition: all 0.3s ease;
            }}
            
            .input-hollow:focus {{
                outline: none;
                border-color: #c8c1f0;
                box-shadow: 0 0 15px rgba(200, 193, 240, 0.3);
                background-color: #ffffff;
            }}

            .btn-primary-gradient {{
                background: linear-gradient(135deg, #5e5983 0%, #c8c1f0 100%);
                transition: opacity 0.3s ease, transform 0.2s ease;
            }}
            
            .btn-primary-gradient:hover {{
                opacity: 0.9;
                transform: scale(1.02);
            }}
        </style>
    </head>
    <body class="bg-background dark:bg-[#121016] min-h-screen flex items-center justify-center p-container-padding relative overflow-hidden font-body-md text-on-surface dark:text-[#e0dbec] transition-colors duration-300">
        <!-- Floating Theme Toggle -->
        <div class="absolute top-6 right-6 z-50">
            <button onclick="toggleDarkMode()" class="p-3 rounded-full bg-surface-container/80 dark:bg-[#1f1a30]/80 text-primary dark:text-[#b4aaf2] border border-white/20 dark:border-white/5 shadow-md backdrop-blur-md flex items-center justify-center hover:scale-110 transition-transform">
                <span class="material-symbols-outlined" id="theme-icon">dark_mode</span>
            </button>
        </div>
        <div class="absolute top-[-10%] left-[-10%] w-[50%] h-[50%] rounded-full bg-secondary-fixed opacity-30 blur-[100px] -z-10 dark:opacity-15"></div>
        <div class="absolute bottom-[-10%] right-[-10%] w-[60%] h-[60%] rounded-full bg-primary-container opacity-40 blur-[120px] -z-10 dark:opacity-20"></div>
        <div class="w-full max-w-[1000px] mx-auto grid grid-cols-1 md:grid-cols-2 gap-stack-lg items-center z-10">
            <!-- Left Side: Context & Branding -->
            <div class="flex flex-col justify-center space-y-stack-md text-center md:text-left order-2 md:order-1 px-4 md:px-0">
                <div>
                    <h1 class="font-display-lg-mobile text-display-lg-mobile md:font-display-lg md:text-display-lg text-primary dark:text-[#b4aaf2] mb-unit">Serene Pulse</h1>
                    <p class="font-headline-md text-headline-md text-on-surface-variant dark:text-[#b0a9c0] opacity-80">El Observador Silencioso.</p>
                </div>
                <p class="font-body-lg text-body-lg text-on-surface-variant dark:text-[#b0a9c0] max-w-[400px] mx-auto md:mx-0 leading-relaxed">
                    Serene Pulse utiliza modelos de lenguaje locales avanzados para visualizar tu paisaje emocional, ayudándote a encontrar claridad y calma a través del análisis de datos.
                </p>
            </div>
            <!-- Right Side: Login Form Canvas -->
            <div class="glass-panel rounded-xl p-8 md:p-12 shadow-[0_20px_40px_rgba(94,89,131,0.05)] flex flex-col items-center justify-center order-1 md:order-2 w-full max-w-[450px] mx-auto">
                <img alt="Serene Pulse Logo" class="w-24 h-24 rounded-full mb-stack-md shadow-[0_10px_30px_rgba(200,193,240,0.3)] object-cover" src="https://lh3.googleusercontent.com/aida/AP1WRLvTpvVzbm6t3e3pSe3PNivw3uCzrxL4N9ILyVl0lTorK6yAWKcIPNqqKSrkC5bPl1ny1kAHGAE5XRYr8r4GVJvTZ5wAEP3t6qFqsD74O63ceAUogWS_Q3BtJVC1KRcwHVINZ8xZUHnM8riyNQ32-MFcstx7QZ3DMzcKMRi7zjNIUqINrrg_mADgoi9QgT5A-D7BCiROhMQrUMhrounANLT9vIW56u1vQMRhPUog5WKDHgBO8cIGy2KeFA"/>
                <h2 class="font-headline-md text-headline-md text-on-surface dark:text-white mb-stack-lg">Iniciar Sesión</h2>
                
                {alert_msg}
                
                <form action="/login" method="POST" class="w-full flex flex-col space-y-stack-sm">
                    <div class="relative w-full">
                        <span class="material-symbols-outlined absolute left-4 top-1/2 -translate-y-1/2 text-outline dark:text-[#8d8a9a]">account_circle</span>
                        <input class="input-hollow w-full rounded-full py-4 pl-12 pr-6 font-body-md text-body-md text-on-surface dark:text-white placeholder:text-outline-variant" placeholder="Usuario" required name="username" id="username" type="text" autocomplete="username"/>
                    </div>
                    <div class="relative w-full">
                        <span class="material-symbols-outlined absolute left-4 top-1/2 -translate-y-1/2 text-outline dark:text-[#8d8a9a]">lock</span>
                        <input class="input-hollow w-full rounded-full py-4 pl-12 pr-6 font-body-md text-body-md text-on-surface dark:text-white placeholder:text-outline-variant" placeholder="Contraseña" required name="password" id="password" type="password" autocomplete="current-password"/>
                    </div>
                    <button class="btn-primary-gradient w-full rounded-full py-4 text-on-primary dark:text-black font-body-lg text-body-lg shadow-[0_10px_20px_rgba(94,89,131,0.15)] flex items-center justify-center gap-2 mt-4" type="submit">
                        Ingresar al Panel
                        <span class="material-symbols-outlined">arrow_forward</span>
                    </button>
                    <div class="text-center mt-4">
                        <a href="/register" class="font-label-sm text-label-sm text-primary dark:text-[#b4aaf2] hover:underline">¿No tienes cuenta? Regístrate aquí</a>
                    </div>
                </form>
            </div>
        </div>
        <script>
            function applyTheme() {{
                const isDark = localStorage.getItem('theme') === 'dark';
                const html = document.documentElement;
                const icon = document.getElementById('theme-icon');
                
                if (isDark) {{
                    html.classList.remove('light');
                    html.classList.add('dark');
                    if (icon) icon.innerText = 'light_mode';
                }} else {{
                    html.classList.remove('dark');
                    html.classList.add('light');
                    if (icon) icon.innerText = 'dark_mode';
                }}
            }}

            function toggleDarkMode() {{
                const isDark = localStorage.getItem('theme') === 'dark';
                localStorage.setItem('theme', isDark ? 'light' : 'dark');
                applyTheme();
            }}

            applyTheme();
        </script>
    </body>
    </html>
    """

@app.get("/register", response_class=HTMLResponse)
def vista_register(error: str = None):
    error_msg = f"""
    <div class="w-full p-4 mb-4 text-sm text-error bg-error-container/30 border border-error/20 rounded-xl text-center font-bold text-error">
        {error}
    </div>
    """ if error else ''
    
    return f"""
    <!DOCTYPE html>
    <html class="light" lang="es">
    <head>
        <meta charset="utf-8"/>
        <meta content="width=device-width, initial-scale=1.0" name="viewport"/>
        <title>Serene Pulse - Registrarse</title>
        <script>
            if (localStorage.getItem('theme') === 'dark') {{
                document.documentElement.classList.add('dark');
                document.documentElement.classList.remove('light');
            }} else {{
                document.documentElement.classList.add('light');
                document.documentElement.classList.remove('dark');
            }}
        </script>
        <script src="https://cdn.tailwindcss.com?plugins=forms,container-queries"></script>
        <link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&amp;display=swap" rel="stylesheet"/>
        <link href="https://fonts.googleapis.com" rel="preconnect"/>
        <link crossorigin="" href="https://fonts.gstatic.com" rel="preconnect"/>
        <link href="https://fonts.googleapis.com/css2?family=Quicksand:wght@400;500;600;700&amp;display=swap" rel="stylesheet"/>
        <script id="tailwind-config">
            tailwind.config = {{
              darkMode: "class",
              theme: {{
                extend: {{
                  "colors": {{
                          "surface-dim": "#d9dadb",
                          "surface-bright": "#f8f9fa",
                          "outline-variant": "#c9c5cf",
                          "on-secondary-fixed": "#01201c",
                          "inverse-primary": "#c8c1f0",
                          "surface-container-highest": "#e1e3e4",
                          "on-primary-fixed-variant": "#474269",
                          "inverse-on-surface": "#f0f1f2",
                          "on-primary-fixed": "#1b163b",
                          "on-error": "#ffffff",
                          "tertiary-container": "#eccecb",
                          "surface-container": "#edeeef",
                          "on-surface-variant": "var(--color-on-surface-variant)",
                          "secondary-fixed": "#c8e9e2",
                          "on-error-container": "#93000a",
                          "secondary-container": "#c8e9e2",
                          "on-primary-container": "#5c5780",
                          "on-tertiary-container": "#6d5654",
                          "on-tertiary-fixed-variant": "#574240",
                          "on-surface": "var(--color-on-surface)",
                          "inverse-surface": "#2e3132",
                          "on-tertiary": "#ffffff",
                          "on-secondary": "#ffffff",
                          "on-secondary-fixed-variant": "#2f4c47",
                          "surface-container-low": "var(--color-surface-container-low)",
                          "secondary-fixed-dim": "#adcdc7",
                          "primary": "#5e5983",
                          "on-background": "var(--color-on-background)",
                          "on-secondary-container": "#4c6a65",
                          "on-tertiary-fixed": "#281716",
                          "primary-container": "#d6cfff",
                          "background": "var(--color-background)",
                          "surface-tint": "#5e5983",
                          "tertiary-fixed-dim": "#ddc0bd",
                          "secondary": "#46645f",
                          "surface": "var(--color-surface)",
                          "outline": "var(--color-outline)",
                          "tertiary": "#705957",
                          "surface-variant": "#e1e3e4",
                          "error": "#ba1a1a",
                          "surface-container-lowest": "var(--color-surface-container-lowest)",
                          "primary-fixed-dim": "#c8c1f0",
                          "error-container": "#ffdad6",
                          "on-primary": "#ffffff",
                          "tertiary-fixed": "#fadbd8",
                          "primary-fixed": "#e5deff",
                          "surface-container-high": "#e7e8e9"
                  }},
                  "borderRadius": {{
                          "DEFAULT": "1rem",
                          "lg": "2rem",
                          "xl": "3rem",
                          "full": "9999px"
                  }},
                  "spacing": {{
                          "unit": "8px",
                          "stack-lg": "48px",
                          "stack-sm": "12px",
                          "container-padding": "32px",
                          "stack-md": "24px",
                          "gutter": "24px"
                  }},
                  "fontFamily": {{
                          "display-lg": [
                                  "Quicksand"
                          ],
                          "body-lg": [
                                  "Quicksand"
                          ],
                          "label-sm": [
                                  "Quicksand"
                          ],
                          "display-lg-mobile": [
                                  "Quicksand"
                          ],
                          "headline-md": [
                                  "Quicksand"
                          ],
                          "body-md": [
                                  "Quicksand"
                          ]
                  }},
                  "fontSize": {{
                          "display-lg": [
                                  "48px",
                                  {{
                                          "lineHeight": "1.2",
                                          "letterSpacing": "-0.02em",
                                          "fontWeight": "700"
                                  }}
                          ],
                          "body-lg": [
                                  "18px",
                                  {{
                                          "lineHeight": "1.6",
                                          "fontWeight": "500"
                                  }}
                          ],
                          "label-sm": [
                                  "12px",
                                  {{
                                          "lineHeight": "1",
                                          "letterSpacing": "0.05em",
                                          "fontWeight": "600"
                                  }}
                          ],
                          "display-lg-mobile": [
                                  "32px",
                                  {{
                                          "lineHeight": "1.2",
                                          "fontWeight": "700"
                                  }}
                          ],
                          "headline-md": [
                                  "24px",
                                  {{
                                          "lineHeight": "1.4",
                                          "fontWeight": "600"
                                  }}
                          ],
                          "body-md": [
                                  "16px",
                                  {{
                                          "lineHeight": "1.6",
                                          "fontWeight": "400"
                                  }}
                          ]
                  }}
                }},
              }},
            }}
        </script>
        <style>
            :root {{
                --color-background: #f8f9fa;
                --color-on-background: #191c1d;
                --color-surface-container-lowest: #ffffff;
                --color-surface-container-low: #f3f4f5;
                --color-surface: #f8f9fa;
                --color-on-surface: #191c1d;
                --color-on-surface-variant: #48464e;
                --color-outline: #78767f;
            }}
            .dark {{
                --color-background: #121016;
                --color-on-background: #e0dbec;
                --color-surface-container-lowest: #151221;
                --color-surface-container-low: #1c192b;
                --color-surface: #121016;
                --color-on-surface: #ffffff;
                --color-on-surface-variant: #b0a9c0;
                --color-outline: #8d8a9a;
            }}

            body {{
                background-color: var(--color-background);
                color: var(--color-on-background);
            }}

            .glass-panel {{
                background: rgba(255, 255, 255, 0.6);
                backdrop-filter: blur(20px);
                -webkit-backdrop-filter: blur(20px);
                border: 1px solid rgba(255, 255, 255, 0.4);
            }}
            .dark .glass-panel {{
                background: rgba(25, 22, 38, 0.6);
                border: 1px solid rgba(255, 255, 255, 0.08);
            }}
            
            .input-hollow {{
                background-color: #F1F3F5;
                border: 1px solid transparent;
                transition: all 0.3s ease;
            }}
            .dark .input-hollow {{
                background-color: #201d2d;
                color: #ffffff;
            }}
            
            .input-hollow:focus {{
                outline: none;
                border-color: #c8c1f0;
                box-shadow: 0 0 15px rgba(200, 193, 240, 0.3);
                background-color: #ffffff;
            }}
            .dark .input-hollow:focus {{
                background-color: #191626;
                border-color: #5e5983;
            }}

            .btn-primary-gradient {{
                background: linear-gradient(135deg, #5e5983 0%, #c8c1f0 100%);
                transition: opacity 0.3s ease, transform 0.2s ease;
            }}
            
            .btn-primary-gradient:hover {{
                opacity: 0.9;
                transform: scale(1.02);
            }}
        </style>
    </head>
    <body class="bg-background dark:bg-[#121016] min-h-screen flex items-center justify-center p-container-padding relative overflow-hidden font-body-md text-on-surface dark:text-[#e0dbec] transition-colors duration-300">
        <!-- Floating Theme Toggle -->
        <div class="absolute top-6 right-6 z-50">
            <button onclick="toggleDarkMode()" class="p-3 rounded-full bg-surface-container/80 dark:bg-[#1f1a30]/80 text-primary dark:text-[#b4aaf2] border border-white/20 dark:border-white/5 shadow-md backdrop-blur-md flex items-center justify-center hover:scale-110 transition-transform">
                <span class="material-symbols-outlined" id="theme-icon">dark_mode</span>
            </button>
        </div>
        <div class="absolute top-[-10%] left-[-10%] w-[50%] h-[50%] rounded-full bg-secondary-fixed opacity-30 blur-[100px] -z-10 dark:opacity-15"></div>
        <div class="absolute bottom-[-10%] right-[-10%] w-[60%] h-[60%] rounded-full bg-primary-container opacity-40 blur-[120px] -z-10 dark:opacity-20"></div>
        <div class="w-full max-w-[1000px] mx-auto grid grid-cols-1 md:grid-cols-2 gap-stack-lg items-center z-10">
            <!-- Left Side: Context & Branding -->
            <div class="flex flex-col justify-center space-y-stack-md text-center md:text-left order-2 md:order-1 px-4 md:px-0">
                <div>
                    <h1 class="font-display-lg-mobile text-display-lg-mobile md:font-display-lg md:text-display-lg text-primary dark:text-[#b4aaf2] mb-unit">Serene Pulse</h1>
                    <p class="font-headline-md text-headline-md text-on-surface-variant dark:text-[#b0a9c0] opacity-80">El Observador Silencioso.</p>
                </div>
                <p class="font-body-lg text-body-lg text-on-surface-variant dark:text-[#b0a9c0] max-w-[400px] mx-auto md:mx-0 leading-relaxed">
                    Crea tu cuenta ingresando un usuario, tu correo institucional y tu contraseña.
                </p>
            </div>
            <!-- Right Side: Register Form Canvas -->
            <div class="glass-panel rounded-xl p-8 md:p-12 shadow-[0_20px_40px_rgba(94,89,131,0.05)] flex flex-col items-center justify-center order-1 md:order-2 w-full max-w-[450px] mx-auto">
                <img alt="Serene Pulse Logo" class="w-24 h-24 rounded-full mb-stack-md shadow-[0_10px_30px_rgba(200,193,240,0.3)] object-cover" src="https://lh3.googleusercontent.com/aida/AP1WRLvTpvVzbm6t3e3pSe3PNivw3uCzrxL4N9ILyVl0lTorK6yAWKcIPNqqKSrkC5bPl1ny1kAHGAE5XRYr8r4GVJvTZ5wAEP3t6qFqsD74O63ceAUogWS_Q3BtJVC1KRcwHVINZ8xZUHnM8riyNQ32-MFcstx7QZ3DMzcKMRi7zjNIUqINrrg_mADgoi9QgT5A-D7BCiROhMQrUMhrounANLT9vIW56u1vQMRhPUog5WKDHgBO8cIGy2KeFA"/>
                <h2 class="font-headline-md text-headline-md text-on-surface dark:text-white mb-stack-lg">Crear Cuenta</h2>
                
                {error_msg}
                
                <form action="/register" method="POST" class="w-full flex flex-col space-y-stack-sm">
                    <div class="relative w-full">
                        <span class="material-symbols-outlined absolute left-4 top-1/2 -translate-y-1/2 text-outline dark:text-[#8d8a9a]">account_circle</span>
                        <input class="input-hollow w-full rounded-full py-4 pl-12 pr-6 font-body-md text-body-md text-on-surface dark:text-white placeholder:text-outline-variant" placeholder="Usuario" required name="username" id="username" type="text" autocomplete="username"/>
                    </div>
                    <div class="relative w-full">
                        <span class="material-symbols-outlined absolute left-4 top-1/2 -translate-y-1/2 text-outline dark:text-[#8d8a9a]">mail</span>
                        <input class="input-hollow w-full rounded-full py-4 pl-12 pr-6 font-body-md text-body-md text-on-surface dark:text-white placeholder:text-outline-variant" placeholder="Correo Electrónico" required name="email" id="email" type="email" autocomplete="email"/>
                    </div>
                    <div class="relative w-full">
                        <span class="material-symbols-outlined absolute left-4 top-1/2 -translate-y-1/2 text-outline dark:text-[#8d8a9a]">lock</span>
                        <input class="input-hollow w-full rounded-full py-4 pl-12 pr-6 font-body-md text-body-md text-on-surface dark:text-white placeholder:text-outline-variant" placeholder="Contraseña" required name="password" id="password" type="password" autocomplete="new-password"/>
                    </div>
                    <button class="btn-primary-gradient w-full rounded-full py-4 text-on-primary dark:text-black font-body-lg text-body-lg shadow-[0_10px_20px_rgba(94,89,131,0.15)] flex items-center justify-center gap-2 mt-4" type="submit">
                        Registrar Cuenta
                        <span class="material-symbols-outlined">arrow_forward</span>
                    </button>
                    <div class="text-center mt-4">
                        <a href="/login" class="font-label-sm text-label-sm text-primary dark:text-[#b4aaf2] hover:underline">¿Ya tienes una cuenta? Inicia sesión aquí</a>
                    </div>
                </form>
            </div>
        </div>
        <script>
            function applyTheme() {{
                const isDark = localStorage.getItem('theme') === 'dark';
                const html = document.documentElement;
                const icon = document.getElementById('theme-icon');
                
                if (isDark) {{
                    html.classList.remove('light');
                    html.classList.add('dark');
                    if (icon) icon.innerText = 'light_mode';
                }} else {{
                    html.classList.remove('dark');
                    html.classList.add('light');
                    if (icon) icon.innerText = 'dark_mode';
                }}
            }}

            function toggleDarkMode() {{
                const isDark = localStorage.getItem('theme') === 'dark';
                localStorage.setItem('theme', isDark ? 'light' : 'dark');
                applyTheme();
            }}

            applyTheme();
        </script>
    </body>
    </html>
    """

@app.post("/register")
def procesar_register(username: str = Form(...), email: str = Form(...), password: str = Form(...)):
    username = username.strip().lower()
    email = email.strip().lower()
    
    users = load_users()
    
    # 1. Validar que el usuario no exista
    if username in users:
        return RedirectResponse(url="/register?error=El%20nombre%20de%20usuario%20ya%20est%C3%A1%20registrado.", status_code=303)
        
    # 2. Validar que el correo no esté registrado con otro usuario
    if any(user_data.get("email") == email for user_data in users.values()):
        return RedirectResponse(url="/register?error=El%20correo%20electr%C3%B3nico%20ya%20est%C3%A1%20registrado.", status_code=303)
        
    # 3. Guardar el nuevo usuario en el JSON local con contraseña hasheada en SHA-256
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    users[username] = {
        "email": email,
        "password_hash": password_hash
    }
    save_users(users)
    
    return RedirectResponse(url="/login?success=Cuenta%20creada%20exitosamente.%20Inicia%20sesi%C3%B3n.", status_code=303)

@app.post("/login")
def procesar_login(username: str = Form(...), password: str = Form(...)):
    username = username.strip().lower()
    users = load_users()
    
    if username in users:
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        if users[username]["password_hash"] == password_hash:
            response = RedirectResponse(url="/", status_code=303)
            response.set_cookie(key="session_user", value=username, max_age=3600, httponly=True)
            return response
            
    return RedirectResponse(url="/login?error=Usuario%20o%20contrase%C3%B1a%20incorrectos.", status_code=303)

@app.get("/logout")
def cerrar_sesion():
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("session_user")
    return response

@app.get("/tweets")
def obtener_tweets(session_user: str = Cookie(None)):
    """Retorna los primeros 20 tweets almacenados en la base de datos para visualizarlos en el Front."""
    if not session_user:
        raise HTTPException(status_code=401, detail="No autorizado")
    
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT id_tweet, entity, sentiment_real, tweet_text, sentiment_prediction FROM tweets LIMIT 20")
            resultado = cursor.fetchall()
            return resultado
    finally:
        connection.close()

@app.post("/predict-db")
def analizar_y_guardar_tweet(request: PredictRequest, session_user: str = Cookie(None)):
    """Obtiene un tweet específico por ID de MySQL, lo analiza con el LLM local y guarda la predicción en la BD."""
    if not session_user:
        raise HTTPException(status_code=401, detail="No autorizado")
        
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            # 1. Buscar el tweet en MySQL
            cursor.execute("SELECT tweet_text FROM tweets WHERE id_tweet = %s", (request.id_tweet,))
            row = cursor.fetchone()
            
            if not row:
                raise HTTPException(status_code=404, detail="Tweet no encontrado en la base de datos.")
            
            texto = row['tweet_text']
            
            # 2. Inferencia local con el modelo LM Studio
            prediction = clasificar_sentimiento_lmstudio(texto)
            label_pred = prediction['label']
            confidence_pred = round(prediction['score'], 4)
            
            # 3. Persistir el resultado en la base de datos
            sql_update = """
                UPDATE tweets 
                SET sentiment_prediction = %s, confidence = %s 
                WHERE id_tweet = %s
            """
            cursor.execute(sql_update, (label_pred, confidence_pred, request.id_tweet))
            connection.commit()
            
            return {
                "id_tweet": request.id_tweet,
                "text": texto,
                "sentiment_llm": label_pred,
                "confidence": confidence_pred,
                "status": "Actualizado en Base de Datos"
            }
    finally:
        connection.close()

@app.post("/predict")
def analizar_texto(request: LivePredictRequest, session_user: str = Cookie(None)):
    """Inferencia al vuelo para texto ingresado manualmente por el usuario."""
    if not session_user:
        raise HTTPException(status_code=401, detail="No autorizado")
        
    prediction = clasificar_sentimiento_lmstudio(request.text)
    return {
        "text": request.text,
        "sentiment": prediction['label'],
        "confidence": round(prediction['score'], 4)
    }


@app.get("/", response_class=HTMLResponse)
def frontend(session_user: str = Cookie(None)):
    if not session_user:
        return RedirectResponse(url="/login", status_code=303)
        
    html_content = """
    <!DOCTYPE html>
    <html class="light" lang="es">
    <head>
        <meta charset="utf-8"/>
        <meta content="width=device-width, initial-scale=1.0" name="viewport"/>
        <title>Tablero de Control - Serene Pulse</title>
        <script>
            if (localStorage.getItem('theme') === 'dark') {
                document.documentElement.classList.add('dark');
                document.documentElement.classList.remove('light');
            } else {
                document.documentElement.classList.add('light');
                document.documentElement.classList.remove('dark');
            }
        </script>
        <script src="https://cdn.tailwindcss.com?plugins=forms,container-queries"></script>
        <link href="https://fonts.googleapis.com/css2?family=Quicksand:wght@400;500;600;700&amp;display=swap" rel="stylesheet"/>
        <link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&amp;display=swap" rel="stylesheet"/>
        <script id="tailwind-config">
            tailwind.config = {
              darkMode: "class",
              theme: {
                extend: {
                  "colors": {
                          "surface-dim": "#d9dadb",
                          "surface-bright": "#f8f9fa",
                          "outline-variant": "#c9c5cf",
                          "on-secondary-fixed": "#01201c",
                          "inverse-primary": "#c8c1f0",
                          "surface-container-highest": "#e1e3e4",
                          "on-primary-fixed-variant": "#474269",
                          "inverse-on-surface": "#f0f1f2",
                          "on-primary-fixed": "#1b163b",
                          "on-error": "#ffffff",
                          "tertiary-container": "#eccecb",
                          "surface-container": "#edeeef",
                          "on-surface-variant": "var(--color-on-surface-variant)",
                          "secondary-fixed": "#c8e9e2",
                          "on-error-container": "#93000a",
                          "secondary-container": "#c8e9e2",
                          "on-primary-container": "#5c5780",
                          "on-tertiary-container": "#6d5654",
                          "on-tertiary-fixed-variant": "#574240",
                          "on-surface": "var(--color-on-surface)",
                          "inverse-surface": "#2e3132",
                          "on-tertiary": "#ffffff",
                          "on-secondary": "#ffffff",
                          "on-secondary-fixed-variant": "#2f4c47",
                          "surface-container-low": "var(--color-surface-container-low)",
                          "secondary-fixed-dim": "#adcdc7",
                          "primary": "#5e5983",
                          "on-background": "var(--color-on-background)",
                          "on-secondary-container": "#4c6a65",
                          "on-tertiary-fixed": "#281716",
                          "primary-container": "#d6cfff",
                          "background": "var(--color-background)",
                          "surface-tint": "#5e5983",
                          "tertiary-fixed-dim": "#ddc0bd",
                          "secondary": "#46645f",
                          "surface": "var(--color-surface)",
                          "outline": "var(--color-outline)",
                          "tertiary": "#705957",
                          "surface-variant": "#e1e3e4",
                          "error": "#ba1a1a",
                          "surface-container-lowest": "var(--color-surface-container-lowest)",
                          "primary-fixed-dim": "#c8c1f0",
                          "error-container": "#ffdad6",
                          "on-primary": "#ffffff",
                          "tertiary-fixed": "#fadbd8",
                          "primary-fixed": "#e5deff",
                          "surface-container-high": "#e7e8e9"
                  },
                  "borderRadius": {
                          "DEFAULT": "1rem",
                          "lg": "2rem",
                          "xl": "3rem",
                          "full": "9999px"
                  },
                  "spacing": {
                          "unit": "8px",
                          "stack-lg": "48px",
                          "stack-sm": "12px",
                          "container-padding": "32px",
                          "stack-md": "24px",
                          "gutter": "24px"
                  },
                  "fontFamily": {
                          "display-lg": ["Quicksand"],
                          "body-lg": ["Quicksand"],
                          "label-sm": ["Quicksand"],
                          "display-lg-mobile": ["Quicksand"],
                          "headline-md": ["Quicksand"],
                          "body-md": ["Quicksand"]
                  },
                  "fontSize": {
                          "display-lg": [
                                  "48px",
                                  {
                                          "lineHeight": "1.2",
                                          "letterSpacing": "-0.02em",
                                          "fontWeight": "700"
                                  }
                          ],
                          "body-lg": [
                                  "18px",
                                  {
                                          "lineHeight": "1.6",
                                          "fontWeight": "500"
                                  }
                          ],
                          "label-sm": [
                                  "12px",
                                  {
                                          "lineHeight": "1",
                                          "letterSpacing": "0.05em",
                                          "fontWeight": "600"
                                  }
                          ],
                          "display-lg-mobile": [
                                  "32px",
                                  {
                                          "lineHeight": "1.2",
                                          "fontWeight": "700"
                                  }
                          ],
                          "headline-md": [
                                  "24px",
                                  {
                                          "lineHeight": "1.4",
                                          "fontWeight": "600"
                                  }
                          ],
                          "body-md": [
                                  "16px",
                                  {
                                          "lineHeight": "1.6",
                                          "fontWeight": "400"
                                  }
                          ]
                  }
                },
              },
            }
        </script>
        <style>
            :root {
                --color-background: #f8f9fa;
                --color-on-background: #191c1d;
                --color-surface-container-lowest: #ffffff;
                --color-surface-container-low: #f3f4f5;
                --color-surface: #f8f9fa;
                --color-on-surface: #191c1d;
                --color-on-surface-variant: #48464e;
                --color-outline: #78767f;
            }
            .dark {
                --color-background: #121016;
                --color-on-background: #e0dbec;
                --color-surface-container-lowest: #151221;
                --color-surface-container-low: #1c192b;
                --color-surface: #121016;
                --color-on-surface: #ffffff;
                --color-on-surface-variant: #b0a9c0;
                --color-outline: #8d8a9a;
            }

            body {
                background-color: var(--color-background);
                color: var(--color-on-background);
            }
            
            .glass-card {
                background: rgba(255, 255, 255, 0.6);
                backdrop-filter: blur(20px);
                border: 1px solid rgba(255, 255, 255, 0.3);
                border-radius: theme('borderRadius.xl');
            }
            .dark .glass-card {
                background: rgba(25, 22, 38, 0.6);
                border: 1px solid rgba(255, 255, 255, 0.08);
            }

            .input-hollow {
                background-color: #F1F3F5;
                border: 1px solid transparent;
                transition: all 0.3s ease;
            }
            .dark .input-hollow {
                background-color: #201d2d;
                color: #ffffff;
            }

            .floating-layer {
                box-shadow: 0 40px 40px -15px rgba(94, 89, 131, 0.1);
            }

            .sentiment-chip {
                display: inline-flex;
                align-items: center;
                justify-content: center;
                border-radius: theme('borderRadius.full');
                padding: 4px 12px;
                font-size: 12px;
                font-weight: 600;
            }

            /* Hide scrollbar for clean look */
            ::-webkit-scrollbar {
                width: 0px;
                background: transparent;
            }
        </style>
    </head>
    <body class="antialiased min-h-screen flex flex-col md:flex-row pb-24 md:pb-0 overflow-x-hidden bg-background dark:bg-[#121016] text-on-background dark:text-[#e0dbec] transition-colors duration-300">
        <!-- Soft diffuse background elements -->
        <div class="absolute top-[-10%] left-[-10%] w-[50%] h-[50%] rounded-full bg-secondary-fixed opacity-20 blur-[100px] -z-10 dark:opacity-10"></div>
        <div class="absolute bottom-[-10%] right-[-10%] w-[60%] h-[60%] rounded-full bg-primary-container opacity-30 blur-[120px] -z-10 dark:opacity-15"></div>

        <!-- Top App Bar (Mobile) -->
        <header class="md:hidden fixed top-0 w-full z-50 bg-surface/60 dark:bg-[#151221]/60 backdrop-blur-xl border-b border-white/10 dark:border-white/5 shadow-[0_40px_40px_-15px_rgba(94,89,131,0.1)] flex justify-between items-center px-container-padding py-stack-sm transition-colors duration-300">
            <div class="font-display-lg-mobile text-display-lg-mobile text-primary dark:text-[#b4aaf2] tracking-tight">Serene Pulse</div>
            <div class="flex items-center gap-4 text-primary dark:text-[#b4aaf2]">
                <button onclick="toggleDarkMode()" class="material-symbols-outlined hover:scale-110 transition-transform" id="mobile-theme-icon" title="Cambiar Tema">dark_mode</button>
                <a href="/logout" class="material-symbols-outlined hover:text-error transition-colors" title="Cerrar Sesión">logout</a>
            </div>
        </header>

        <!-- Side Navigation (Desktop) -->
        <nav class="hidden md:flex flex-col w-64 h-screen fixed left-0 top-0 bg-surface-container-lowest/60 dark:bg-[#151221]/60 backdrop-blur-2xl border-r border-white/20 dark:border-white/5 p-container-padding shadow-[0_40px_40px_-15px_rgba(94,89,131,0.1)] z-40 transition-colors duration-300">
            <div class="font-headline-md text-headline-md text-primary dark:text-[#b4aaf2] tracking-tight mb-stack-lg">Serene Pulse</div>
            <div class="flex flex-col gap-4 h-full">
                <a class="flex items-center gap-4 px-4 py-3 rounded-xl bg-primary-container/50 dark:bg-[#342e4f]/50 text-on-primary-container dark:text-[#b4aaf2] font-bold transition-all" href="#">
                    <span class="material-symbols-outlined" style="font-variation-settings: 'FILL' 1;">analytics</span>
                    <span class="font-label-sm text-label-sm">Tablero</span>
                </a>
                
                <button onclick="toggleDarkMode()" class="flex items-center gap-4 px-4 py-3 rounded-xl text-primary dark:text-[#b4aaf2] hover:bg-primary-container/20 dark:hover:bg-white/5 transition-colors mt-auto w-full text-left">
                    <span class="material-symbols-outlined" id="theme-icon">dark_mode</span>
                    <span class="font-label-sm text-label-sm" id="theme-text">Modo Oscuro</span>
                </button>
                
                <a class="flex items-center gap-4 px-4 py-3 rounded-xl text-error hover:bg-error-container/20 dark:hover:bg-error/10 transition-colors" href="/logout">
                    <span class="material-symbols-outlined">logout</span>
                    <span class="font-label-sm text-label-sm">Cerrar Sesión</span>
                </a>
            </div>
        </nav>

        <!-- Main Content Canvas -->
        <main class="flex-1 px-container-padding pt-24 md:pt-12 md:ml-64 w-full max-w-7xl mx-auto space-y-stack-lg pb-12">
            <!-- Header -->
            <header class="max-w-3xl">
                <h1 class="font-display-lg text-display-lg-mobile md:text-display-lg text-on-surface mb-stack-sm">Tablero Bento Grid</h1>
                <p class="font-body-lg text-body-lg text-on-surface-variant/80">Monitorea los datos de MySQL, analiza tweets e inferencias en vivo con IA local. Sesión: <strong class="text-primary capitalize">{USUARIO_ACTIVO}</strong></p>
            </header>

            <!-- Architecture Bento Grid -->
            <div class="grid grid-cols-1 md:grid-cols-3 gap-gutter">
                <!-- 1. Data Collection -->
                <div class="glass-card p-6 floating-layer flex flex-col">
                    <div class="flex items-center gap-3 mb-4">
                        <div class="p-3 bg-secondary-container/50 rounded-full text-secondary flex items-center justify-center">
                            <span class="material-symbols-outlined">database</span>
                        </div>
                        <h2 class="font-headline-md text-headline-md text-on-surface">Base de Datos</h2>
                    </div>
                    <p class="font-body-md text-body-md text-on-surface-variant/80 mb-6 flex-1">Tweets y clasificaciones de sentimientos persistidas de manera local en el servidor MySQL.</p>
                    <div class="bg-surface-container-low rounded-lg p-4 font-mono text-sm text-on-surface-variant/70 border border-white/50">
                        <div class="flex justify-between border-b border-surface-variant pb-2 mb-2">
                            <span>Estado</span><span id="db-status-badge" class="text-error font-bold">Desconectada</span>
                        </div>
                        <div class="flex justify-between border-b border-surface-variant pb-2 mb-2">
                            <span>Ubicación</span><span>Localhost</span>
                        </div>
                        <div class="flex justify-between">
                            <span>Motor</span><span>InnoDB (MySQL)</span>
                        </div>
                    </div>
                </div>

                <!-- 2. Sentiment Analysis -->
                <div class="glass-card p-6 floating-layer flex flex-col md:col-span-2 relative overflow-hidden">
                    <div class="absolute -right-20 -top-20 w-64 h-64 bg-primary-container/20 rounded-full blur-3xl z-0 pointer-events-none"></div>
                    <div class="relative z-10">
                        <div class="flex items-center gap-3 mb-4">
                            <div class="p-3 bg-primary-container/50 rounded-full text-primary flex items-center justify-center">
                                <span class="material-symbols-outlined">auto_awesome</span>
                            </div>
                            <h2 class="font-headline-md text-headline-md text-on-surface">Inferencia con LLM</h2>
                        </div>
                        <p class="font-body-md text-body-md text-on-surface-variant/80 mb-6 max-w-lg">Procesamiento cognitivo local que clasifica los textos en sentimientos para entender el panorama general.</p>
                        <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
                            <div class="bg-surface-container-lowest/80 dark:bg-[#191626]/80 rounded-lg p-4 border border-white/40 dark:border-white/5 transition-colors duration-300">
                                <span class="block font-label-sm text-label-sm text-outline mb-1">Modelo Activo</span>
                                <span class="font-body-md text-body-md font-semibold text-primary dark:text-[#b4aaf2]">LM Studio GGUF</span>
                            </div>
                            <div class="bg-surface-container-lowest/80 dark:bg-[#191626]/80 rounded-lg p-4 border border-white/40 dark:border-white/5 transition-colors duration-300">
                                <span class="block font-label-sm text-label-sm text-outline mb-1">Puerto API</span>
                                <span class="font-body-md text-body-md font-semibold text-primary dark:text-[#b4aaf2]">1234 (Local)</span>
                            </div>
                            <div class="bg-surface-container-lowest/80 dark:bg-[#191626]/80 rounded-lg p-4 border border-white/40 dark:border-white/5 transition-colors duration-300">
                                <span class="block font-label-sm text-label-sm text-outline mb-1">Privacidad</span>
                                <span class="font-body-md text-body-md font-semibold text-secondary dark:text-[#83cbdc]">Aislado (Offline)</span>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- 3. Visualization -->
                <div class="glass-card p-6 floating-layer flex flex-col md:col-span-3">
                    <div class="flex items-center gap-3 mb-4">
                        <div class="p-3 bg-tertiary-container/50 rounded-full text-tertiary flex items-center justify-center">
                            <span class="material-symbols-outlined">palette</span>
                        </div>
                        <h2 class="font-headline-md text-headline-md text-on-surface">Mapeo de Espectros</h2>
                    </div>
                    <p class="font-body-md text-body-md text-on-surface-variant/80 mb-6 max-w-2xl">Representación visual de los sentimientos recopilados. Los colores pastel identifican de inmediato las categorías.</p>
                    <div class="h-8 w-full rounded-full bg-gradient-to-r from-secondary-container via-primary-container to-tertiary-container mb-2"></div>
                    <div class="flex justify-between text-label-sm text-outline font-label-sm px-2">
                        <span>Positivo (Calma)</span>
                        <span>Neutral</span>
                        <span>Negativo / Irrelevante (Alerta)</span>
                    </div>
                </div>
            </div>

            <!-- Live Analyzer Card -->
            <div class="glass-card p-8 floating-layer flex flex-col w-full">
                <div class="flex items-center gap-3 mb-4">
                    <div class="p-3 bg-primary-container/50 rounded-full text-primary flex items-center justify-center">
                        <span class="material-symbols-outlined">psychology</span>
                    </div>
                    <h2 class="font-headline-md text-headline-md text-on-surface">Analizador de Texto en Vivo</h2>
                </div>
                <p class="font-body-md text-body-md text-on-surface-variant/80 mb-6">
                    Escribe cualquier comentario en inglés para analizar su sentimiento en tiempo real utilizando el LLM local en LM Studio.
                </p>
                <div class="flex flex-col gap-4 w-full">
                    <textarea id="liveTextInput" class="input-hollow w-full rounded-xl p-4 font-body-md text-body-md text-black placeholder:text-outline-variant resize-none" rows="3" placeholder="Escribe un comentario en inglés para analizar su sentimiento..." style="overflow-y:hidden;"></textarea>
                    <div class="flex justify-end">
                        <button id="liveAnalyzeBtn" onclick="analizarTextoEnVivo()" class="btn-primary-gradient rounded-full py-3 px-8 text-black font-body-lg text-body-lg shadow-[0_10px_20px_rgba(94,89,131,0.15)] flex items-center justify-center gap-2 w-full sm:w-auto">
                            Analizar Tweet
                            <span class="material-symbols-outlined">arrow_forward</span>
                        </button>
                    </div>
                </div>
                
                <!-- Live Result Area -->
                <div id="liveResultBox" class="mt-6 p-6 rounded-xl border border-dashed border-outline-variant hidden flex-col gap-4 transition-all duration-300">
                    <div class="flex items-center justify-between w-full">
                        <div class="flex items-center gap-4">
                            <span id="liveResultIcon" class="material-symbols-outlined text-primary" style="font-size: 32px;">sentiment_satisfied</span>
                            <div>
                                <span id="liveResultLabel" class="block font-headline-md text-headline-md text-on-surface">Sentimiento</span>
                                <span id="liveResultScore" class="block font-label-sm text-label-sm text-outline">Confianza</span>
                            </div>
                        </div>
                        <span id="liveResultChip" class="sentiment-chip">Label</span>
                    </div>
                    <div class="bg-surface-container-low dark:bg-[#1c192b] p-4 rounded-xl text-sm italic text-on-surface-variant/80 dark:text-[#b0a9c0] border border-white/50 dark:border-white/5 w-full">
                        <strong>Tweet analizado:</strong> <span id="liveResultText" class="text-black dark:text-[#e0dbec]"></span>
                    </div>
                </div>
            </div>

            <!-- Data Table Preview -->
            <div class="glass-card p-8 floating-layer">
                <div class="flex justify-between items-center mb-6">
                    <h3 class="font-headline-md text-headline-md text-on-surface">Base de Datos de Tweets</h3>
                </div>
                <div class="overflow-x-auto">
                    <table class="w-full text-left border-collapse">
                        <thead>
                            <tr class="border-b border-surface-variant/50">
                                <th class="py-4 px-4 font-label-sm text-label-sm text-outline uppercase tracking-wider">ID Tweet</th>
                                <th class="py-4 px-4 font-label-sm text-label-sm text-outline uppercase tracking-wider">Entidad</th>
                                <th class="py-4 px-4 font-label-sm text-label-sm text-outline uppercase tracking-wider">Texto del Tweet</th>
                                <th class="py-4 px-4 font-label-sm text-label-sm text-outline uppercase tracking-wider">Predicción IA (MySQL)</th>
                                <th class="py-4 px-4 font-label-sm text-label-sm text-outline uppercase tracking-wider">Sentimiento Real</th>
                                <th class="py-4 px-4 font-label-sm text-label-sm text-outline uppercase tracking-wider text-right">Acción</th>
                            </tr>
                        </thead>
                        <tbody id="tabla-tweets" class="font-body-md text-body-md text-on-surface-variant">
                            <tr>
                                <td colspan="6" class="py-8 text-center text-outline italic">Cargando tweets...</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </main>

        <!-- Bottom Nav Bar (Mobile) -->
        <nav class="md:hidden fixed bottom-0 left-0 w-full z-50 flex justify-around items-center px-4 pb-8 pt-4 bg-surface-container-lowest/60 dark:bg-[#151221]/60 backdrop-blur-2xl border-t border-white/20 dark:border-white/5 shadow-[0_-10px_40px_rgba(94,89,131,0.05)] rounded-t-xl transition-colors duration-300">
            <a class="flex flex-col items-center justify-center bg-primary-container/50 dark:bg-[#342e4f]/50 text-on-primary-container dark:text-[#b4aaf2] rounded-full px-6 py-2 scale-95 transition-transform duration-200" href="#">
                <span class="material-symbols-outlined" style="font-variation-settings: 'FILL' 1;">analytics</span>
                <span class="font-label-sm text-label-sm mt-1 font-bold">Tablero</span>
            </a>
            <a class="flex flex-col items-center justify-center text-error px-6 py-2 hover:scale-110 transition-transform" href="/logout">
                <span class="material-symbols-outlined">logout</span>
                <span class="font-label-sm text-label-sm mt-1">Cerrar</span>
            </a>
        </nav>

        <script>
            function getSentimentChip(sentiment) {
                if (!sentiment) return '<span class="text-outline-variant italic">Sin procesar</span>';
                
                const s = sentiment.trim().toLowerCase();
                if (s === 'positive') {
                    return '<span class="sentiment-chip bg-secondary-container/30 text-secondary">Positive</span>';
                } else if (s === 'negative') {
                    return '<span class="sentiment-chip bg-error-container/30 text-error">Negative</span>';
                } else if (s === 'neutral') {
                    return '<span class="sentiment-chip bg-primary-container/30 text-primary">Neutral</span>';
                } else if (s === 'irrelevant') {
                    return '<span class="sentiment-chip bg-surface-variant/50 text-outline">Irrelevant</span>';
                } else {
                    return `<span class="sentiment-chip bg-surface-variant/50 text-outline">${sentiment}</span>`;
                }
            }

            async function cargarTweets() {
                try {
                    const response = await fetch('/tweets');
                    if (response.status === 401) {
                        window.location.href = '/login';
                        return;
                    }
                    const tweets = await response.json();
                    const tbody = document.getElementById('tabla-tweets');
                    tbody.innerHTML = '';
                    
                    // Activar el badge de conexión
                    document.getElementById('db-status-badge').className = "text-secondary font-bold";
                    document.getElementById('db-status-badge').innerText = "Activa";
                    
                    tweets.forEach(t => {
                        const predCell = getSentimentChip(t.sentiment_prediction);
                        const realCell = getSentimentChip(t.sentiment_real);
                        const textClean = (t.tweet_text || '').replace(/"/g, '&quot;');
                        
                        tbody.innerHTML += `
                            <tr class="border-b border-surface-variant/30 hover:bg-surface-container-low/30 transition-colors">
                                <td class="py-4 px-4 font-mono text-sm">${t.id_tweet}</td>
                                <td class="py-4 px-4 font-semibold text-primary">${t.entity}</td>
                                <td class="py-4 px-4 text-on-surface-variant/80 max-w-[300px] truncate" title="${textClean}">${t.tweet_text}</td>
                                <td class="py-4 px-4" id="pred-${t.id_tweet}">${predCell}</td>
                                <td class="py-4 px-4">${realCell}</td>
                                <td class="py-4 px-4 text-right">
                                    <button onclick="procesarTweet(${t.id_tweet})" class="bg-primary/5 text-primary hover:bg-primary/10 hover:scale-105 transition-all px-4 py-2 rounded-full font-label-sm text-label-sm inline-flex items-center gap-1">
                                        Analizar <span class="material-symbols-outlined" style="font-size: 14px;">auto_awesome</span>
                                    </button>
                                </td>
                            </tr>
                        `;
                    });
                } catch (e) {
                    console.error("Error al cargar tweets:", e);
                    const tbody = document.getElementById('tabla-tweets');
                    tbody.innerHTML = '<tr><td colspan="6" class="py-8 text-center text-error font-bold">Error de conexión a la Base de Datos</td></tr>';
                    
                    document.getElementById('db-status-badge').className = "text-error font-bold";
                    document.getElementById('db-status-badge').innerText = "Desconectada";
                }
            }

            async function procesarTweet(id) {
                const tdPred = document.getElementById(`pred-${id}`);
                tdPred.innerHTML = '<span class="text-outline-variant italic animate-pulse">Procesando...</span>';
                
                try {
                    const response = await fetch('/predict-db', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({id_tweet: id})
                    });
                    
                    if (response.status === 401) {
                        window.location.href = '/login';
                        return;
                    }
                    
                    const data = await response.json();
                    if (response.ok) {
                        tdPred.innerHTML = getSentimentChip(data.sentiment_llm);
                    } else {
                        tdPred.innerHTML = '<span class="text-error font-bold">Error</span>';
                    }
                } catch (e) {
                    tdPred.innerHTML = '<span class="text-error font-bold">Error Red</span>';
                }
            }

            async function analizarTextoEnVivo() {
                const text = document.getElementById('liveTextInput').value.trim();
                if (!text) {
                    alert("Por favor escribe algún texto primero.");
                    return;
                }
                
                const btn = document.getElementById('liveAnalyzeBtn');
                const box = document.getElementById('liveResultBox');
                const label = document.getElementById('liveResultLabel');
                const score = document.getElementById('liveResultScore');
                const chip = document.getElementById('liveResultChip');
                const icon = document.getElementById('liveResultIcon');
                
                btn.disabled = true;
                btn.innerText = "Analizando Tweet...";
                
                try {
                    const response = await fetch('/predict', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({text: text})
                    });
                    
                    if (response.status === 401) {
                        window.location.href = '/login';
                        return;
                    }
                    
                    const data = await response.json();
                    
                    if (response.ok) {
                        box.classList.remove('hidden');
                        box.classList.add('flex');
                        
                        // Mostrar el tweet analizado y limpiar el input
                        document.getElementById('liveResultText').innerText = text;
                        const txInput = document.getElementById('liveTextInput');
                        txInput.value = "";
                        txInput.style.height = "auto";
                        
                        label.innerText = "Análisis Completado";
                        score.innerText = `Confianza: ${(data.confidence * 100).toFixed(2)}%`;
                        
                        // Update chip
                        chip.innerText = data.sentiment;
                        chip.className = "sentiment-chip";
                        
                        const s = data.sentiment.trim().toLowerCase();
                        if (s === 'positive') {
                            chip.classList.add('bg-secondary-container/30', 'text-secondary');
                            icon.innerText = "sentiment_very_satisfied";
                        } else if (s === 'negative') {
                            chip.classList.add('bg-error-container/30', 'text-error');
                            icon.innerText = "sentiment_very_dissatisfied";
                        } else if (s === 'neutral') {
                            chip.classList.add('bg-primary-container/30', 'text-primary');
                            icon.innerText = "sentiment_neutral";
                        } else if (s === 'irrelevant') {
                            chip.classList.add('bg-surface-variant/50', 'text-outline');
                            icon.innerText = "sentiment_satisfied";
                        } else {
                            chip.classList.add('bg-surface-variant/50', 'text-outline');
                            icon.innerText = "sentiment_satisfied";
                        }
                    } else {
                        alert("Error al analizar el texto.");
                    }
                } catch (e) {
                    alert("Error de conexión al servidor.");
                } finally {
                    btn.disabled = false;
                    btn.innerText = "Analizar Tweet";
                }
            }

            function applyTheme() {
                const isDark = localStorage.getItem('theme') === 'dark';
                const html = document.documentElement;
                const icon = document.getElementById('theme-icon');
                const text = document.getElementById('theme-text');
                const mobileIcon = document.getElementById('mobile-theme-icon');
                
                if (isDark) {
                    html.classList.remove('light');
                    html.classList.add('dark');
                    if (icon) icon.innerText = 'light_mode';
                    if (text) text.innerText = 'Modo Claro';
                    if (mobileIcon) mobileIcon.innerText = 'light_mode';
                } else {
                    html.classList.remove('dark');
                    html.classList.add('light');
                    if (icon) icon.innerText = 'dark_mode';
                    if (text) text.innerText = 'Modo Oscuro';
                    if (mobileIcon) mobileIcon.innerText = 'dark_mode';
                }
            }

            function toggleDarkMode() {
                const isDark = localStorage.getItem('theme') === 'dark';
                localStorage.setItem('theme', isDark ? 'light' : 'dark');
                applyTheme();
            }

            // Cargar datos y configurar auto-crecimiento del textarea al iniciar la página
            window.onload = function() {
                applyTheme();
                cargarTweets();
                
                const tx = document.getElementById('liveTextInput');
                if (tx) {
                    tx.addEventListener("input", function() {
                        this.style.height = "auto";
                        this.style.height = (this.scrollHeight) + "px";
                    }, false);
                }
            };
        </script>
    </body>
    </html>
    """
    # Reemplazar dinámicamente el usuario activo
    html_content = html_content.replace("{USUARIO_ACTIVO}", session_user)
    return HTMLResponse(content=html_content)

if __name__ == "__main__":
    import uvicorn
    # Ejecutamos en el puerto 8000 en todas las interfaces para evitar conflictos de IPv6 en localhost
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)