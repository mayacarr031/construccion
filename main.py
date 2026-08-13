from fastapi import FastAPI, HTTPException, Form, Response, Cookie, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel
import pymysql
from openai import OpenAI

app = FastAPI(title="API de Análisis de Sentimientos con MySQL")

# Configuración de conexión a MySQL
def get_db_connection():
    # Intentar conexión con los parámetros del entorno de desarrollo local (puerto 3308 y contraseña 'lasalle')
    try:
        return pymysql.connect(
            host='localhost',
            port=3308,
            user='root',
            password='lasalle',
            database='db_sentimientos',
            cursorclass=pymysql.cursors.DictCursor
        )
    except Exception:
        # Fallback a los parámetros predeterminados de la tarea escolar (puerto 3306 y contraseña 'password')
        return pymysql.connect(
            host='localhost',
            port=3306,
            user='root',
            password='password',
            database='db_sentimientos',
            cursorclass=pymysql.cursors.DictCursor
        )

# Inicializar cliente compatible con la API de OpenAI para LM Studio
client = OpenAI(
    base_url="http://localhost:1234/v1",
    api_key="lm-studio"
)

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
        response = client.chat.completions.create(
            model="local-model", # LM Studio usa el modelo cargado
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Text: {texto}"}
            ],
            temperature=0.0, # Temperatura 0 para mayor determinismo y consistencia
            max_tokens=5
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
def vista_login(error: str = None):
    error_msg = f'<div class="error-msg">{error}</div>' if error else ''
    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Iniciar Sesión - Control de Sentimientos</title>
        <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet" />
        <style>
            :root {{
                --bg-color: #0f172a;
                --card-bg: rgba(30, 41, 59, 0.7);
                --text-color: #e2e8f0;
                --text-muted: #94a3b8;
                --primary: #3b82f6;
                --border-color: rgba(255, 255, 255, 0.08);
                --gradient: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%);
            }}
            body {{
                font-family: 'Plus Jakarta Sans', Arial, sans-serif;
                background-color: var(--bg-color);
                color: var(--text-color);
                display: flex;
                align-items: center;
                justify-content: center;
                min-height: 100vh;
                margin: 0;
                background-image: 
                    radial-gradient(at 0% 0%, rgba(59, 130, 246, 0.1) 0px, transparent 50%),
                    radial-gradient(at 100% 0%, rgba(139, 92, 246, 0.1) 0px, transparent 50%);
                background-attachment: fixed;
            }}
            .login-container {{
                background: var(--card-bg);
                border: 1px solid var(--border-color);
                border-radius: 16px;
                padding: 40px;
                width: 100%;
                max-width: 400px;
                box-shadow: 0 10px 30px -10px rgba(0, 0, 0, 0.5);
                backdrop-filter: blur(12px);
            }}
            h2 {{
                font-size: 1.8rem;
                font-weight: 700;
                margin: 0 0 10px 0;
                text-align: center;
                background: var(--gradient);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
            }}
            p {{
                color: var(--text-muted);
                text-align: center;
                margin-top: 0;
                margin-bottom: 30px;
                font-size: 0.95rem;
            }}
            .form-group {{
                margin-bottom: 20px;
            }}
            label {{
                display: block;
                margin-bottom: 8px;
                font-size: 0.9rem;
                font-weight: 500;
                color: var(--text-color);
            }}
            input {{
                width: 100%;
                box-sizing: border-box;
                background: rgba(15, 23, 42, 0.6);
                border: 1px solid var(--border-color);
                border-radius: 8px;
                color: #fff;
                padding: 12px 16px;
                font-size: 0.95rem;
                outline: none;
                transition: border-color 0.2s;
            }}
            input:focus {{
                border-color: var(--primary);
            }}
            button {{
                width: 100%;
                background: var(--gradient);
                color: white;
                border: none;
                padding: 12px;
                cursor: pointer;
                border-radius: 8px;
                font-weight: 600;
                font-size: 1rem;
                transition: all 0.2s ease;
                box-shadow: 0 4px 12px rgba(59, 130, 246, 0.25);
                margin-top: 10px;
            }}
            button:hover {{
                opacity: 0.95;
                transform: translateY(-1px);
                box-shadow: 0 6px 16px rgba(59, 130, 246, 0.4);
            }}
            .error-msg {{
                background: rgba(239, 68, 68, 0.15);
                color: #f87171;
                border: 1px solid rgba(239, 68, 68, 0.3);
                padding: 12px;
                border-radius: 8px;
                font-size: 0.9rem;
                margin-bottom: 20px;
                text-align: center;
            }}
        </style>
    </head>
    <body>
        <div class="login-container">
            <h2>Acceso al Sistema</h2>
            <p>Ingresa tus credenciales para continuar</p>
            {error_msg}
            <form action="/login" method="POST">
                <div class="form-group">
                    <label for="username">Usuario</label>
                    <input type="text" id="username" name="username" placeholder="admin" required autocomplete="username">
                </div>
                <div class="form-group">
                    <label for="password">Contraseña</label>
                    <input type="password" id="password" name="password" placeholder="••••••••" required autocomplete="current-password">
                </div>
                <button type="submit">Iniciar Sesión</button>
            </form>
        </div>
    </body>
    </html>
    """

@app.post("/login")
def procesar_login(username: str = Form(...), password: str = Form(...)):
    if username == "admin" and password == "12345":
        response = RedirectResponse(url="/", status_code=303)
        response.set_cookie(key="session_user", value="admin", max_age=3600, httponly=True)
        return response
    else:
        return RedirectResponse(url="/login?error=Usuario%20o%20contrase%C3%B1a%20incorrectos.", status_code=303)

@app.get("/logout")
def cerrar_sesion():
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("session_user")
    return response

@app.get("/tweets")
def obtener_tweets(session_user: str = Cookie(None)):
    """Retorna los primeros 20 tweets almacenados en la base de datos para visualizarlos en el Front."""
    if session_user != "admin":
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
    if session_user != "admin":
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
    if session_user != "admin":
        raise HTTPException(status_code=401, detail="No autorizado")
        
    prediction = clasificar_sentimiento_lmstudio(request.text)
    return {
        "text": request.text,
        "sentiment": prediction['label'],
        "confidence": round(prediction['score'], 4)
    }


@app.get("/", response_class=HTMLResponse)
def frontend(session_user: str = Cookie(None)):
    if session_user != "admin":
        return RedirectResponse(url="/login", status_code=303)
        
    return """
    <!DOCTYPE html>
    <html lang="es">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Panel de Control de Sentimientos (MySQL)</title>
            <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet" />
            <style>
                :root {
                    --bg-color: #0f172a;
                    --card-bg: rgba(30, 41, 59, 0.7);
                    --text-color: #e2e8f0;
                    --text-muted: #94a3b8;
                    --primary: #3b82f6;
                    --border-color: rgba(255, 255, 255, 0.08);
                    --gradient: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%);
                }
                body { 
                    font-family: 'Plus Jakarta Sans', Arial, sans-serif; 
                    margin: 0;
                    padding: 0; 
                    background-color: var(--bg-color); 
                    color: var(--text-color);
                    min-height: 100vh;
                    background-image: 
                        radial-gradient(at 0% 0%, rgba(59, 130, 246, 0.1) 0px, transparent 50%),
                        radial-gradient(at 100% 0%, rgba(139, 92, 246, 0.1) 0px, transparent 50%);
                    background-attachment: fixed;
                }
                header {
                    background: rgba(15, 23, 42, 0.8);
                    backdrop-filter: blur(12px);
                    border-bottom: 1px solid var(--border-color);
                    padding: 16px 40px;
                    position: sticky;
                    top: 0;
                    z-index: 50;
                }
                .nav-container {
                    max-width: 1200px;
                    margin: 0 auto;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                }
                .nav-title {
                    font-size: 1.4rem;
                    font-weight: 700;
                    background: var(--gradient);
                    -webkit-background-clip: text;
                    -webkit-text-fill-color: transparent;
                }
                .nav-user {
                    display: flex;
                    align-items: center;
                    gap: 15px;
                    font-size: 0.9rem;
                }
                .logout-btn {
                    background: rgba(239, 68, 68, 0.1);
                    color: #ef4444;
                    border: 1px solid rgba(239, 68, 68, 0.2);
                    padding: 8px 16px;
                    border-radius: 8px;
                    text-decoration: none;
                    font-weight: 600;
                    font-size: 0.85rem;
                    transition: all 0.2s;
                }
                .logout-btn:hover {
                    background: rgba(239, 68, 68, 0.2);
                    border-color: rgba(239, 68, 68, 0.4);
                }
                .container {
                    max-width: 1200px;
                    margin: 40px auto;
                    padding: 0 20px;
                }
                h2 {
                    font-size: 2rem;
                    font-weight: 700;
                    margin: 0 0 10px 0;
                    color: #fff;
                }
                .desc {
                    color: var(--text-muted);
                    font-size: 1.05rem;
                    margin: 0 0 30px 0;
                    line-height: 1.5;
                }
                .grid {
                    display: grid;
                    grid-template-columns: 1fr;
                    gap: 30px;
                    margin-bottom: 40px;
                }
                @media (min-width: 768px) {
                    .grid {
                        grid-template-columns: 1fr 1fr;
                    }
                }
                .card {
                    background: var(--card-bg);
                    border: 1px solid var(--border-color);
                    border-radius: 16px;
                    padding: 24px;
                    backdrop-filter: blur(12px);
                    box-shadow: 0 10px 30px -10px rgba(0, 0, 0, 0.5);
                }
                .card-title {
                    font-size: 1.25rem;
                    font-weight: 700;
                    margin-top: 0;
                    margin-bottom: 20px;
                    color: #fff;
                    display: flex;
                    align-items: center;
                    gap: 8px;
                }
                textarea {
                    width: 100%;
                    box-sizing: border-box;
                    background: rgba(15, 23, 42, 0.6);
                    border: 1px solid var(--border-color);
                    border-radius: 8px;
                    color: #fff;
                    padding: 16px;
                    font-size: 0.95rem;
                    outline: none;
                    transition: border-color 0.2s;
                    resize: none;
                    height: 120px;
                    font-family: inherit;
                }
                textarea:focus {
                    border-color: var(--primary);
                }
                .btn-container {
                    display: flex;
                    justify-content: flex-end;
                    margin-top: 15px;
                }
                button { 
                    background: var(--gradient); 
                    color: white; 
                    border: none; 
                    padding: 10px 18px; 
                    cursor: pointer; 
                    border-radius: 8px; 
                    font-weight: 600;
                    font-size: 0.85rem;
                    transition: all 0.2s ease;
                    box-shadow: 0 4px 12px rgba(59, 130, 246, 0.25);
                    white-space: nowrap;
                }
                button:hover { 
                    transform: translateY(-1px);
                    box-shadow: 0 6px 16px rgba(59, 130, 246, 0.4);
                    opacity: 0.95;
                }
                button:active {
                    transform: translateY(1px);
                }
                .result-box {
                    margin-top: 20px;
                    padding: 16px;
                    border-radius: 8px;
                    border: 1px solid var(--border-color);
                    display: none;
                    background: rgba(255, 255, 255, 0.02);
                }
                .result-box.active {
                    display: block;
                }
                .result-box.result-POSITIVE, .result-box.result-Positive {
                    background: rgba(16, 185, 129, 0.1);
                    border-color: rgba(16, 185, 129, 0.3);
                    color: #34d399;
                }
                .result-box.result-NEGATIVE, .result-box.result-Negative {
                    background: rgba(239, 68, 68, 0.1);
                    border-color: rgba(239, 68, 68, 0.3);
                    color: #f87171;
                }
                .result-label {
                    font-weight: 700;
                    font-size: 1.1rem;
                    margin-bottom: 4px;
                }
                .result-score {
                    font-size: 0.9rem;
                    opacity: 0.8;
                }
                .table-container {
                    background: var(--card-bg);
                    border: 1px solid var(--border-color);
                    border-radius: 16px;
                    overflow: hidden;
                    box-shadow: 0 10px 30px -10px rgba(0, 0, 0, 0.5);
                    backdrop-filter: blur(12px);
                }
                table { 
                    width: 100%; 
                    border-collapse: collapse; 
                    background: transparent; 
                }
                th, td { 
                    padding: 16px 20px; 
                    border-bottom: 1px solid var(--border-color); 
                    text-align: left; 
                }
                th { 
                    background-color: rgba(15, 23, 42, 0.8); 
                    color: var(--text-color); 
                    font-weight: 600;
                    text-transform: uppercase;
                    font-size: 0.8rem;
                    letter-spacing: 0.05em;
                }
                tr:last-child td {
                    border-bottom: none;
                }
                tr:hover { 
                    background-color: rgba(255, 255, 255, 0.02); 
                }
                strong {
                    color: #fff;
                }
                td i {
                    color: var(--text-muted);
                }
            </style>
        </head>
        <body>
            <header>
                <div class="nav-container">
                    <div class="nav-title">StudioLumina</div>
                    <div class="nav-user">
                        <span>👤 Usuario: <strong>admin</strong></span>
                        <a href="/logout" class="logout-btn">Cerrar Sesión</a>
                    </div>
                </div>
            </header>

            <div class="container">
                <div class="grid">
                    <div>
                        <h2>Panel de Control Inteligente</h2>
                        <p class="desc">Administra el modelo local HuggingFace de clasificación de sentimientos y la base de datos MySQL en tiempo real.</p>
                    </div>
                    
                    <div class="card">
                        <div class="card-title">🔍 Analizador de Texto en Vivo</div>
                        <textarea id="liveTextInput" placeholder="Escribe un comentario en inglés para analizar su sentimiento..."></textarea>
                        <div class="btn-container">
                            <button id="liveAnalyzeBtn" onclick="analizarTextoEnVivo()">Analizar Sentimiento</button>
                        </div>
                        <div id="liveResultBox" class="result-box">
                            <div id="liveResultLabel" class="result-label"></div>
                            <div id="liveResultScore" class="result-score"></div>
                        </div>
                    </div>
                </div>
                
                <h2>Base de Datos Local (MySQL)</h2>
                <p class="desc">Tweets migrados de Kaggle. Utiliza el modelo local para procesar o actualizar la predicción persistente.</p>
                
                <div class="table-container">
                    <table>
                        <thead>
                            <tr>
                                <th>ID Tweet</th>
                                <th>Entidad</th>
                                <th>Sentimiento Real (Kaggle)</th>
                                <th>Texto del Tweet</th>
                                <th>Predicción IA (MySQL)</th>
                                <th>Acción</th>
                            </tr>
                        </thead>
                        <tbody id="tabla-tweets">
                        </tbody>
                    </table>
                </div>
            </div>

            <script>
                async function cargarTweets() {
                    const response = await fetch('/tweets');
                    if (response.status === 401) {
                        window.location.href = '/login';
                        return;
                    }
                    const tweets = await response.json();
                    const tbody = document.getElementById('tabla-tweets');
                    tbody.innerHTML = '';
                    
                    tweets.forEach(t => {
                        tbody.innerHTML += `
                            <tr>
                                <td>${t.id_tweet}</td>
                                <td>${t.entity}</td>
                                <td><strong>${t.sentiment_real}</strong></td>
                                <td>${t.tweet_text}</td>
                                <td id="pred-${t.id_tweet}">${t.sentiment_prediction ? t.sentiment_prediction : '<i>Sin procesar</i>'}</td>
                                <td><button onclick="procesarTweet(${t.id_tweet})">Analizar con LLM</button></td>
                            </tr>
                        `;
                    });
                }

                async function procesarTweet(id) {
                    const tdPred = document.getElementById(`pred-${id}`);
                    tdPred.innerText = "Procesando...";
                    
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
                    if(response.ok) {
                        tdPred.innerHTML = `<strong>${data.sentiment_llm}</strong> (${data.confidence})`;
                    } else {
                        tdPred.innerText = "Error";
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
                    
                    btn.disabled = true;
                    btn.innerText = "Analizando...";
                    
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
                            box.className = "result-box active result-" + data.sentiment;
                            label.innerText = "Sentimiento: " + data.sentiment;
                            score.innerText = "Confianza: " + (data.confidence * 100).toFixed(2) + "%";
                        } else {
                            box.className = "result-box active";
                            label.innerText = "Error en el análisis";
                            score.innerText = "";
                        }
                    } catch (e) {
                        box.className = "result-box active";
                        label.innerText = "Error de conexión";
                        score.innerText = "";
                    } finally {
                        btn.disabled = false;
                        btn.innerText = "Analizar Sentimiento";
                    }
                }

                // Cargar datos al iniciar la página
                window.onload = cargarTweets;
            </script>
        </body>
    </html>
    """