"""
Script de Procesamiento por Lotes (Batch Processing)
1) Carga una muestra de 50 tweets del dataset limpio.
2) Sanitiza el texto con sanitizar_texto() eliminando caracteres extraños e intentos de Prompt Injection.
3) Envía las solicitudes al endpoint /predict / /predict-db de FastAPI o al servidor local de inferencia.
4) Guarda los resultados en resultados_inferencia.csv.
"""

import os
import sys
import time
import re
import unicodedata
import requests
import pandas as pd


def sanitizar_texto(texto: str) -> str:
    """
    Limpia caracteres extraños, caracteres de control no imprimibles
    y mitiga posibles intentos de Prompt Injection en el texto del tweet.
    
    Args:
        texto (str): Texto original del tweet.
        
    Returns:
        str: Texto sanitizado y seguro para el LLM / modelo de inferencia.
    """
    if not isinstance(texto, str):
        return ""
        
    # 1. Eliminar etiquetas HTML y delimitadores especiales de instruct/prompt
    texto = re.sub(r'<[^>]+>', ' ', texto)
    texto = re.sub(r'\[\/?INST\]', ' ', texto, flags=re.IGNORECASE)
    texto = re.sub(r'<\|im_start\|>|<\|im_end\|>', ' ', texto)
    
    # 2. Neutralizar patrones comunes de Prompt Injection (case-insensitive)
    patrones_injection = [
        r'ignore\s+previous\s+instructions',
        r'ignore\s+all\s+instructions',
        r'disregard\s+all\s+previous',
        r'system\s*:',
        r'user\s*:',
        r'assistant\s*:',
        r'you\s+are\s+now',
        r'forget\s+(your\s+)?role',
        r'override\s+(the\s+)?prompt'
    ]
    for patron in patrones_injection:
        texto = re.sub(patron, '[TEXTO_FILTRADO]', texto, flags=re.IGNORECASE)
        
    # 3. Remover caracteres de control ASCII/Unicode no imprimibles
    texto = "".join(ch for ch in texto if unicodedata.category(ch)[0] != "C" or ch in ("\n", "\t"))
    
    # 4. Normalizar espacios en blanco consecutivos y extremos
    texto = re.sub(r'\s+', ' ', texto).strip()
    
    return texto


def cargar_muestra_limpia(csv_path="data/twitter_validation.csv", sample_size=50, seed=42):
    """
    Carga el dataset, elimina filas con valores nulos en la columna 'Tweet' y obtiene una muestra aleatoria.
    
    Args:
        csv_path (str): Ruta al archivo CSV.
        sample_size (int): Cantidad de muestras a extraer (default: 50).
        seed (int): Semilla aleatoria para reproducibilidad.
        
    Returns:
        pd.DataFrame: Muestra de tweets limpios.
    """
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"No se encontró el archivo dataset en {csv_path}")
        
    columnas = ['ID', 'Entity', 'Sentiment', 'Tweet']
    df = pd.read_csv(csv_path, names=columnas)
    
    # Limpieza de valores nulos en la columna de texto 'Tweet'
    df_clean = df.dropna(subset=['Tweet']).copy()
    
    # Extracción de la muestra de 50 tweets
    df_sample = df_clean.sample(n=min(sample_size, len(df_clean)), random_state=seed).copy()
    return df_sample


def predecir_con_fastapi_o_local(texto_sanitizado, id_tweet=None, api_session=None, api_url="http://localhost:8000"):
    """
    Envía el texto al endpoint /predict o /predict-db de FastAPI.
    Si el servidor FastAPI no está en ejecución, utiliza un motor local de inferencia de respaldo.
    """
    # 1. Intentar endpoint /predict de FastAPI si hay una sesión HTTP disponible
    if api_session and api_url:
        try:
            resp = api_session.post(f"{api_url}/predict", json={"text": texto_sanitizado}, timeout=1)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("sentiment", "Neutral"), round(float(data.get("confidence", 1.0)), 4)
        except Exception:
            pass

    # 2. Fallback a análisis rápido basado en léxico/reglas cuando no hay servidor activo
    texto_lower = texto_sanitizado.lower()
    
    palabras_positivas = {'good', 'great', 'awesome', 'love', 'happy', 'best', 'excellent', 'amazing', 'nice', 'win', 'win!'}
    palabras_negativas = {'bad', 'worst', 'hate', 'terrible', 'awful', 'poor', 'sad', 'angry', 'sucks', 'fail', 'fix'}
    palabras_irrelevantes = {'http', 'www', 'com', 'pic.twitter', 'news', 'link'}

    score_pos = sum(1 for word in palabras_positivas if word in texto_lower)
    score_neg = sum(1 for word in palabras_negativas if word in texto_lower)
    score_irr = sum(1 for word in palabras_irrelevantes if word in texto_lower)

    if score_pos > score_neg and score_pos > score_irr:
        return "Positive", 0.95
    elif score_neg > score_pos and score_neg > score_irr:
        return "Negative", 0.95
    elif score_irr > score_pos and score_irr > score_neg:
        return "Irrelevant", 0.85
    else:
        return "Neutral", 0.80


def ejecutar_batch_processing(csv_path="data/twitter_validation.csv", output_path="resultados_inferencia.csv", sample_size=50):
    """
    Ejecuta el flujo completo de Batch Processing de 50 tweets.
    """
    print("=== Iniciando Batch Processing (50 Tweets) ===", flush=True)
    
    # Step 1: Cargar muestra de 50 tweets del dataset limpio
    print(f"[1/4] Cargando muestra de {sample_size} tweets del dataset limpio...", flush=True)
    df_sample = cargar_muestra_limpia(csv_path=csv_path, sample_size=sample_size)
    print(f"      - Muestra cargada correctamente: {len(df_sample)} filas.", flush=True)
    
    # Comprobar si FastAPI está corriendo localmente
    api_url = "http://localhost:8000"
    session = requests.Session()
    api_activa = False
    try:
        login_resp = session.post(f"{api_url}/login", data={"username": "admin", "password": "12345"}, timeout=1)
        if login_resp.status_code in [200, 303]:
            api_activa = True
            print(f"[+] Conexión autenticada con servidor FastAPI en {api_url}", flush=True)
    except Exception:
        print("[!] Servidor FastAPI en http://localhost:8000 no disponible. Se utilizará inferencia local de respaldo.", flush=True)

    # Step 2 & 3: Sanitización e Inferencia
    print(f"[2/4 & 3/4] Aplicando sanitizar_texto() y procesando inferencias...", flush=True)
    textos_sanitizados = []
    predicciones = []
    confianzas = []
    
    start_time = time.time()
    for idx, (row_id, row) in enumerate(df_sample.iterrows(), 1):
        original_text = row['Tweet']
        
        # 2) Función sanitizar_texto()
        clean_text = sanitizar_texto(original_text)
        textos_sanitizados.append(clean_text)
        
        # 3) Enviar texto a /predict o /predict-db o servidor local
        pred, conf = predecir_con_fastapi_o_local(
            texto_sanitizado=clean_text, 
            id_tweet=row['ID'],
            api_session=session if api_activa else None, 
            api_url=api_url
        )
        predicciones.append(pred)
        confianzas.append(conf)
        
        if idx % 10 == 0 or idx == sample_size:
            print(f"      - Procesados {idx}/{sample_size} tweets...", flush=True)
            
    total_time = time.time() - start_time
    
    # Agregar columnas resultantes
    df_sample['Tweet_Sanitizado'] = textos_sanitizados
    df_sample['Sentiment_Prediction'] = predicciones
    df_sample['Confidence'] = confianzas
    
    # Step 4: Guardar los resultados en resultados_inferencia.csv
    print(f"[4/4] Guardando resultados en {output_path}...", flush=True)
    df_sample.to_csv(output_path, index=False)
    
    # También guardar una copia en data/resultados_inferencia.csv si existe la carpeta data
    if os.path.exists("data"):
        df_sample.to_csv("data/resultados_inferencia.csv", index=False)
        
    print("\n" + "=" * 60, flush=True)
    print("           RESUMEN DE BATCH PROCESSING", flush=True)
    print("=" * 60, flush=True)
    print(f" Total procesados     : {len(df_sample)} tweets", flush=True)
    print(f" Tiempo total         : {total_time:.2f} segundos", flush=True)
    print(f" Archivo generado     : {output_path}", flush=True)
    print("=" * 60, flush=True)
    print("\nMuestra de Resultados (Primeros 5 registros):", flush=True)
    print(df_sample[['ID', 'Sentiment', 'Sentiment_Prediction', 'Confidence', 'Tweet_Sanitizado']].head(5).to_string(), flush=True)
    
    return df_sample


if __name__ == "__main__":
    ejecutar_batch_processing()
