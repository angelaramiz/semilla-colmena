# core/llm_router.py
"""
Enrutador de modelos para la agencia.

Cada TAREA elige un nivel de modelo:
- "rutina"    -> Ollama local (gratis, privado, determinista): scraping, extracción,
                 resúmenes, clasificación, formateo JSON.
- "estrategia"-> OpenRouter (cloud, mayor calidad): copy creativo, estrategia,
                 toma de decisiones.

Si falta OPENROUTER_API_KEY, "estrategia" degrada a Ollama local con advertencia.
"""
import os
import sys
import time
import asyncio
import inspect

from dotenv import load_dotenv
from crewai import LLM

load_dotenv()

# Niveles soportados
RUTINA = "rutina"
ESTRATEGIA = "estrategia"


# --- Rotación automática ante 429 (rate-limit) ---------------------------
# Los modelos ':free' de OpenRouter comparten pool y devuelven 429 en horas pico.
# Interceptamos el chokepoint único (cliente OpenAI -> chat.completions.create)
# y, ante 429, reenviamos con el siguiente modelo de la cadena. Si TODOS los
# modelos de OpenRouter fallan por 429, caemos a OLLAMA LOCAL (fallback) para
# no bloquear esperando a OpenRouter.
def _build_ollama_client():
    from openai import OpenAI
    base = os.getenv("LOCAL_LLM_BASE_URL", "http://localhost:11434/v1")
    model = os.getenv("LOCAL_LLM_MODEL", "qwen3:4b")
    try:
        client = OpenAI(base_url=base, api_key="not-needed", timeout=60)
    except Exception:
        client = None
    return client, model


def _make_retry_wrapper(orig_create, models: list, log_fn, fallback=None):
    """Devuelve un wrapper (sync o async) que rota de modelo ante 429 y cae a Ollama local."""
    fclient, fmodel = fallback if fallback else (None, None)

    if inspect.iscoroutinefunction(orig_create):
        async def wrapper(**kwargs):
            last = None
            for i, model in enumerate(models):
                kw = dict(kwargs)
                kw["model"] = model
                try:
                    return await orig_create(**kw)
                except Exception as e:
                    if getattr(e, "status_code", None) == 429:
                        log_fn(f"429 en {model}; rotando a {models[i + 1]}" if i < len(models) - 1
                               else f"429 en {model}; OpenRouter agotado")
                        await asyncio.sleep(2)
                        last = e
                        continue
                    raise
            if fclient is not None and last is not None:
                log_fn(f"OpenRouter agotado; usando Ollama local ({fmodel})")
                kw = dict(kwargs)
                kw["model"] = fmodel
                return await fclient.chat.completions.create(**kw)
            raise last
        return wrapper

    def wrapper(**kwargs):
        last = None
        for i, model in enumerate(models):
            kw = dict(kwargs)
            kw["model"] = model
            try:
                return orig_create(**kw)
            except Exception as e:
                if getattr(e, "status_code", None) == 429:
                    log_fn(f"429 en {model}; rotando a {models[i + 1]}" if i < len(models) - 1
                           else f"429 en {model}; OpenRouter agotado")
                    time.sleep(2)
                    last = e
                    continue
                raise
        if fclient is not None and last is not None:
            log_fn(f"OpenRouter agotado; usando Ollama local ({fmodel})")
            kw = dict(kwargs)
            kw["model"] = fmodel
            return fclient.chat.completions.create(**kw)
        raise last
    return wrapper


def _patch_client(client, models: list, log_fn, fallback=None):
    """Parchea create/stream (sync+async) del cliente OpenAI para rotar modelos."""
    if client is None:
        return
    # chat.completions es un sub-recurso; responses tiene create directo.
    resources = []
    chat = getattr(client, "chat", None)
    if chat is not None and getattr(chat, "completions", None) is not None:
        resources.append(chat.completions)
    if getattr(client, "responses", None) is not None:
        resources.append(client.responses)
    for resource in resources:
        for method_attr in ("create", "stream"):
            method = getattr(resource, method_attr, None)
            if callable(method):
                setattr(resource, method_attr, _make_retry_wrapper(method, models, log_fn, fallback))


def enable_rotation(llm) -> LLM:
    """Parchea el LLM de estrategia para rotar modelos ante 429 y caer a Ollama local.
    Devuelve el mismo LLM (modificado in-place)."""
    models = [os.getenv("OPENROUTER_MODEL", "z-ai/glm-5.2:free")]
    fallbacks = [m.strip() for m in os.getenv("OPENROUTER_FALLBACK_MODELS", "").split(",") if m.strip()]
    models.extend(fallbacks)
    if not fallbacks:
        models = models[:1]  # sin fallbacks de OpenRouter, sin rotación entre ellos

    def log_fn(msg):
        print(f"\n[LLM-ROTACION] {msg}", file=sys.stderr)

    ollama_client, ollama_model = _build_ollama_client()
    fallback = (ollama_client, ollama_model) if ollama_client is not None else None

    try:
        _patch_client(llm._get_sync_client(), models, log_fn, fallback)
    except Exception as e:
        print(f"[LLM-ROTACION] sin sync client: {e}", file=sys.stderr)
    try:
        _patch_client(llm._get_async_client(), models, log_fn, fallback)
    except Exception as e:
        print(f"[LLM-ROTACION] sin async client: {e}", file=sys.stderr)
    return llm


def get_llm(nivel: str = RUTINA) -> LLM:
    """Retorna el LLM apropiado según el nivel de la tarea.

    - "rutina"    -> primer (único) modelo local de Ollama.
    - "estrategia"-> modelo primario de OpenRouter con ROTACIÓN automática ante 429.
    """
    if nivel == ESTRATEGIA:
        return enable_rotation(_get_openrouter())
    return _get_ollama_local()


def _get_ollama_local() -> LLM:
    """Modelo local (Ollama) para tareas rutinarias."""
    return LLM(
        model=os.getenv("LOCAL_LLM_MODEL", "qwen3:4b"),
        base_url=os.getenv("LOCAL_LLM_BASE_URL", "http://localhost:11434/v1"),
        api_key="not-needed",
        temperature=0.01,   # determinista para tool-calling estable
        top_p=0.9,
        timeout=120,
        max_tokens=2048,
    )


def _get_openrouter(model: str = None) -> LLM:
    """Modelo cloud (OpenRouter) para tareas de estrategia/creatividad."""
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        print("\n⚠️ OPENROUTER_API_KEY no configurada. Degradando 'estrategia' a Ollama local.", file=sys.stderr)
        return _get_ollama_local()

    model = model or os.getenv("OPENROUTER_MODEL", "z-ai/glm-5.2:free")
    return LLM(
        model=model,
        provider="openrouter",
        base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
        api_key=api_key,
        temperature=float(os.getenv("OPENROUTER_TEMPERATURE", "0.7")),
        max_tokens=int(os.getenv("OPENROUTER_MAX_TOKENS", "4096")),
    )