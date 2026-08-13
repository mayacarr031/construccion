import sys
import time
from openai import OpenAI

def test_connection():
    print("=== Iniciando Prueba de Conexion con LM Studio ===")
    print("Base URL: http://localhost:1234/v1")
    
    # Inicializar cliente compatible con la API de OpenAI
    client = OpenAI(
        base_url="http://localhost:1234/v1",
        api_key="lm-studio"
    )
    
    start_time = time.time()
    try:
        print("\n[+] Enviando solicitud de chat completado a LM Studio...")
        response = client.chat.completions.create(
            model="local-model",  # LM Studio utiliza por defecto cualquier modelo cargado
            messages=[
                {"role": "system", "content": "Eres un asistente de pruebas util y conciso."},
                {"role": "user", "content": "Hola. Responde con un saludo breve y confirma si estas listo para analizar sentimientos."}
            ],
            temperature=0.7,
            max_tokens=50
        )
        
        elapsed_time = time.time() - start_time
        
        # Procesar respuesta
        reply = response.choices[0].message.content
        print("\n[OK] Conexion Exitosa!")
        print(f"[*] Tiempo de respuesta: {elapsed_time:.2f} segundos")
        print(f"[*] Contenido de la respuesta:\n---\n{reply.strip()}\n---")
        print("\n[i] Verificacion de Costo y Privacidad:")
        print("    - Costo por tokens: $0.00 (Inferencia local y gratuita)")
        print("    - Flujo de datos: 100% Offline (Tus datos no salen de la maquina local)")
        
    except Exception as e:
        elapsed_time = time.time() - start_time
        print("\n[X] Error de conexion con el servidor local de LM Studio.")
        print(f"[*] Tiempo transcurrido: {elapsed_time:.2f} segundos")
        print(f"[*] Detalles del error: {e}")
        print("\n[!] Asegurate de que:")
        print("    1. LM Studio esta abierto.")
        print("    2. El servidor local de LM Studio esta activo (Local Server) expuesto en el puerto 1234.")
        print("    3. Tienes un modelo cargado en el servidor local de LM Studio.")
        sys.exit(1)

if __name__ == "__main__":
    test_connection()
