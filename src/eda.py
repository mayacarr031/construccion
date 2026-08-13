"""
Modulo de Análisis Exploratorio de Datos (EDA) para Twitter Validation Dataset.
Diseñado de forma modular para reusabilidad en scripts y notebooks.
"""

import os
import pandas as pd

def load_data(file_path="data/twitter_validation.csv", column_names=None):
    """
    Carga el dataset CSV de Twitter utilizando pandas.
    
    Args:
        file_path (str): Ruta al archivo CSV.
        column_names (list): Nombres de las columnas si el CSV no tiene encabezado.
        
    Returns:
        pd.DataFrame: DataFrame cargado con pandas.
    """
    if column_names is None:
        column_names = ['ID', 'Entity', 'Sentiment', 'Tweet']
    
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"El archivo {file_path} no fue encontrado.")
        
    df = pd.read_csv(file_path, names=column_names)
    print(f"[+] Dataset cargado exitosamente: {df.shape[0]} filas, {df.shape[1]} columnas.")
    return df


def clean_data(df, text_column='Tweet'):
    """
    Realiza la limpieza del dataset eliminando filas con valores nulos en la columna de texto.
    
    Args:
        df (pd.DataFrame): DataFrame original.
        text_column (str): Nombre de la columna de texto a verificar.
        
    Returns:
        pd.DataFrame: DataFrame limpio sin nulos en la columna especificada.
    """
    initial_rows = len(df)
    null_count = df[text_column].isnull().sum()
    
    df_clean = df.dropna(subset=[text_column]).copy()
    final_rows = len(df_clean)
    
    print(f"[+] Limpieza realizada en columna '{text_column}':")
    print(f"    - Filas iniciales: {initial_rows}")
    print(f"    - Nulos eliminados: {null_count}")
    print(f"    - Filas finales: {final_rows}")
    
    return df_clean


def generate_summary(df, text_column='Tweet'):
    """
    Genera un resumen estadístico básico y descriptivo del dataset.
    
    Args:
        df (pd.DataFrame): DataFrame limpio.
        text_column (str): Columna principal de contenido de texto.
        
    Returns:
        dict: Diccionario con métricas y resúmenes estadísticos.
    """
    summary = {}
    
    # Dimensiones y tipos de datos
    summary['dimensions'] = df.shape
    summary['columns'] = list(df.columns)
    summary['null_counts'] = df.isnull().sum().to_dict()
    
    # Resumen descriptivo general de pandas
    summary['general_describe'] = df.describe(include='all')
    
    # Distribución de Sentimiento
    if 'Sentiment' in df.columns:
        summary['sentiment_counts'] = df['Sentiment'].value_counts()
        summary['sentiment_percentages'] = (df['Sentiment'].value_counts(normalize=True) * 100).round(2)
        
    # Distribución por Entidades
    if 'Entity' in df.columns:
        summary['entity_counts'] = df['Entity'].value_counts()
        summary['total_entities'] = df['Entity'].nunique()
        
    # Métricas estadísticas de longitud de texto
    if text_column in df.columns:
        text_series = df[text_column].astype(str)
        char_lengths = text_series.str.len()
        word_counts = text_series.str.split().str.len()
        
        summary['text_stats'] = {
            'char_length': {
                'promedio': round(char_lengths.mean(), 2),
                'mediana': round(char_lengths.median(), 2),
                'desviacion_std': round(char_lengths.std(), 2),
                'min': char_lengths.min(),
                'max': char_lengths.max()
            },
            'word_count': {
                'promedio': round(word_counts.mean(), 2),
                'mediana': round(word_counts.median(), 2),
                'desviacion_std': round(word_counts.std(), 2),
                'min': word_counts.min(),
                'max': word_counts.max()
            }
        }
        
    return summary


def print_eda_report(summary):
    """
    Imprime en consola el reporte estadístico en un formato estructurado.
    
    Args:
        summary (dict): Diccionario generado por generate_summary.
    """
    print("=" * 65)
    print("           RESUMEN ESTADÍSTICO EXPLORATORIO (EDA)")
    print("=" * 65)
    print(f" Dimensiones: {summary['dimensions'][0]} filas x {summary['dimensions'][1]} columnas")
    print(f" Columnas: {', '.join(summary['columns'])}")
    
    print("\n--- Conteo de Valores Nulos ---")
    for col, count in summary['null_counts'].items():
        print(f"  - {col}: {count} nulos")
        
    if 'sentiment_counts' in summary:
        print("\n--- Distribución de Sentimientos ---")
        for label, count in summary['sentiment_counts'].items():
            pct = summary['sentiment_percentages'][label]
            print(f"  - {label:<12}: {count:>4} tweets ({pct:>5.2f}%)")
            
    if 'total_entities' in summary:
        print(f"\n--- Total de Entidades Únicas: {summary['total_entities']} ---")
        print(" Top 5 Entidades más frecuentes:")
        for entity, count in summary['entity_counts'].head(5).items():
            print(f"  - {entity:<25}: {count} tweets")
            
    if 'text_stats' in summary:
        ts = summary['text_stats']
        print("\n--- Métricas de Texto (Caracteres y Palabras) ---")
        print(f" Longitud (Caracteres) -> Promedio: {ts['char_length']['promedio']}, Mediana: {ts['char_length']['mediana']}, Min: {ts['char_length']['min']}, Max: {ts['char_length']['max']}")
        print(f" Conteo de Palabras     -> Promedio: {ts['word_count']['promedio']}, Mediana: {ts['word_count']['mediana']}, Min: {ts['word_count']['min']}, Max: {ts['word_count']['max']}")
    print("=" * 65)


def run_eda(file_path="data/twitter_validation.csv", text_column='Tweet'):
    """
    Orquestador principal para ejecutar la tubería completa de EDA.
    
    Returns:
        tuple: (df_clean, summary)
    """
    df = load_data(file_path)
    df_clean = clean_data(df, text_column=text_column)
    summary = generate_summary(df_clean, text_column=text_column)
    print_eda_report(summary)
    return df_clean, summary


if __name__ == "__main__":
    run_eda()
