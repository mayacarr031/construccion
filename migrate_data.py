import os
import pandas as pd
import pymysql

# Cargar automáticamente variables de .env asegurando la ruta absoluta
def _load_env_file(filepath=None):
    if filepath is None:
        filepath = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip("'\"")
                if k:
                    os.environ[k] = v

_load_env_file()

DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("DB_PORT", 3308))
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "lasalle")
DB_NAME = os.getenv("DB_NAME", "db_sentimientos")
CSV_PATH = os.path.join("data", "twitter_validation.csv")

def connect_to_db():
    # 1. Intentar conectar directamente a la base de datos configurada
    try:
        return pymysql.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            connect_timeout=5,
            cursorclass=pymysql.cursors.DictCursor
        ), True
    except Exception as e1:
        # 2. Si la base de datos no existe aún, intentar conectar sin base para crearla
        try:
            conn = pymysql.connect(
                host=DB_HOST,
                port=DB_PORT,
                user=DB_USER,
                password=DB_PASSWORD,
                connect_timeout=5,
                cursorclass=pymysql.cursors.DictCursor
            )
            return conn, False
        except Exception as e2:
            raise Exception(f"No se pudo conectar a MariaDB en {DB_HOST}:{DB_PORT} (Usuario: {DB_USER}). Detalle: {e2}")

def run_migration():
    print("=" * 60)
    print("[INFO] INICIANDO MIGRACION Y CARGA DE DATOS A MARIADB REMOTA")
    print("=" * 60)
    print(f"Host:     {DB_HOST}")
    print(f"Puerto:   {DB_PORT}")
    print(f"Usuario:  {DB_USER}")
    print(f"Base:     {DB_NAME}")
    print("=" * 60)

    try:
        connection, db_already_selected = connect_to_db()
        print("[OK] Conexion establecida con el servidor MariaDB.")
    except Exception as e:
        print(f"[ERROR] Error de conexion: {e}")
        return

    try:
        with connection.cursor() as cursor:
            # 1. Crear base de datos si no estaba seleccionada
            if not db_already_selected:
                cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME}")
                print(f"[OK] Base de datos '{DB_NAME}' verificada/creada.")
                connection.select_db(DB_NAME)
            else:
                print(f"[OK] Conectado a la base de datos '{DB_NAME}'.")

            # 2. Crear tabla tweets
            create_table_sql = """
            CREATE TABLE IF NOT EXISTS tweets (
                id_tweet INT PRIMARY KEY,
                entity VARCHAR(255) NOT NULL,
                sentiment_real VARCHAR(50) NOT NULL,
                tweet_text TEXT NOT NULL,
                sentiment_prediction VARCHAR(50) NULL,
                confidence FLOAT NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
            cursor.execute(create_table_sql)
            print("[OK] Tabla 'tweets' verificada/creada.")

            # 3. Leer CSV e importar (o descargar si no existe)
            if not os.path.exists(CSV_PATH):
                print(f"[INFO] Archivo CSV no encontrado en '{CSV_PATH}'. Descargando automáticamente...")
                try:
                    from download_dataset import download_dataset
                    download_dataset()
                except Exception as e_dl:
                    print(f"[ERROR] No se pudo descargar el dataset: {e_dl}")
                    return

            if not os.path.exists(CSV_PATH):
                print(f"[ERROR] Archivo CSV no encontrado en '{CSV_PATH}'.")
                return

            print(f"[INFO] Leyendo dataset desde '{CSV_PATH}'...")
            columnas = ['ID', 'Entity', 'Sentiment', 'Tweet']
            df = pd.read_csv(CSV_PATH, names=columnas, header=None, encoding='utf-8', on_bad_lines='skip').dropna()

            print(f"[INFO] Registros encontrados en CSV: {len(df)}")
            print("[INFO] Insertando registros en MariaDB remota...")

            insert_sql = """
            INSERT INTO tweets (id_tweet, entity, sentiment_real, tweet_text)
            VALUES (%s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE 
                entity = VALUES(entity), 
                sentiment_real = VALUES(sentiment_real), 
                tweet_text = VALUES(tweet_text)
            """

            records = []
            for _, row in df.iterrows():
                records.append((
                    int(row['ID']),
                    str(row['Entity']),
                    str(row['Sentiment']),
                    str(row['Tweet'])
                ))

            cursor.executemany(insert_sql, records)
            connection.commit()
            print(f"[SUCCESS] Migracion exitosa! Se cargaron {len(records)} registros en MariaDB remota.")

            # Contar total actual en tabla
            cursor.execute("SELECT COUNT(*) AS total FROM tweets;")
            total = cursor.fetchone()
            print(f"[INFO] Total de tweets en la base de datos: {total['total']}")

    except Exception as e:
        print(f"[ERROR] Error durante la migracion: {e}")
    finally:
        connection.close()
        print("=" * 60)

if __name__ == "__main__":
    run_migration()
