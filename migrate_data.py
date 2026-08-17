import os
import pandas as pd
import pymysql

# Lista de credenciales a probar en orden
DB_CONFIGS = [
    # 1. XAMPP por defecto (Puerto 3306, sin clave) — configuración principal
    {"host": "127.0.0.1", "port": 3306, "user": "root", "password": "", "connect_timeout": 2},
    # 2. Contenedor Docker / MariaDB local (Puerto 3308, clave lasalle)
    {"host": "127.0.0.1", "port": 3308, "user": "root", "password": "lasalle", "connect_timeout": 2},
    # 3. Tarea escolar estándar (Puerto 3306, clave password)
    {"host": "127.0.0.1", "port": 3306, "user": "root", "password": "password", "connect_timeout": 2},
    # 4. Entorno local (Puerto 3306, clave lasalle)
    {"host": "127.0.0.1", "port": 3306, "user": "root", "password": "lasalle", "connect_timeout": 2},
]
DB_NAME = os.getenv("DB_NAME", 'db_sentimientos')
CSV_PATH = os.path.join("data", "twitter_validation.csv")

def connect_with_fallbacks():
    # Si se definen variables de entorno, priorizamos esa conexión directa (útil para contenedores remotos)
    env_host = os.getenv("DB_HOST")
    if env_host:
        env_port = int(os.getenv("DB_PORT", 3306))
        env_user = os.getenv("DB_USER", "root")
        env_password = os.getenv("DB_PASSWORD", "")
        try:
            return pymysql.connect(
                host=env_host,
                port=env_port,
                user=env_user,
                password=env_password,
                connect_timeout=3,
                cursorclass=pymysql.cursors.DictCursor
            )
        except Exception as e:
            print(f"Error al conectar con variables de entorno a {env_host}:{env_port}: {e}")
            # Continuamos con los fallbacks locales

    for config in DB_CONFIGS:
        try:
            return pymysql.connect(
                cursorclass=pymysql.cursors.DictCursor,
                **config
            )
        except Exception:
            continue
    raise Exception("No se pudo conectar a MySQL con ninguna de las configuraciones conocidas.")

def run_migration():
    print("Connecting to MySQL...")
    # Connect without database first to create it
    try:
        connection = connect_with_fallbacks()
    except Exception as e:
        print(f"Error: {e}")
        return
    
    try:
        with connection.cursor() as cursor:
            # 1. Create database
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME}")
            print(f"Database '{DB_NAME}' checked/created.")
            
        connection.select_db(DB_NAME)
        
        with connection.cursor() as cursor:
            # 2. Create table
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
            print("Table 'tweets' checked/created.")
            
            # 3. Read CSV and import
            if not os.path.exists(CSV_PATH):
                print(f"Error: CSV file not found at {CSV_PATH}. Please run download_dataset.py first.")
                return
            
            print(f"Reading dataset from {CSV_PATH}...")
            columnas = ['ID', 'Entity', 'Sentiment', 'Tweet']
            df = pd.read_csv(CSV_PATH, names=columnas, header=None, encoding='utf-8', on_bad_lines='skip').dropna()
            
            print(f"Found {len(df)} rows. Inserting into MySQL...")
            
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
            
            # Bulk insert for efficiency
            cursor.executemany(insert_sql, records)
            connection.commit()
            print(f"Successfully migrated {len(records)} records to MySQL database!")
            
    except Exception as e:
        print(f"Error during migration: {e}")
    finally:
        connection.close()

if __name__ == "__main__":
    run_migration()
