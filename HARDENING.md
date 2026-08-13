# Guía de Bastionado (Hardening) de LM Studio

Este documento detalla las instrucciones paso a paso para asegurar la ejecución del servidor local de **LM Studio**, garantizando que funcione de forma aislada, sin acceso a internet (para máxima privacidad de los datos) y con permisos del sistema de archivos estrictamente limitados (ACL/DAC) en sistemas **Windows** y **Linux**.

---

## 🔒 1. Conceptos de Seguridad Aplicados
Para lograr un entorno seguro de inferencia local con LLMs, aplicamos dos principios fundamentales de ciberseguridad:
1. **Principio de Mínimo Privilegio (ACL/Permisos)**: Evitar que otros usuarios del sistema puedan leer, escribir o ejecutar la aplicación o sus modelos cargados.
2. **Aislamiento de Red (Firewall)**: Bloquear cualquier tráfico de salida (outbound) a internet de LM Studio para prevenir la telemetría, descargas no autorizadas de modelos o fugas de información, permitiendo únicamente el tráfico de entrada de bucle local (*loopback*) en el puerto `1234`.

---

## 💻 Bastionado en Windows

> [!IMPORTANT]
> Reemplaza `<Usuario>` en los siguientes comandos por tu nombre de usuario de Windows actual (puedes verificarlo ejecutando `whoami` en PowerShell).

### Paso 1: Configurar el Firewall de Windows (PowerShell Administrador)
Abre PowerShell con privilegios de Administrador y ejecuta los siguientes comandos para bloquear el acceso a internet de LM Studio y restringir su acceso de red:

```powershell
# 1. Definir la ruta del ejecutable de LM Studio (Ruta estándar de instalación por usuario)
$LMStudioPath = "$env:LOCALAPPDATA\Programs\lm-studio\LM Studio.exe"

# 2. Bloquear todas las conexiones de salida (Outbound) para el ejecutable
New-NetFirewallRule -DisplayName "LM-Studio: Bloquear Salida Internet" `
    -Direction Outbound `
    -Program $LMStudioPath `
    -Action Block `
    -Description "Bloquea todo el trafico saliente a Internet desde LM Studio para privacidad."

# 3. Permitir conexiones de entrada únicamente en la interfaz de bucle local (Loopback/Localhost)
New-NetFirewallRule -DisplayName "LM-Studio: Permitir Entrada Localhost (TCP 1234)" `
    -Direction Inbound `
    -Program $LMStudioPath `
    -Protocol TCP `
    -LocalPort 1234 `
    -RemoteAddress 127.0.0.1,::1 `
    -Action Allow `
    -Description "Permite conexiones entrantes al API local de LM Studio desde el propio equipo."

# 4. Bloquear cualquier otra conexión de entrada (Inbound) desde el resto de la red local
New-NetFirewallRule -DisplayName "LM-Studio: Bloquear Entrada Externa" `
    -Direction Inbound `
    -Program $LMStudioPath `
    -Action Block `
    -Description "Bloquea accesos entrantes a LM Studio desde cualquier IP externa."
```

### Paso 2: Restringir Permisos de Archivos (ACL) con `icacls`
Por defecto, Windows instala las aplicaciones de usuario en `%LOCALAPPDATA%`, lo cual es accesible por el propio usuario y administradores. Para asegurar que otros usuarios locales del sistema no puedan inspeccionar ni modificar los binarios ni modelos, ejecuta:

```powershell
# Ruta de instalación de LM Studio
$LMStudioFolder = "$env:LOCALAPPDATA\Programs\lm-studio"

# Deshabilitar la herencia de permisos y remover permisos heredados, manteniendo solo a los necesarios
icacls $LMStudioFolder /inheritance:r /grant:r "$($env:USERNAME):(OI)(CI)(F)" /grant:r "SYSTEM:(OI)(CI)(F)" /grant:r "Administrators:(OI)(CI)(F)"
```

> [!TIP]
> Si almacenas los modelos de LM Studio en una ruta personalizada (por ejemplo, en `C:\Users\<Usuario>\.cache\lm-studio\models`), aplica el mismo comando `icacls` a esa carpeta para proteger la propiedad intelectual de tus modelos descargados.

---

## 🐧 Bastionado en Linux

En Linux, la mejor práctica de bastionado consiste en crear un usuario y grupo de sistema dedicado para ejecutar el binario de LM Studio (o su AppImage) e implementar reglas de Firewall por ID de usuario.

### Paso 1: Crear un Usuario de Sistema Dedicado
Evita ejecutar LM Studio con tu cuenta de usuario regular o como `root`. Crea un usuario sin shell interactivo:

```bash
# Crear grupo y usuario de sistema sin shell ni home directory
sudo groupadd -r lmstudio
sudo useradd -r -g lmstudio -d /opt/lmstudio -s /sbin/nologin -c "LM Studio Service Account" lmstudio
```

### Paso 2: Restringir Permisos del Directorio y Ejecutable (DAC)
Coloca la aplicación (ej. el AppImage) en un directorio del sistema protegido:

```bash
# Crear directorio de trabajo
sudo mkdir -p /opt/lmstudio/bin
sudo mkdir -p /opt/lmstudio/models

# Mover la AppImage al directorio seguro (reemplazar con la ruta real de descarga)
sudo mv LM_Studio.AppImage /opt/lmstudio/bin/lmstudio.AppImage
sudo chmod +x /opt/lmstudio/bin/lmstudio.AppImage

# Establecer la propiedad del directorio al usuario dedicado
sudo chown -R lmstudio:lmstudio /opt/lmstudio

# Restringir permisos de lectura/escritura/ejecución exclusivamente al propietario
sudo chmod 700 /opt/lmstudio/bin/lmstudio.AppImage
sudo chmod -R 700 /opt/lmstudio
```

### Paso 3: Configurar el Firewall (iptables / UFW)
Aislamos la red del usuario `lmstudio` bloqueando todo el tráfico de salida de red WAN y permitiendo únicamente la interfaz de loopback (`lo`).

#### Opción A: Reglas con `iptables` nativo (Recomendado)
```bash
# Permitir al usuario 'lmstudio' usar la interfaz loopback (indispensable para exponer el puerto 1234 localmente)
sudo iptables -A OUTPUT -m owner --uid-owner lmstudio -o lo -j ACCEPT

# Bloquear cualquier otro trafico de salida (Internet / LAN externa) para ese usuario
sudo iptables -A OUTPUT -m owner --uid-owner lmstudio -j REJECT

# Guardar las reglas para que persistan tras reiniciar (en Debian/Ubuntu)
sudo apt-get install iptables-persistent -y
sudo netfilter-persistent save
```

#### Opción B: Si utilizas `UFW` (Uncomplicated Firewall)
UFW no soporta de forma nativa reglas por propietario (`owner`) en su CLI estándar, por lo que debes añadir las reglas en el archivo de configuración `/etc/ufw/before.rules`:

1. Edita el archivo con `sudo nano /etc/ufw/before.rules`.
2. Añade las siguientes líneas antes de la directiva `COMMIT` al final del archivo:
   ```text
   # Reglas para aislar LM Studio
   -A ufw-before-output -m owner --uid-owner lmstudio -o lo -j ACCEPT
   -A ufw-before-output -m owner --uid-owner lmstudio -j REJECT
   ```
3. Recarga UFW: `sudo ufw reload`.

---

## 🔍 Verificación del Bloqueo
Para certificar que las reglas se han aplicado correctamente:

1. **Prueba de Conexión Local**: Ejecuta la API de FastAPI (`python main.py`). Esta debería conectarse exitosamente a `http://localhost:1234/v1` y obtener respuestas sin problemas.
2. **Prueba de Fuga de Red**: 
   - En Windows, intenta abrir un comando PowerShell bajo el contexto del firewall o verifica en el Monitor de Recursos que los procesos asociados a `LM Studio.exe` no tengan direcciones IP remotas externas (solo `127.0.0.1` o `::1`).
   - En Linux, ejecuta una prueba de curl usando el usuario `lmstudio`:
     ```bash
     sudo -u lmstudio curl -I https://www.google.com
     ```
     La respuesta debería ser rechazada inmediatamente (`Connection refused` o similar), demostrando el correcto aislamiento del servicio.
