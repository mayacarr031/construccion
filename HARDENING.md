# Guía de Bastionado (Hardening) de Seguridad

Este documento detalla las instrucciones paso a paso para fortalecer la postura de seguridad de la infraestructura y el backend de análisis de sentimientos, cubriendo el aislamiento del entorno de ejecución de **LM Studio**, la protección del almacenamiento de los modelos y la sanitización de metadatos en **FastAPI**.

---

## 🔒 1. Aislamiento de Red de LM Studio (Firewall de Windows)

Para garantizar la absoluta privacidad de los datos procesados por el LLM local, configuramos el Firewall de Windows Defender con seguridad avanzada para denegar el acceso a internet (tanto de entrada como de salida) al ejecutable de LM Studio, limitando su exposición únicamente al puerto local TCP `1234`.

### Paso 1: Localizar el Ejecutable de LM Studio
Por defecto, LM Studio se instala en la ruta de perfil del usuario:
`%LOCALAPPDATA%\Programs\lm-studio\LM Studio.exe`
*(Equivale a `C:\Users\<TuUsuario>\AppData\Local\Programs\lm-studio\LM Studio.exe`)*

### Paso 2: Crear Reglas del Firewall mediante PowerShell (Administrador)
Abre PowerShell como **Administrador** y ejecuta los siguientes comandos para aplicar el aislamiento:

```powershell
# 1. Definir la ruta del binario de LM Studio
$LMStudioPath = "$env:LOCALAPPDATA\Programs\lm-studio\LM Studio.exe"

# 2. Bloquear todas las conexiones salientes (Outbound) del ejecutable
New-NetFirewallRule -DisplayName "LM-Studio: Bloquear Salida WAN" `
    -Direction Outbound `
    -Program $LMStudioPath `
    -Action Block `
    -Description "Bloquea toda conexion saliente de LM Studio a Internet."

# 3. Permitir conexiones entrantes únicamente desde localhost (bucle local) en el puerto TCP 1234
New-NetFirewallRule -DisplayName "LM-Studio: Permitir Entrada Localhost TCP 1234" `
    -Direction Inbound `
    -Program $LMStudioPath `
    -Protocol TCP `
    -LocalPort 1234 `
    -RemoteAddress 127.0.0.1,::1 `
    -Action Allow `
    -Description "Permite peticiones locales al API del modelo en el puerto 1234."

# 4. Bloquear cualquier otra conexión entrante (Inbound) externa (LAN o WAN)
New-NetFirewallRule -DisplayName "LM-Studio: Bloquear Entrada Externa" `
    -Direction Inbound `
    -Program $LMStudioPath `
    -Action Block `
    -Description "Deniega accesos entrantes a LM Studio desde cualquier maquina de la red local."
```

---

## 📁 2. Restricción de Permisos del Sistema de Archivos (ACL)

Los modelos de lenguaje (.gguf) representan propiedad intelectual crítica y datos sensibles. Protegemos las carpetas del modelo restringiendo las Listas de Control de Acceso (ACL) para que solo el propietario de la cuenta y los procesos autorizados del sistema tengan lectura/escritura sobre ellos.

### Paso A: Identificar Carpetas de Almacenamiento
*   **Directorio del Ejecutable**: `%LOCALAPPDATA%\Programs\lm-studio`
*   **Directorio de Modelos / Caché**: `%USERPROFILE%\.cache\lm-studio`

### Paso B: Aplicar Restricción de ACL en Windows con `icacls`
Ejecuta los siguientes comandos en PowerShell para romper la herencia de permisos y otorgar control exclusivo únicamente al usuario propietario y al sistema:

```powershell
# 1. Asegurar la carpeta de la aplicacion
$AppFolder = "$env:LOCALAPPDATA\Programs\lm-studio"
icacls $AppFolder /inheritance:r /grant:r "$($env:USERNAME):(OI)(CI)(F)" /grant:r "SYSTEM:(OI)(CI)(F)" /grant:r "Administrators:(OI)(CI)(F)"

# 2. Asegurar la carpeta cache y de descarga de modelos
$ModelsFolder = "$env:USERPROFILE\.cache\lm-studio"
if (Test-Path $ModelsFolder) {
    icacls $ModelsFolder /inheritance:r /grant:r "$($env:USERNAME):(OI)(CI)(F)" /grant:r "SYSTEM:(OI)(CI)(F)" /grant:r "Administrators:(OI)(CI)(F)"
}
```

> [!NOTE]
> *   `(OI)`: Object Inherit (los archivos dentro de la carpeta heredan los permisos).
> *   `(CI)`: Container Inherit (las subcarpetas heredan los permisos).
> *   `(F)`: Full Control (Control total).

---

## 🛡️ 3. Sanitización de Encabezados y Metadatos en FastAPI

Por defecto, los servidores ASGI (como Uvicorn) y FastAPI pueden revelar metadatos técnicos en las cabeceras HTTP de respuesta (ej. `server: uvicorn`) o exponer rutas de documentación OpenAPI en entornos de producción, facilitando a un atacante el escaneo de vulnerabilidades.

Aplica las siguientes prácticas recomendadas en el código del backend:

### A. Deshabilitar Documentación Automática en Producción
Evita exponer Swagger UI (`/docs`) y ReDoc (`/redoc`) definiendo las variables en la instanciación de FastAPI basándote en la variable de entorno:

```python
import os
from fastapi import FastAPI

# Verificar entorno de ejecucion
is_production = os.getenv("ENV", "development") == "production"

app = FastAPI(
    title="API de Análisis de Sentimientos",
    docs_url=None if is_production else "/docs",
    redoc_url=None if is_production else "/redoc",
    openapi_url=None if is_production else "/openapi.json"
)
```

### B. Sanitización de Cabeceras HTTP con Middleware Personalizado
Añade un middleware ASGI en tu aplicación FastAPI para remover los encabezados que revelen la infraestructura subyacente (como `server`, `x-powered-by`, `x-process-time`, etc.):

```python
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

class HeaderSanitizerMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # Eliminar encabezados informativos del servidor
        response.headers.pop("server", None)
        response.headers.pop("x-powered-by", None)
        response.headers.pop("x-process-time", None)
        
        # Opcional: Agregar cabeceras de seguridad indispensables
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        
        return response

# Agregar el middleware a la aplicacion
app.add_middleware(HeaderSanitizerMiddleware)
```

### C. Configurar el Servidor ASGI (Uvicorn)
Al iniciar la aplicación con Uvicorn en producción, utiliza las banderas de seguridad para evitar que agregue su encabezado de servidor predeterminado en las respuestas HTTP:

```bash
uvicorn main:app --host 127.0.0.1 --port 8000 --no-server-header --no-date-header
```

*   `--no-server-header`: Elimina el encabezado `Server: uvicorn` de las respuestas HTTP de bajo nivel gestionadas directamente por el servidor web ASGI.
*   `--no-date-header`: Oculta el encabezado `Date` del servidor web en caso de ser necesario por políticas de endurecimiento.
