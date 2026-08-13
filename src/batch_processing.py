import os
import sys
import time
import pandas as pd
from openai import OpenAI

def clean_predicted_label(prediction):
    """
    Limpia y normaliza la respuesta del modelo para asegurar que
    coincida con una de las cuatro etiquetas requeridas.
    """
    clean_pred = prediction.strip().strip('"').strip("'").strip(".").strip().lower()
    
    # Mapeo a las etiquetas oficiales
    if "positive" in clean_pred:
        return "Positive"
    elif "negative" in clean_pred:
        return "Negative"
    elif "neutral" in clean_pred:
        return "Neutral"
    elif "irrelevant" in clean_pred:
        return "Irrelevant"
    else:
        # Fallback en caso de que devuelva algo inesperado
        return "Neutral"

def batch_process_sentiment(csv_path="data/twitter_validation.csv", output_path="data/resultados_inferencia.csv", sample_size=100, seed=42):
    print("=== Iniciando Procesamiento por Lotes (Batch Processing) ===")
    
    # 1. Cargar archivo CSV
    if not os.path.exists(csv_path):
        print(f"[X] Error: No se encontro el archivo {csv_path}. Asegurese de ejecutar download_dataset.py primero.")
        sys.exit(1)
        
    print(f"[+] Cargando dataset desde {csv_path}...")
    columnas = ['ID', 'Entity', 'Sentiment', 'Tweet']
    df = pd.read_csv(csv_path, names=columnas)
    
    # 2. Limpiar filas con textos nulos
    initial_len = len(df)
    df = df.dropna(subset=['Tweet'])
    clean_len = len(df)
    print(f"[+] Filas iniciales: {initial_len} -> Filas despues de limpiar nulos: {clean_len}")
    
    # 3. Muestra aleatoria controlada
    print(f"[+] Seleccionando muestra aleatoria de {sample_size} tweets (semilla/random_state={seed})...")
    df_sample = df.sample(n=sample_size, random_state=seed).copy()
    
    # 4. Inicializar cliente compatible con OpenAI para LM Studio
    client = OpenAI(
        base_url="http://localhost:1234/v1",
        api_key="lm-studio"
    )
    
    # System prompt optimizado
    system_prompt = (
        "You are an expert sentiment analysis AI. Analyze the sentiment of the user's tweet.\n"
        "You MUST respond with EXACTLY ONE of these labels: Positive, Negative, Neutral, Irrelevant.\n"
        "Do not write any introductory text, explanation, punctuation, or any other words. Just write the label."
    )
    
    predicted_sentiments = []
    
    start_time = time.time()
    
    print("\n[+] Iniciando inferencia en el servidor local de LM Studio...")
    for idx, (idx_row, row) in enumerate(df_sample.iterrows(), 1):
        tweet_text = row['Tweet']
        real_sentiment = row['Sentiment']
        
        try:
            # Enviar solicitud al servidor local de LM Studio
            response = client.chat.completions.create(
                model="local-model", # LM Studio usa el modelo cargado
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Tweet: {tweet_text}"}
                ],
                temperature=0.0, # Temperatura 0 para mayor determinismo y consistencia
                max_tokens=5
            )
            
            raw_reply = response.choices[0].message.content
            pred_sentiment = clean_predicted_label(raw_reply)
            
        except Exception as e:
            # En caso de error de conexión o API, mostramos la advertencia y asignamos Neutral
            print(f"\n[WARN] Error en el tweet {idx} (ID: {row['ID']}): {e}")
            pred_sentiment = "Neutral"
            
        predicted_sentiments.append(pred_sentiment)
        
        # Mostrar progreso
        if idx % 10 == 0 or idx == sample_size:
            print(f"    - Procesados: {idx}/{sample_size} tweets...")
            
    total_time = time.time() - start_time
    
    # 5. Agregar la nueva columna de predicciones
    df_sample['predicted_sentiment'] = predicted_sentiments
    
    # 6. Guardar el resultado procesado
    print(f"\n[+] Guardando resultados en {output_path}...")
    # Asegurar que el directorio de salida existe
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df_sample.to_csv(output_path, index=False)
    
    # 7. Resumen de ejecución y métricas de evaluación
    print("\n=== Resumen de la Inferencia por Lotes ===")
    print(f"[*] Tiempo total de ejecucion: {total_time:.2f} segundos")
    print(f"[*] Tiempo promedio por tweet: {total_time/sample_size:.3f} segundos")
    
    # Calcular precisión básica (Accuracy)
    # Comparamos ignorando mayúsculas y minúsculas para mayor robustez
    matches = df_sample['Sentiment'].str.strip().str.lower() == df_sample['predicted_sentiment'].str.strip().str.lower()
    correct_predictions = matches.sum()
    accuracy = (correct_predictions / sample_size) * 100
    
    print(f"[*] Tweets clasificados correctamente: {correct_predictions} / {sample_size}")
    print(f"[*] Precision basica (Accuracy): {accuracy:.2f}%")
    
    # Mostrar tabla comparativa básica (primeros 10 de la muestra)
    print("\nMuestra Comparativa (Primeros 10 registros):")
    print(df_sample[['Tweet', 'Sentiment', 'predicted_sentiment']].head(10).to_string())

if __name__ == "__main__":
    batch_process_sentiment()
