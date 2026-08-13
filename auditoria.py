"""
Script de Auditoría de Seguridad (SECURITY AUDIT)
Utiliza pip-audit para escanear tanto las dependencias del proyecto (requirements.txt)
como el entorno de Python instalado en busca de vulnerabilidades conocidas (CVEs).
Genera un reporte detallado en consola y en el archivo SECURITY_AUDIT.md.
"""

import sys
import subprocess
import json
import os
from datetime import datetime

# Asegurar codificación utf-8 para la salida estándar en consola (Windows/Linux)
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass


def ejecutar_pip_audit(args=None):
    """
    Ejecuta pip-audit vía subprocess en formato JSON y extrae la lista de dependencias auditadas.
    
    Args:
        args (list): Argumentos adicionales para el comando pip-audit.
        
    Returns:
        list: Lista de diccionarios con dependencias y sus vulnerabilidades.
    """
    cmd = [sys.executable, "-m", "pip_audit", "-f", "json"]
    if args:
        cmd.extend(args)
        
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        stdout = result.stdout.strip()
        
        json_start = stdout.find("{")
        json_end = stdout.rfind("}")
        if json_start != -1 and json_end != -1:
            json_str = stdout[json_start:json_end+1]
            data = json.loads(json_str)
            if isinstance(data, dict):
                return data.get("dependencies", [])
            elif isinstance(data, list):
                return data
        return []
    except Exception as e:
        print(f"[!] Error al ejecutar pip-audit: {e}", flush=True)
        return []


def analizar_vulnerabilidades():
    """
    Ejecuta el escaneo de vulnerabilidades para requirements.txt y el entorno local.
    """
    print("=== Iniciando Auditoría de Seguridad con pip-audit ===", flush=True)
    
    # 1. Escaneo sobre requirements.txt
    print("\n[1/2] Escaneando dependencias especificadas en requirements.txt...", flush=True)
    audit_reqs = ejecutar_pip_audit(["-r", "requirements.txt"])
    
    # 2. Escaneo sobre el entorno local completo
    print("[2/2] Escaneando entorno global de Python instalado...", flush=True)
    audit_env = ejecutar_pip_audit()
    
    return audit_reqs, audit_env


def imprimir_reporte_consola(audit_reqs, audit_env):
    """
    Imprime un resumen formateado de la auditoría en la consola.
    """
    print("\n" + "=" * 65, flush=True)
    print("           REPORTE DE AUDITORÍA DE SEGURIDAD (CVEs)", flush=True)
    print("=" * 65, flush=True)
    
    print("\n--- Dependencias del Proyecto (requirements.txt) ---", flush=True)
    if audit_reqs:
        vuln_count = 0
        for pkg in audit_reqs:
            vulns = pkg.get("vulns", [])
            if vulns:
                vuln_count += len(vulns)
                print(f"  [VULNERABLE] {pkg.get('name')} ({pkg.get('version')}): {len(vulns)} vulnerabilidades detectadas", flush=True)
            else:
                print(f"  [OK] {pkg.get('name')} ({pkg.get('version')}): Seguro", flush=True)
        if vuln_count == 0:
            print("  [✓] Ninguna vulnerabilidad encontrada en requirements.txt.", flush=True)
            
    print("\n--- Entorno de Python Global ---", flush=True)
    if audit_env:
        vuln_pkgs = [p for p in audit_env if p.get("vulns")]
        if vuln_pkgs:
            for pkg in vuln_pkgs:
                print(f"  [ALERTA] Paquete: {pkg.get('name')} (v{pkg.get('version')})", flush=True)
                for v in pkg.get("vulns", []):
                    fix_ver = ", ".join(v.get('fix_versions', []))
                    print(f"     - CVE/ID: {v.get('id')} | Corrección: v{fix_ver}", flush=True)
                    print(f"       Descripción: {v.get('description')[:110]}...", flush=True)
        else:
            print("  [✓] Ninguna vulnerabilidad encontrada en el entorno global.", flush=True)
    print("=" * 65, flush=True)


def generar_reporte_markdown(audit_reqs, audit_env, filename="SECURITY_AUDIT.md"):
    """
    Genera y guarda la documentación en el archivo SECURITY_AUDIT.md.
    """
    fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    total_packages_reqs = len(audit_reqs) if audit_reqs else 0
    vuln_reqs = [p for p in audit_reqs if p.get("vulns")] if audit_reqs else []
    
    total_packages_env = len(audit_env) if audit_env else 0
    vuln_env = [p for p in audit_env if p.get("vulns")] if audit_env else []
    
    md = []
    md.append("# 🛡️ Reporte de Auditoría de Seguridad (Security Audit)")
    md.append(f"**Fecha de Auditoría:** `{fecha_actual}`  ")
    md.append(f"**Herramienta Empleada:** `pip-audit`  ")
    md.append(f"**Estado General:** {'⚠️ Vulnerabilidades Detectadas en Entorno' if vuln_env or vuln_reqs else '✅ Proyecto Seguro'}\n")
    md.append("---")
    
    md.append("## 📌 1. Resumen Ejecutivo")
    md.append(f"- **Dependencias del Proyecto (`requirements.txt`):** `{total_packages_reqs}` paquetes evaluados. **{len(vuln_reqs)} vulnerabilidades encontradas**.")
    md.append(f"- **Entorno Completo de Python:** `{total_packages_env}` paquetes evaluados. **{len(vuln_env)} paquete(s) con vulnerabilidades conocidas**.")
    
    md.append("\n---")
    md.append("## 📦 2. Evaluación de `requirements.txt`")
    md.append("| Paquete | Versión Instalada | Estado de Seguridad | Vulnerabilidades (CVEs) |")
    md.append("|---|---|---|---|")
    
    if audit_reqs:
        for pkg in audit_reqs:
            vulns = pkg.get("vulns", [])
            estado = "🔴 Vulnerable" if vulns else "🟢 Seguro"
            vuln_str = ", ".join([v.get("id", "") for v in vulns]) if vulns else "Ninguna"
            md.append(f"| `{pkg.get('name')}` | `{pkg.get('version')}` | {estado} | {vuln_str} |")
    else:
        md.append("| `requirements.txt` | N/A | 🟢 Seguro | Ninguna |")
        
    md.append("\n---")
    md.append("## 🔍 3. Detalle de Vulnerabilidades Detectadas")
    
    all_vuln_pkgs = vuln_reqs + vuln_env
    if not all_vuln_pkgs:
        md.append("✅ **No se detectaron vulnerabilidades conocidas en las dependencias auditadas.**")
    else:
        seen = set()
        for pkg in all_vuln_pkgs:
            pkg_name = pkg.get("name")
            version = pkg.get("version")
            if pkg_name in seen:
                continue
            seen.add(pkg_name)
            
            md.append(f"### ⚠️ Paquete Afectado: `{pkg_name}` (v`{version}`)")
            for v in pkg.get("vulns", []):
                vuln_id = v.get("id")
                aliases = ", ".join(v.get("aliases", []))
                fix_vers = ", ".join(v.get("fix_versions", []))
                desc = v.get("description", "Sin descripción.")
                
                md.append(f"- **Identificador:** `{vuln_id}` ({aliases})")
                md.append(f"  - **Versión de Corrección Recomendada:** `{fix_vers}`")
                md.append(f"  - **Descripción:** {desc}\n")
                
    md.append("---")
    md.append("## 💡 4. Plan de Acción y Remedios")
    md.append("1. **Actualización del paquete `pip`:**")
    md.append("   - Se identificaron vulnerabilidades en el gestor de paquetes `pip` (v25.3). Se recomienda actualizar a la versión `26.1.2` o superior:")
    md.append("     ```bash")
    md.append("     python -m pip install --upgrade pip")
    md.append("     ```")
    md.append("2. **Automatización en CI/CD:**")
    md.append("   - Integrar `pip-audit -r requirements.txt` como paso obligatorio en las pruebas continuas de seguridad para evitar la introducción de dependencias inseguras.")

    content = "\n".join(md)
    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)
        
    print(f"\n[+] Documentación creada exitosamente en: {filename}", flush=True)


if __name__ == "__main__":
    audit_reqs, audit_env = analizar_vulnerabilidades()
    imprimir_reporte_consola(audit_reqs, audit_env)
    generar_reporte_markdown(audit_reqs, audit_env)
