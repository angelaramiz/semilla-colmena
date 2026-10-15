# scripts/memoria.py — Memoria local de la agencia (mem0 + Ollama + Qdrant).
# Todo 100% en la máquina: sin nube, sin suscripción.
# Uso:
#   python scripts/memoria.py guardar "La Directora prefiere reportes en español" [-u directora]
#   python scripts/memoria.py recordar "idioma de reportes" [-u directora]
import os
import sys

USUARIO_DEFAULT = "directora"


def _memory():
    from mem0 import Memory
    config = {
        "llm": {
            # qwen2.5 sin thinking: qwen3 responde vacío en chat y mem0 no extrae hechos.
            "provider": "ollama",
            "config": {"model": os.getenv("MEMORIA_LLM_MODEL", "qwen2.5:1.5b"),
                       "ollama_base_url": os.getenv("LOCAL_LLM_BASE_URL", "http://localhost:11434"),
                       "temperature": 0.1, "max_tokens": 512},
        },
        "embedder": {
            "provider": "ollama",
            "config": {"model": "nomic-embed-text",
                       "ollama_base_url": os.getenv("LOCAL_LLM_BASE_URL", "http://localhost:11434")},
        },
        "vector_store": {
            "provider": "qdrant",
            "config": {"host": os.getenv("QDRANT_HOST", "localhost"),
                       "port": int(os.getenv("QDRANT_PORT", "6333")),
                       "embedding_model_dims": 768},  # nomic-embed-text
        },
    }
    return Memory.from_config(config)


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("-u")]
    usuario = USUARIO_DEFAULT
    if "-u" in sys.argv:
        usuario = sys.argv[sys.argv.index("-u") + 1]
    if len(args) < 2 or args[0] not in ("guardar", "recordar"):
        print('Uso: memoria.py guardar|recordar "texto" [-u usuario]')
        return 2
    m = _memory()
    if args[0] == "guardar":
        r = m.add(args[1], user_id=usuario)
        print("GUARDADO:", r)
    else:
        r = m.search(args[1], filters={"user_id": usuario}, limit=5)
        for x in (r.get("results") if isinstance(r, dict) else r) or []:
            print("-", x.get("memory"), "|", round(float(x.get("score", 0)), 3))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
