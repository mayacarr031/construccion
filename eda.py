"""
Script de Entrada Principal para Análisis Exploratorio de Datos (EDA)
Ejecuta la tubería modular definida en src/eda.py
"""

from src.eda import run_eda

if __name__ == "__main__":
    print("Ejecutando Análisis Exploratorio de Datos (EDA)...")
    df_clean, summary = run_eda("data/twitter_validation.csv", text_column="Tweet")
