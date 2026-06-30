import pandas as pd
from transformers import pipeline

# 1. Configuración del pipeline (Descarga inicial local)
clasificador_local = pipeline("sentiment-analysis", model="distilbert-base-uncased-finetuned-sst-2-english")

# 2. Carga y preparación del Dataset de Kaggle
columnas = ['ID', 'Entity', 'Sentiment', 'Tweet']
df_val = pd.read_csv('data/twitter_validation.csv', names=columnas).dropna().head(20)

def predecir_sentimiento_local(texto):
    # El modelo tiene un límite de tokens, truncamos a 512 caracteres por seguridad
    resultado = clasificador_local(texto[:512]) 
    return resultado[0]['label']

# 3. Comparativa de etiquetas (Real vs Local)
df_val['Prediccion_Local'] = df_val['Tweet'].apply(predecir_sentimiento_local)
print(df_val[['Sentiment', 'Prediccion_Local']])