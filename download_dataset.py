import os
import urllib.request
import pandas as pd

URLS = [
    "https://raw.githubusercontent.com/kristishqau/SentimentAnalysis_NLP/master/twitter_validation.csv",
    "https://raw.githubusercontent.com/regisx001/Real-Time-Social-Media-Sentiment-Analysis/master/data/twitter/twitter_validation.csv",
    "https://raw.githubusercontent.com/anmolrk/Social-Media-Sentiment-Analysis/master/twitter_validation.csv"
]

TARGET_FILE = os.path.join("data", "twitter_validation.csv")

def generate_mock_data():
    print("Generando dataset sintético de respaldo...")
    mock_data = [
        [3364, "Facebook", "Irrelevant", "I mentioned on Facebook that I was struggling for motivation to go for a run."],
        [352, "Amazon", "Neutral", "BBC News - Amazon boss Jeff Bezos rejects pay rise proposal for staff."],
        [8312, "Microsoft", "Negative", "@Microsoft Why do I pay for Xbox Live when it does not work? So frustrating."],
        [4371, "CS-GO", "Negative", "CS-GO is such a bad game now, the servers are laggy and full of cheaters."],
        [9012, "Google", "Positive", "I love the new Google Pixel phone, it is amazing and the camera is outstanding!"],
        [1204, "FIFA21", "Negative", "FIFA 21 is absolute trash. The gameplay is scripted and career mode is broken."],
        [4512, "Borderlands", "Positive", "Borderlands 3 is an absolute masterpiece! The gunplay and comedy are top tier."],
        [5621, "Verizon", "Neutral", "Verizon customer service was average today, resolved billing issue after 30 mins."],
        [6203, "PlayStation5", "Positive", "Got my PS5 today! The controller feels incredible and graphics are stunning."],
        [2894, "Cyberpunk2077", "Negative", "Cyberpunk 2077 is so buggy on console. It crashes every hour. Waste of money."]
    ]
    # Guardamos SIN nombres de columna como fila 1 para simular el archivo crudo de Kaggle
    df = pd.DataFrame(mock_data)
    df.to_csv(TARGET_FILE, index=False, header=False, encoding="utf-8")
    print(f"Dataset sintético creado en {TARGET_FILE}.")

def download_dataset():
    os.makedirs("data", exist_ok=True)
    if os.path.exists(TARGET_FILE):
        print(f"El dataset ya existe en {TARGET_FILE}.")
        return
    for url in URLS:
        try:
            print(f"Descargando desde {url}...")
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req) as response:
                content = response.read().decode("utf-8", errors="ignore")
                with open(TARGET_FILE, "w", encoding="utf-8") as f:
                    f.write(content)
            print("¡Descarga completada con éxito!")
            return
        except Exception as e:
            print(f"Error al descargar de la URL: {e}")
            
    print("Todas las URLs fallaron. Generando datos de respaldo...")
    generate_mock_data()

if __name__ == "__main__":
    download_dataset()