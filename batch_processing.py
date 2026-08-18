"""
Batch Processing - Analisis de Sentimientos con FastAPI + LM Studio + MySQL

Flujo:
1. Carga una muestra reproducible del dataset de Kaggle.
2. Limpia y sanitiza el texto.
3. Se autentica en FastAPI.
4. Envia el texto sanitizado al endpoint /predict.
5. FastAPI envia el texto a LM Studio.
6. LM Studio/Qwen devuelve:
   Positive, Negative, Neutral o Irrelevant.
7. La prediccion se guarda en MySQL.
8. Los resultados se guardan en resultados_inferencia.csv.

IMPORTANTE:
- No existe fallback por palabras.
- Si LM Studio/FastAPI falla, se registra el error.
- No se inventa un valor de "confianza".
"""

import os
import re
import time
import unicodedata

import pandas as pd
import pymysql
import requests

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


# =========================================================
# CONFIGURACION
# =========================================================

CSV_PATH = "data/twitter_validation.csv"
OUTPUT_PATH = "resultados_inferencia.csv"

# Empezamos con 5.
# Cuando confirmemos que funciona, cambiaremos a 100.
SAMPLE_SIZE = 5
RANDOM_SEED = 42

FASTAPI_URL = os.getenv("FASTAPI_URL", "http://127.0.0.1:8000")

# Configuracion actual de tu proyecto
FASTAPI_USER = os.getenv("FASTAPI_USER", "admin")
FASTAPI_PASSWORD = os.getenv("FASTAPI_PASSWORD", "12345")

# MySQL: XAMPP local (puerto 3306, sin contraseña)
# Configurable vía variables de entorno para otros entornos
MYSQL_HOST = os.getenv("DB_HOST", "127.0.0.1")
MYSQL_PORT = int(os.getenv("DB_PORT", 3306))
MYSQL_USER = os.getenv("DB_USER", "root")
MYSQL_PASSWORD = os.getenv("DB_PASSWORD", "")
MYSQL_DATABASE = os.getenv("DB_NAME", "db_sentimientos")


# =========================================================
# SANITIZACION
# =========================================================

def sanitizar_texto(texto: str) -> str:
    """
    Limpia el texto antes de enviarlo al LLM.

    Medidas:
    - Elimina etiquetas HTML.
    - Elimina delimitadores especiales de modelos.
    - Neutraliza patrones comunes de Prompt Injection.
    - Elimina caracteres de control.
    - Normaliza espacios.
    - Limita la longitud.
    """

    if not isinstance(texto, str):
        return ""

    # Eliminar etiquetas HTML
    texto = re.sub(r"<[^>]+>", " ", texto)

    # Eliminar delimitadores especiales comunes
    texto = re.sub(
        r"\[\/?INST\]",
        " ",
        texto,
        flags=re.IGNORECASE
    )

    texto = re.sub(
        r"<\|im_start\|>|<\|im_end\|>",
        " ",
        texto,
        flags=re.IGNORECASE
    )

    # Patrones comunes de Prompt Injection
    patrones_injection = [
        r"ignore\s+previous\s+instructions",
        r"ignore\s+all\s+instructions",
        r"disregard\s+all\s+previous",
        r"system\s*:",
        r"user\s*:",
        r"assistant\s*:",
        r"you\s+are\s+now",
        r"forget\s+(your\s+)?role",
        r"override\s+(the\s+)?prompt",
    ]

    for patron in patrones_injection:
        texto = re.sub(
            patron,
            "[TEXTO_FILTRADO]",
            texto,
            flags=re.IGNORECASE
        )

    # Eliminar caracteres de control
    texto = "".join(
        ch
        for ch in texto
        if unicodedata.category(ch)[0] != "C"
        or ch in ("\n", "\t")
    )

    # Normalizar espacios
    texto = re.sub(r"\s+", " ", texto).strip()

    # Limitar longitud enviada al modelo
    texto = texto[:1500]

    return texto


# =========================================================
# CARGA DEL DATASET
# =========================================================

def cargar_muestra_limpia(
    csv_path=CSV_PATH,
    sample_size=SAMPLE_SIZE,
    seed=RANDOM_SEED
):
    """
    Carga twitter_validation.csv,
    elimina textos nulos/vacios y toma una muestra reproducible.
    """

    if not os.path.exists(csv_path):
        raise FileNotFoundError(
            f"No se encontro el dataset en: {csv_path}"
        )

    columnas = [
        "ID",
        "Entity",
        "Sentiment",
        "Tweet"
    ]

    df = pd.read_csv(
        csv_path,
        names=columnas,
        header=None,
        encoding="utf-8",
        on_bad_lines="skip"
    )

    # Eliminar valores nulos
    df = df.dropna(subset=["Tweet"]).copy()

    # Convertir texto a string y limpiar espacios
    df["Tweet"] = df["Tweet"].astype(str).str.strip()

    # Eliminar tweets vacios
    df = df[df["Tweet"] != ""].copy()

    # Asegurar ID numerico
    df["ID"] = pd.to_numeric(
        df["ID"],
        errors="coerce"
    )

    df = df.dropna(subset=["ID"]).copy()
    df["ID"] = df["ID"].astype(int)

    # Muestra reproducible
    n = min(sample_size, len(df))

    muestra = df.sample(
        n=n,
        random_state=seed
    ).copy()

    return muestra


# =========================================================
# FASTAPI
# =========================================================

def crear_sesion_fastapi():
    """
    Inicia sesion en FastAPI y conserva la cookie.
    """

    session = requests.Session()

    try:
        response = session.post(
            f"{FASTAPI_URL}/login",
            data={
                "username": FASTAPI_USER,
                "password": FASTAPI_PASSWORD
            },
            timeout=10,
            allow_redirects=False
        )

        if response.status_code not in (200, 303):
            raise RuntimeError(
                f"Login FastAPI fallo. "
                f"HTTP {response.status_code}"
            )

        print(
            f"[OK] Autenticacion FastAPI correcta: {FASTAPI_URL}"
        )

        return session

    except requests.RequestException as error:
        raise RuntimeError(
            f"No fue posible conectar con FastAPI: {error}"
        )


def predecir_con_fastapi(
    texto_sanitizado: str,
    session: requests.Session
):
    """
    Envia texto sanitizado a FastAPI.

    FastAPI se comunica con LM Studio
    mediante el endpoint /predict.
    """

    response = session.post(
        f"{FASTAPI_URL}/predict",
        json={
            "text": texto_sanitizado
        },
        timeout=120
    )

    response.raise_for_status()

    data = response.json()

    sentimiento = data.get("sentiment")

    etiquetas_validas = {
        "Positive",
        "Negative",
        "Neutral",
        "Irrelevant"
    }

    if sentimiento not in etiquetas_validas:
        raise ValueError(
            f"FastAPI devolvio una etiqueta invalida: "
            f"{sentimiento}"
        )

    return sentimiento


# =========================================================
# MYSQL
# =========================================================

def conectar_mysql():
    """
    Conexión directa y exclusiva al contenedor de MariaDB.
    """
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
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=False,
            connect_timeout=5
        )
    except Exception as e:
        # Fallback si se ejecuta dentro de la red Docker interna
        try:
            return pymysql.connect(
                host="mariadb",
                port=3306,
                user=user,
                password=password,
                database=database,
                cursorclass=pymysql.cursors.DictCursor,
                autocommit=False,
                connect_timeout=3
            )
        except Exception:
            raise Exception(f"No se pudo conectar al contenedor MariaDB en {host}:{port} ({e}).")


def guardar_prediccion_mysql(
    connection,
    id_tweet: int,
    sentimiento: str
):
    """
    Guarda la prediccion generada por LM Studio en MySQL.

    No guarda una confianza falsa.
    La columna confidence queda NULL.
    """

    sql = """
        UPDATE tweets
        SET
            sentiment_prediction = %s,
            confidence = NULL
        WHERE id_tweet = %s
    """

    with connection.cursor() as cursor:

        cursor.execute(
            sql,
            (
                sentimiento,
                int(id_tweet)
            )
        )

    connection.commit()


# =========================================================
# BATCH PROCESSING
# =========================================================

def ejecutar_batch_processing(
    csv_path=CSV_PATH,
    output_path=OUTPUT_PATH,
    sample_size=SAMPLE_SIZE
):
    """
    Ejecuta el Batch Processing completo.
    """

    print()
    print("=" * 65)
    print(" BATCH PROCESSING - FASTAPI + LM STUDIO + MYSQL")
    print("=" * 65)

    # -----------------------------------------------------
    # 1. Dataset
    # -----------------------------------------------------

    print(
        f"\n[1/5] Cargando muestra de "
        f"{sample_size} tweets..."
    )

    df_sample = cargar_muestra_limpia(
        csv_path=csv_path,
        sample_size=sample_size
    )

    print(
        f"[OK] Tweets cargados: "
        f"{len(df_sample)}"
    )

    # -----------------------------------------------------
    # 2. FastAPI
    # -----------------------------------------------------

    print(
        "\n[2/5] Conectando con FastAPI..."
    )

    session = crear_sesion_fastapi()

    # -----------------------------------------------------
    # 3. MySQL
    # -----------------------------------------------------

    print(
        "\n[3/5] Conectando con MySQL..."
    )

    connection = conectar_mysql()

    print(
        f"[OK] MySQL conectado en "
        f"{MYSQL_HOST}:{MYSQL_PORT}"
    )

    # -----------------------------------------------------
    # Listas de resultados
    # -----------------------------------------------------

    textos_sanitizados = []
    predicciones = []
    tiempos = []
    estados = []
    errores = []

    inicio_batch = time.time()

    # -----------------------------------------------------
    # 4. Inferencias
    # -----------------------------------------------------

    print(
        "\n[4/5] Ejecutando inferencias..."
    )

    try:

        for numero, (_, row) in enumerate(
            df_sample.iterrows(),
            start=1
        ):

            id_tweet = int(row["ID"])
            texto_original = row["Tweet"]

            texto_sanitizado = sanitizar_texto(
                texto_original
            )

            textos_sanitizados.append(
                texto_sanitizado
            )

            print()
            print(
                f"[{numero}/{len(df_sample)}] "
                f"Tweet ID {id_tweet}"
            )

            inicio_inferencia = time.time()

            try:

                # -----------------------------------------
                # FastAPI -> LM Studio
                # -----------------------------------------

                prediccion = predecir_con_fastapi(
                    texto_sanitizado,
                    session
                )

                duracion = (
                    time.time()
                    - inicio_inferencia
                )

                # -----------------------------------------
                # Persistencia MySQL
                # -----------------------------------------

                guardar_prediccion_mysql(
                    connection,
                    id_tweet,
                    prediccion
                )

                predicciones.append(
                    prediccion
                )

                tiempos.append(
                    round(duracion, 2)
                )

                estados.append(
                    "OK"
                )

                errores.append(
                    ""
                )

                print(
                    f"    Real       : "
                    f"{row['Sentiment']}"
                )

                print(
                    f"    Prediccion : "
                    f"{prediccion}"
                )

                print(
                    f"    Tiempo     : "
                    f"{duracion:.2f} s"
                )

                print(
                    "    MySQL       : "
                    "actualizado"
                )

            except Exception as error:

                duracion = (
                    time.time()
                    - inicio_inferencia
                )

                predicciones.append(
                    "ERROR"
                )

                tiempos.append(
                    round(duracion, 2)
                )

                estados.append(
                    "ERROR"
                )

                errores.append(
                    str(error)
                )

                print(
                    f"    [ERROR] {error}"
                )

    finally:

        connection.close()

    # -----------------------------------------------------
    # Agregar resultados al DataFrame
    # -----------------------------------------------------

    df_sample[
        "Tweet_Sanitizado"
    ] = textos_sanitizados

    df_sample[
        "predicted_sentiment"
    ] = predicciones

    df_sample[
        "inference_time_seconds"
    ] = tiempos

    df_sample[
        "status"
    ] = estados

    df_sample[
        "error"
    ] = errores

    # -----------------------------------------------------
    # 5. Guardar CSV
    # -----------------------------------------------------

    print(
        f"\n[5/5] Guardando resultados en "
        f"{output_path}..."
    )

    df_sample.to_csv(
        output_path,
        index=False,
        encoding="utf-8-sig"
    )

    # Copia adicional dentro de data/
    if os.path.isdir("data"):

        df_sample.to_csv(
            "data/resultados_inferencia.csv",
            index=False,
            encoding="utf-8-sig"
        )

    tiempo_total = (
        time.time()
        - inicio_batch
    )

    # =====================================================
    # EVALUACION BASICA
    # =====================================================

    exitosos = df_sample[
        df_sample["status"] == "OK"
    ].copy()

    if not exitosos.empty:

        correctos = (
            exitosos["Sentiment"]
            == exitosos["predicted_sentiment"]
        ).sum()

        accuracy = (
            correctos
            / len(exitosos)
        )

    else:

        correctos = 0
        accuracy = 0.0

    # =====================================================
    # RESUMEN
    # =====================================================

    print()
    print("=" * 65)
    print(" RESUMEN DEL BATCH")
    print("=" * 65)

    print(
        f"Tweets seleccionados : "
        f"{len(df_sample)}"
    )

    print(
        f"Inferencias exitosas : "
        f"{len(exitosos)}"
    )

    print(
        f"Errores              : "
        f"{len(df_sample) - len(exitosos)}"
    )

    print(
        f"Predicciones correctas: "
        f"{correctos}"
    )

    print(
        f"Accuracy             : "
        f"{accuracy * 100:.2f}%"
    )

    print(
        f"Tiempo total         : "
        f"{tiempo_total:.2f} segundos"
    )

    if len(exitosos) > 0:

        print(
            f"Tiempo promedio      : "
            f"{exitosos['inference_time_seconds'].mean():.2f} "
            f"segundos/tweet"
        )

    print(
        f"Archivo generado     : "
        f"{output_path}"
    )

    print("=" * 65)

    # Mostrar resultados
    print()
    print("RESULTADOS:")
    print()

    columnas_resumen = [
        "ID",
        "Sentiment",
        "predicted_sentiment",
        "inference_time_seconds",
        "status"
    ]

    print(
        df_sample[
            columnas_resumen
        ].to_string(
            index=False
        )
    )

    print()

    return df_sample


# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":

    ejecutar_batch_processing()