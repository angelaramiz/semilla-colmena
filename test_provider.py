# test_provider.py
import os, sys, json
from dotenv import load_dotenv

load_dotenv()
sys.path.append(".")

from servidor_mcp import buscar_negocio

print(f"🔍 Probando búsqueda con proveedor: {os.getenv('DATA_PROVIDER', 'mock').upper()}")

try:
    resultado = buscar_negocio("semilla morada", "Santa Catarina, Nuevo León")
    datos = json.loads(resultado)  # Convierte string JSON a dict para imprimir bonito
    
    print("✅ Respuesta recibida correctamente:")
    print(json.dumps(datos, indent=2, ensure_ascii=False))
    
    if datos.get("mock"):
        print("\n Modo MOCK activo. Para datos reales, configura SERPAPI_KEY o GOOGLE_API_KEY en .env")
    else:
        print(f"\n📊 Rating: {datos.get('rating')} | Reseñas: {datos.get('total_resenas')} | Web: {datos.get('tiene_web')}")
        
except Exception as e:
    print(f"\n❌ Error en prueba: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()