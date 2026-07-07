# Proyecto: API de Análisis de Sentimientos con MySQL

Aplicación web fullstack desarrollada con **FastAPI** + **MySQL** + **HuggingFace DistilBERT**, que permite analizar el sentimiento de tweets en inglés usando un modelo de inteligencia artificial ejecutado **de forma local**.

---

## 🚀 Funcionalidades

- 🔐 **Autenticación con sesión** — Acceso protegido por usuario y contraseña.
- 📊 **Panel de tweets desde MySQL** — Visualiza los primeros 20 tweets migrados de Kaggle.
- 🤖 **Análisis con LLM local** — Analiza el sentimiento de tweets directamente desde la base de datos y persiste el resultado.
- 🔍 **Analizador en vivo** — Escribe cualquier texto en inglés y obtén la clasificación de sentimiento al instante.

---

## 🛠 Requisitos

- Python 3.10+
- MySQL 8.0 corriendo localmente
- Git

---

## ⚙️ Instalación paso a paso

### 1. Clonar el repositorio

```bash
git clone https://github.com/mayacarr031/construccion.git
cd construccion
```

### 2. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 3. Configurar la base de datos MySQL

Asegúrate de tener MySQL corriendo. Luego ejecuta el script de migración para crear la base de datos y poblarla con los tweets de Kaggle:

```bash
python download_dataset.py   # Descarga el CSV si no existe
python migrate_data.py       # Crea la BD y migra los datos
```

> **Nota:** El script `migrate_data.py` se conecta con `host=localhost`, `user=root`, `password=password`, `port=3306`. Si tu configuración local es diferente, edita el archivo antes de correrlo.

### 4. Iniciar el servidor

```bash
uvicorn main:app --reload
```

### 5. Abrir en el navegador

```
http://127.0.0.1:8000
```

---

## 🔐 Credenciales de acceso

| Campo    | Valor   |
|----------|---------|
| Usuario  | `admin` |
| Contraseña | `12345` |

---

## 📡 Endpoints de la API

| Método | Ruta          | Descripción                                           |
|--------|---------------|-------------------------------------------------------|
| GET    | `/`           | Panel de control principal (requiere sesión)          |
| GET    | `/login`      | Página de inicio de sesión                            |
| POST   | `/login`      | Procesa el inicio de sesión                           |
| GET    | `/logout`     | Cierra la sesión                                      |
| GET    | `/tweets`     | Devuelve los primeros 20 tweets desde MySQL           |
| POST   | `/predict-db` | Analiza un tweet por ID y guarda la predicción en BD  |
| POST   | `/predict`    | Analiza texto libre (sin guardar en base de datos)    |

---

## 🗂 Estructura del proyecto

```
construccion/
├── main.py              # Backend FastAPI con endpoints y frontend embebido
├── migrate_data.py      # Script para crear la BD y migrar el CSV a MySQL
├── download_dataset.py  # Descarga el dataset de Kaggle (twitter_validation.csv)
├── prueba_dataset.py    # Script de prueba local con pandas + DistilBERT
├── requirements.txt     # Dependencias del proyecto
├── data/
│   └── twitter_validation.csv
├── static/
│   ├── css/styles.css
│   └── js/app.js
└── templates/
    ├── index.html
    └── login.html
```

---

## 🧠 Modelo utilizado

[`distilbert-base-uncased-finetuned-sst-2-english`](https://huggingface.co/distilbert/distilbert-base-uncased-finetuned-sst-2-english) de HuggingFace — modelo ligero de análisis de sentimientos, ejecutado **100% localmente** sin llamadas a APIs externas.
