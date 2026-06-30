from fastapi import FastAPI, Form, Response, Cookie, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from transformers import pipeline
import pandas as pd
import os
import bcrypt

app = FastAPI(title="StudioLumina - Servidor Inteligente")

# Montaje de estáticos y plantillas
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Carga perezosa/global del clasificador local
print("Cargando modelo DistilBERT de HuggingFace en memoria local...")
clasificador = pipeline("sentiment-analysis", model="distilbert-base-uncased-finetuned-sst-2-english")

class TweetInput(BaseModel):
    text: str

# Middleware de Seguridad Local mediante cookies
def obtener_usuario_actual(session_user: str = Cookie(None)):
    if not session_user or not session_user.endswith("@lasallistas.org.mx"):
        raise HTTPException(status_code=401, detail="No autorizado")
    return session_user

# --- RUTAS FRONTEND ---

# --- RUTAS FRONTEND (MÁXIMA COMPATIBILIDAD) ---

@app.get("/login", response_class=HTMLResponse)
def vista_login(request: Request, error: str = None):
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"error": error}
    )

@app.get("/", response_class=HTMLResponse)
def frontend(request: Request, session_user: str = Cookie(None)):
    if not session_user or not session_user.endswith("@lasallistas.org.mx"):
        return RedirectResponse(url="/login", status_code=303)
        
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"user": session_user}
    )

CONTRASENA_PLANA = "12345"
# Generamos el hash seguro que simula cómo estaría guardado en una base de datos
HASH_PROVISTO = bcrypt.hashpw(CONTRASENA_PLANA.encode('utf-8'), bcrypt.gensalt())


# --- LÓGICA DE CONTROL DE ACCESO ACTUALIZADA ---

@app.post("/login")
def procesar_login(email: str = Form(...), password: str = Form(...)):
    # 1. Validación estricta del dominio solicitado
    if not email.endswith("@lasallistas.org.mx"):
        return RedirectResponse(
            url="/login?error=Correo%20no%20valido.%20Debe%20ser%20@lasallistas.org.mx", 
            status_code=303
        )
    
    # 2. Validación segura de la contraseña mediante Bcrypt
    # Comparamos la contraseña enviada en el formulario contra el Hash seguro
    es_valida = bcrypt.checkpw(password.encode('utf-8'), HASH_PROVISTO)
    
    if es_valida:
        res = RedirectResponse(url="/", status_code=303)
        # Seteamos la cookie de sesión por 1 hora (3600 segundos)
        res.set_cookie(key="session_user", value=email, max_age=3600, httponly=True)
        return res
    else:
        # Si la contraseña es incorrecta, devolvemos el error a la plantilla
        return RedirectResponse(
            url="/login?error=Contraseña%20institucional%20incorrecta.", 
            status_code=303
        )

@app.get("/logout")
def cerrar_sesion():
    res = RedirectResponse(url="/login", status_code=303)
    res.delete_cookie("session_user")
    return res

# --- ENDPOINTS API (IA INFERENCIA) ---

@app.post("/predict")
def analizar_texto(input_data: TweetInput, usuario: str = Depends(obtener_usuario_actual)):
    prediction = clasificador(input_data.text[:512])[0]
    return {
        "text": input_data.text,
        "sentiment": prediction['label'],
        "confidence": round(prediction['score'], 4)
    }

@app.get("/api/dataset")
def get_dataset_comparacion(usuario: str = Depends(obtener_usuario_actual)):
    dataset_path = os.path.join("data", "twitter_validation.csv")
    if not os.path.exists(dataset_path):
        raise HTTPException(status_code=404, detail="Dataset no encontrado. Corre primero download_dataset.py")

    columnas = ['ID', 'Entity', 'Sentiment', 'Tweet']
    # Leemos mapeando directamente las columnas sin importar si el archivo tiene cabecera o no
    df = pd.read_csv(dataset_path, names=columnas, header=None, encoding='utf-8', on_bad_lines='skip').dropna().head(20)

    resultados = []
    for _, row in df.iterrows():
        tweet_text = str(row['Tweet'])[:512]
        pred = clasificador(tweet_text)[0]
        resultados.append({
            "entity":  str(row['Entity']),
            "real":    str(row['Sentiment']),
            "pred":    pred['label'],
            "confidence": round(pred['score'], 4),
            "tweet":   str(row['Tweet'])[:200]
        })
    return resultados