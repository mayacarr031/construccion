# 🛡️ Reporte de Auditoría de Seguridad (Security Audit)
**Fecha de Auditoría:** `2026-08-12 20:28:34`  
**Herramienta Empleada:** `pip-audit`  
**Estado General:** ⚠️ Vulnerabilidades Detectadas en Entorno

---
## 📌 1. Resumen Ejecutivo
- **Dependencias del Proyecto (`requirements.txt`):** `55` paquetes evaluados. **0 vulnerabilidades encontradas**.
- **Entorno Completo de Python:** `159` paquetes evaluados. **1 paquete(s) con vulnerabilidades conocidas**.

---
## 📦 2. Evaluación de `requirements.txt`
| Paquete | Versión Instalada | Estado de Seguridad | Vulnerabilidades (CVEs) |
|---|---|---|---|
| `fastapi` | `0.141.1` | 🟢 Seguro | Ninguna |
| `uvicorn` | `0.52.1` | 🟢 Seguro | Ninguna |
| `pymysql` | `1.2.0` | 🟢 Seguro | Ninguna |
| `sqlalchemy` | `2.0.52` | 🟢 Seguro | Ninguna |
| `pandas` | `3.0.5` | 🟢 Seguro | Ninguna |
| `numpy` | `2.5.2` | 🟢 Seguro | Ninguna |
| `requests` | `2.34.2` | 🟢 Seguro | Ninguna |
| `charset-normalizer` | `3.5.0` | 🟢 Seguro | Ninguna |
| `idna` | `3.18` | 🟢 Seguro | Ninguna |
| `urllib3` | `2.7.0` | 🟢 Seguro | Ninguna |
| `openai` | `3.0.0` | 🟢 Seguro | Ninguna |
| `anyio` | `4.14.2` | 🟢 Seguro | Ninguna |
| `distro` | `1.9.0` | 🟢 Seguro | Ninguna |
| `httpx2` | `2.10.0` | 🟢 Seguro | Ninguna |
| `httpcore2` | `2.10.0` | 🟢 Seguro | Ninguna |
| `jiter` | `0.16.0` | 🟢 Seguro | Ninguna |
| `pydantic` | `2.13.4` | 🟢 Seguro | Ninguna |
| `pydantic-core` | `2.46.4` | 🟢 Seguro | Ninguna |
| `typing-extensions` | `4.16.0` | 🟢 Seguro | Ninguna |
| `pip-audit` | `2.10.1` | 🟢 Seguro | Ninguna |
| `cyclonedx-python-lib` | `11.11.2` | 🟢 Seguro | Ninguna |
| `license-expression` | `30.4.4` | 🟢 Seguro | Ninguna |
| `packageurl-python` | `0.17.6` | 🟢 Seguro | Ninguna |
| `py-serializable` | `2.1.0` | 🟢 Seguro | Ninguna |
| `defusedxml` | `0.7.1` | 🟢 Seguro | Ninguna |
| `sortedcontainers` | `2.4.0` | 🟢 Seguro | Ninguna |
| `annotated-doc` | `0.0.5` | 🟢 Seguro | Ninguna |
| `annotated-types` | `0.8.0` | 🟢 Seguro | Ninguna |
| `boolean-py` | `5.0` | 🟢 Seguro | Ninguna |
| `cachecontrol` | `0.14.4` | 🟢 Seguro | Ninguna |
| `msgpack` | `1.2.1` | 🟢 Seguro | Ninguna |
| `certifi` | `2026.7.22` | 🟢 Seguro | Ninguna |
| `click` | `8.4.2` | 🟢 Seguro | Ninguna |
| `filelock` | `3.32.2` | 🟢 Seguro | Ninguna |
| `greenlet` | `3.5.5` | 🟢 Seguro | Ninguna |
| `h11` | `0.16.0` | 🟢 Seguro | Ninguna |
| `pip-api` | `0.0.34` | 🟢 Seguro | Ninguna |
| `pip-requirements-parser` | `32.0.1` | 🟢 Seguro | Ninguna |
| `platformdirs` | `4.11.2` | 🟢 Seguro | Ninguna |
| `python-dateutil` | `2.9.0.post0` | 🟢 Seguro | Ninguna |
| `rich` | `15.0.0` | 🟢 Seguro | Ninguna |
| `pygments` | `2.20.0` | 🟢 Seguro | Ninguna |
| `markdown-it-py` | `4.2.0` | 🟢 Seguro | Ninguna |
| `mdurl` | `0.1.2` | 🟢 Seguro | Ninguna |
| `six` | `1.17.0` | 🟢 Seguro | Ninguna |
| `starlette` | `1.6.0` | 🟢 Seguro | Ninguna |
| `tomli` | `2.4.1` | 🟢 Seguro | Ninguna |
| `tomli-w` | `1.2.0` | 🟢 Seguro | Ninguna |
| `tqdm` | `4.70.0` | 🟢 Seguro | Ninguna |
| `truststore` | `0.10.4` | 🟢 Seguro | Ninguna |
| `typing-inspection` | `0.4.4` | 🟢 Seguro | Ninguna |
| `colorama` | `0.4.6` | 🟢 Seguro | Ninguna |
| `pyparsing` | `3.3.2` | 🟢 Seguro | Ninguna |
| `sniffio` | `1.3.1` | 🟢 Seguro | Ninguna |
| `tzdata` | `2026.3` | 🟢 Seguro | Ninguna |

---
## 🔍 3. Detalle de Vulnerabilidades Detectadas
### ⚠️ Paquete Afectado: `pip` (v`25.3`)
- **Identificador:** `PYSEC-2026-196` (CVE-2026-8643, GHSA-wf93-45jw-7689)
  - **Versión de Corrección Recomendada:** `26.1.2`
  - **Descripción:** pip would treat console_scripts and gui_scripts as paths instead of file names without sanitizing the resolved absolute path to the installation directory, leading to entry points being installed outside the installation directory.

- **Identificador:** `PYSEC-2026-1796` (GHSA-6vgw-5pg2-w6jp, CVE-2026-1703)
  - **Versión de Corrección Recomendada:** `26.0`
  - **Descripción:** When pip is installing and extracting a maliciously crafted wheel archive, files may be extracted outside the installation directory. The path traversal is limited to prefixes of the installation directory, thus isn't able to inject or overwrite executable files in typical situations.

- **Identificador:** `PYSEC-2026-196` (CVE-2026-8643, GHSA-wf93-45jw-7689)
  - **Versión de Corrección Recomendada:** `26.1.2`
  - **Descripción:** pip would treat console_scripts and gui_scripts as paths instead of file names without sanitizing the resolved absolute path to the installation directory, leading to entry points being installed outside the installation directory.

- **Identificador:** `PYSEC-2026-2875` (GHSA-58qw-9mgm-455v, CVE-2026-3219)
  - **Versión de Corrección Recomendada:** `26.1`
  - **Descripción:** pip handles concatenated tar and ZIP files as ZIP files regardless of filename or whether a file is both a tar and ZIP file. This behavior could result in confusing installation behavior, such as installing "incorrect" files according to the filename of the archive. New behavior only proceeds with installation if the file identifies uniquely as a ZIP or tar archive, not as both.

- **Identificador:** `PYSEC-2026-2876` (GHSA-jp4c-xjxw-mgf9, CVE-2026-6357)
  - **Versión de Corrección Recomendada:** `26.1`
  - **Descripción:** pip prior to version 26.1 would run self-update check functionality after installing wheel files which required importing well-known Python modules names. These module imports were intentionally deferred to increase startup time of the pip CLI. The patch changes self-update functionality to run before wheels are installed to prevent newly-installed modules from being imported shortly after the installation of a wheel package. Users should still review package contents prior to installation.

---
## 💡 4. Plan de Acción y Remedios
1. **Actualización del paquete `pip`:**
   - Se identificaron vulnerabilidades en el gestor de paquetes `pip` (v25.3). Se recomienda actualizar a la versión `26.1.2` o superior:
     ```bash
     python -m pip install --upgrade pip
     ```
2. **Automatización en CI/CD:**
   - Integrar `pip-audit -r requirements.txt` como paso obligatorio en las pruebas continuas de seguridad para evitar la introducción de dependencias inseguras.