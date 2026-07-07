import os
import pandas as pd
import pymysql

# MySQL connection settings
MYSQL_HOST = 'localhost'
MYSQL_PORT = 3308
MYSQL_USER = 'root'
MYSQL_PASSWORD = 'lasalle'
DB_NAME = 'db_sentimientos'
CSV_PATH = os.path.join("data", "twitter_validation.csv")

def run_migration():
    print("Connecting to MySQL...")
    # Connect without database first to create it
    connection = pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        cursorclass=pymysql.cursors.DictCursor
    )
    
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
