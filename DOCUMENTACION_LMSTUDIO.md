# Documentacion del Proyecto: Inferencia Local Segura con LM Studio

Este documento detalla la arquitectura de inferencia local offline, los procedimientos de instalacion, ejecucion de procesamiento por lotes, endurecimiento (hardening) del sistema operativo y las conclusiones del equipo para el proyecto **Desarrollo Seguro de IA Local**.

---

## 🛠️ 1. Setup de LM Studio (Tarjetas 1.1 y 1.3)

LM Studio es una aplicacion de escritorio que permite descargar y ejecutar Modelos de Lenguaje (LLMs) localmente en formato GGUF de manera offline.

### A. Pasos para Descargar e Instalar LM Studio
* **En Windows**:
  1. Descarga el instalador ejecutable (`.exe`) desde el sitio web oficial: [https://lmstudio.ai/](https://lmstudio.ai/).
  2. Ejecuta el instalador. Por defecto, se instalara en el directorio de usuario (`%USERPROFILE%\AppData\Local\Programs\lm-studio`), lo que cumple con el Principio de Menor Privilegio al no requerir permisos de Administrador para su ejecucion regular.
* **En Linux**:
  1. Descarga el archivo AppImage desde la pagina oficial.
  2. Dale permisos de ejecucion desde la terminal:
     ```bash
     chmod +x LM-Studio-*.AppImage
     ```
  3. Ejecuta la aplicacion:
     ```bash
     ./LM-Studio-*.AppImage
     ```

### B. Como descargar un Modelo Ligero en GGUF
1. Abre LM Studio.
2. Haz clic en el icono de **Búsqueda (Lupa)** en la barra lateral izquierda.
3. Escribe en el buscador el modelo deseado, por ejemplo:
   - `Phi-3-mini-4k-instruct` (Microsoft)
   - `Llama-3.2-1B-Instruct-GGUF` (Meta)
4. En el panel de resultados, veras una lista de creadores y cuantizaciones. Selecciona una cuantizacion recomendada (marcada con etiqueta verde de compatibilidad, por ejemplo, `Q4_K_M` o `Q8_0`).
5. Haz clic en **Download** para bajar el archivo GGUF directamente a tu carpeta de cache local.

### C. Iniciar el Servidor de Inferencia Local (Local Server)
1. Ve a la seccion **Local Server** (icono de puerto/servidor en la barra lateral izquierda).
2. En la parte superior de la pantalla, selecciona el modelo descargado en el menu desplegable: **"Select a model to load"**. Espera a que se cargue en la memoria RAM/VRAM de tu tarjeta grafica.
3. Configura los siguientes parametros en el panel derecho:
   - **Port**: `1234`
   - **CORS**: Activado (por defecto)
   - **Server Bind Address**: `127.0.0.1` (para restringir el acceso solo a tu computadora local).
4. Haz clic en **Start Server**.
5. El servidor estara expuesto en: `http://localhost:1234/v1` (compatible con el formato de API de OpenAI).

---

## 🚀 2. Procesamiento por Lotes y Evaluacion (Tarjeta 2.2)

Se ha creado un script especializado en `src/batch_processing.py` para procesar tweets por lotes de forma local.

### Arquitectura de Inferencia
El procesamiento por lotes utiliza la API compatible con OpenAI para comunicarse localmente con el servidor de LM Studio:

```
[twitter_validation.csv] 
         │
         ▼
[Pandas: Filtro Nulos & Sample (n=100, seed=42)]
         │
         ▼
[src/batch_processing.py]  ◄───(Inferencia Local Puerto 1234)───► [LM Studio Server]
         │
         ▼
[data/resultados_inferencia.csv] ──► [Calculo de Precision (Accuracy) y Tiempos]
```

### Ejecucion del Script de Procesamiento
1. Activa tu entorno virtual de Python:
   - **En Windows**:
     ```powershell
     .\venv\Scripts\activate
     ```
   - **En Linux**:
     ```bash
     source venv/bin/activate
     ```
2. Instala las dependencias necesarias de integracion:
   ```bash
   pip install -r requirements_lmstudio.txt
   ```
3. Ejecuta el script de prueba de conexion para validar que LM Studio este escuchando:
   ```bash
   python test_lmstudio_connection.py
   ```
4. Ejecuta el procesamiento por lotes:
   ```bash
   python src/batch_processing.py
   ```

### Optimizacion del System Prompt y Limpieza
El System Prompt configurado en el script es el siguiente:
> *You are an expert sentiment analysis AI. Analyze the sentiment of the user's tweet. You MUST respond with EXACTLY ONE of these labels: Positive, Negative, Neutral, Irrelevant. Do not write any introductory text, explanation, punctuation, or any other words. Just write the label.*

El script utiliza una funcion de limpieza determinista (`clean_predicted_label`) que procesa la respuesta del modelo, convirtiendola a minusculas y eliminando espacios y puntuacion, para luego mapearla de manera estricta a una de las 4 etiquetas: `Positive`, `Negative`, `Neutral`, `Irrelevant`.

---

## 🔒 3. Hardening del Sistema Operativo (Tarjeta 3.1)

Para garantizar la confidencialidad absoluta de los datos analizados, se configuran las siguientes directivas de hardening de seguridad en el sistema operativo local.

### A. Verificacion de Privilegios (Menor Privilegio)
Asegurate de que tanto LM Studio como Python se ejecutan bajo un usuario estandar del sistema sin privilegios de Administrador (root / admin).
* **En Windows (PowerShell)**:
  Ejecuta el siguiente comando para verificar si la sesion de PowerShell actual tiene privilegios de Administrador:
  ```powershell
  [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent() | Format-List
  ```
  Verifica que el resultado del rol de Administrador sea `False`.
* **En Linux**:
  Ejecuta `id` y verifica que el identificador de usuario (`uid`) sea diferente de 0.

### B. Reglas de Firewall (Aislamiento Offline Completo)
Para impedir fugas de datos hacia internet, crearemos reglas de Firewall saliente (Outbound Rules) para bloquear todo el trafico de red externa de los procesos de inferencia, permitiendo unicamente la comunicacion loopback (`127.0.0.1`).

* **En Windows (PowerShell como Administrador)**:
  Ejecuta estos comandos para crear las reglas de bloqueo:
  ```powershell
  # 1. Bloquear trafico saliente de LM Studio a Internet
  New-NetFirewallRule -DisplayName "Bloquear Inferencia LM Studio Externa" `
      -Direction Outbound `
      -Program "$env:USERPROFILE\AppData\Local\Programs\lm-studio\LM Studio.exe" `
      -Action Block `
      -Description "Bloquea todo el trafico de salida de LM Studio para garantizar privacidad 100% offline."

  # 2. Bloquear trafico saliente de Python a Internet (Usando la ruta de tu entorno virtual)
  New-NetFirewallRule -DisplayName "Bloquear Inferencia Python Venv Externa" `
      -Direction Outbound `
      -Program "C:\Users\Maya\Downloads\construccion\venv\Scripts\python.exe" `
      -Action Block `
      -Description "Bloquea el trafico de salida del entorno de Python durante la inferencia local."
  ```
  *Nota:* Las conexiones a `http://localhost:1234` o `127.0.0.1` seguiran funcionando, ya que el Firewall de Windows permite de forma nativa la comunicacion a la interfaz loopback.

* **En Linux (Mediante UFW / iptables)**:
  Si ejecutas en Linux, puedes bloquear la salida de red del usuario especifico que corre el servicio de inferencia usando `iptables`:
  ```bash
  # Bloquear todo el trafico saliente para el usuario 'inferencia-user' excepto a loopback (lo)
  sudo iptables -A OUTPUT -m owner --uid-owner inferencia-user -o lo -j ACCEPT
  sudo iptables -A OUTPUT -m owner --uid-owner inferencia-user -j REJECT
  ```

### C. Permisos de Archivos (ACL / chmod)
Restringir permisos de acceso local a las carpetas del proyecto y los modelos descargados para evitar modificaciones o lectura por parte de otros usuarios del mismo sistema.

* **En Windows (PowerShell)**:
  Establece permisos ACL restrictivos en el directorio del proyecto:
  ```powershell
  # Desactivar la herencia de permisos y copiar los actuales
  icacls "C:\Users\Maya\Downloads\construccion" /inheritance:d

  # Quitar permisos de lectura/escritura a los grupos "Todos" y "Usuarios"
  icacls "C:\Users\Maya\Downloads\construccion" /remove "Todos"
  icacls "C:\Users\Maya\Downloads\construccion" /remove "Usuarios"
  
  # Otorgar control total unicamente al propietario actual y a SYSTEM
  icacls "C:\Users\Maya\Downloads\construccion" /grant:r "${env:USERNAME}:(OI)(CI)F"
  icacls "C:\Users\Maya\Downloads\construccion" /grant:r "SYSTEM:(OI)(CI)F"
  ```
* **En Linux**:
  Aplica un chmod restrictivo recursivamente en el directorio del proyecto:
  ```bash
  chmod -R 700 /ruta/al/proyecto/construccion
  ```

### D. Checklist de Evidencias Requeridas
Para auditar y certificar que la configuracion es segura, se deben documentar y recopilar las siguientes evidencias:
- [ ] **Captura 1**: Pantalla de LM Studio en la pestaña "Local Server" mostrando el servidor activo en el puerto 1234 y el modelo cargado.
- [ ] **Captura 2**: Consola con la salida del script `test_lmstudio_connection.py` mostrando que la conexion se realiza exitosamente con el host loopback.
- [ ] **Captura 3**: Configuracion del Firewall de Windows en PowerShell o en la interfaz grafica de Windows Defender Firewall mostrando las reglas de salida bloqueando el trafico externo de Python y LM Studio.
- [ ] **Captura 4**: Terminal de comandos ejecutando un `ping google.com` exitoso (para demostrar que la maquina si tiene red general) junto con un script de python intentando hacer una consulta externa (por ejemplo, a `requests.get('https://google.com')`) fallando por bloqueo del Firewall.
- [ ] **Captura 5**: Salida del comando de permisos de archivos (`icacls` o `ls -la`) demostrando que solo el usuario actual tiene acceso al proyecto.

---

## 👥 4. Conclusion en Equipo: Balance Tecnologico (Tarjeta 4.1)

El analisis comparativo entre la implementacion local vs. nube para nuestro analizador de sentimientos arroja las siguientes conclusiones tecnicas:

| Dimensión | Inferencia Local (LM Studio) | API en la Nube (OpenAI / Cohere) |
|---|---|---|
| **Costo Financiero** | **$0.00 constante**. La infraestructura es propia. Costo amortizado en el hardware existente. Cero costo por token. | Pago por uso (Pay-as-you-go). El costo escala linealmente con el volumen de datos e inferencias mensuales. |
| **Privacidad y Cumplimiento** | **Seguridad Absoluta (100% Offline)**. Los tweets confidenciales y los datos internos nunca salen del servidor local. Facilita el cumplimiento de normativas de privacidad (GDPR / locales). | **Riesgo de Fuga de Datos**. Los datos viajan por internet a servidores externos de terceros y pueden ser usados para re-entrenar modelos o guardarse en logs. |
| **Rendimiento y Latencia** | Latencia constante sin depender de ancho de banda o disponibilidad de internet. La velocidad depende de la potencia de la GPU/CPU local (en un modelo de 1B a 3B en GPU dedicada, la latencia es <1s). | Latencia variable sujeta al trafico de red (retraso de ida y vuelta de API) y saturacion de los servidores de la nube. Puede ser mas rapido para modelos masivos. |

### Sintesis
La inferencia local es la opcion optima para este proyecto debido a que el procesamiento de datos sensibles (tweets con informacion potencialmente confidencial o sujeta a auditorias locales) requiere un control riguroso de la transmision de datos. El uso de modelos ligeros cuantizados como **Llama-3.2-1B-Instruct** o **Phi-3-mini** nos permite obtener precisiones competitivas sin incurrir en costos operativos de API en la nube ni comprometer la privacidad del entorno corporativo.

---

## 📁 5. Estructura de Carpetas del Repositorio Limpio

Para asegurar un repositorio limpio y ordenado, se ha definido la siguiente estructura, eliminando archivos temporales basura o duplicados:

```
construccion/
├── data/
│   ├── twitter_validation.csv       # Dataset original de Kaggle para validacion
│   └── resultados_inferencia.csv    # [RESULTADO] Salida del procesamiento por lotes
├── src/
│   └── batch_processing.py          # Script de inferencia por lotes y evaluacion
├── static/
│   ├── css/styles.css               # Estilos frontend de la aplicacion FastAPI
│   └── js/app.js                    # Logica frontend
├── templates/
│   ├── index.html                   # Vista principal de la app FastAPI
│   └── login.html                   # Vista de autenticacion de la app FastAPI
├── venv/                            # Entorno virtual de Python (excluido en .gitignore)
├── db_config.py                     # Configuracion de conexion a la base de datos MySQL
├── download_dataset.py              # Script utilitario para descargar el CSV de Kaggle
├── main.py                          # Backend FastAPI para el panel web principal
├── migrate_data.py                  # Migracion de base de datos MySQL
├── prueba_dataset.py                # Prueba inicial de pipeline local HuggingFace
├── requirements.txt                 # Dependencias del backend FastAPI + MySQL
├── requirements_lmstudio.txt        # Dependencias especificas de integracion LM Studio
├── test_lmstudio_connection.py      # Script de prueba rapida de conexion local
└── DOCUMENTACION_LMSTUDIO.md        # [NUEVO] Guia de setup, ejecucion, hardening y conclusiones
```
