# puente_agui/servidor.py — Endpoint AG-UI del orquestador de la agencia.
# Corre en su propio venv (sin tocar el venv de la agencia). Por cada run,
# lanza `main.py --orquestador` del repo agencia en un subproceso y reenvía
# su stdout como deltas de mensaje AG-UI (SSE). OpenBot lo registra como Bot.
import json
import os
import subprocess
import sys
import uuid

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

AQUI = os.path.dirname(os.path.abspath(__file__))
AGENCIA = os.path.dirname(AQUI)  # raiz del repo agencia (agen_mrk)
PY_AGENCIA = os.path.join(AGENCIA, ".venv", "Scripts", "python.exe")
TOKEN = os.environ.get("PUENTE_TOKEN", "").strip()
MEM_USUARIO = os.environ.get("MEMORIA_USUARIO", "directora")

app = FastAPI(title="Puente AG-UI — Orquestador Colmena")


def _texto_instruccion(messages) -> str:
    for m in reversed(messages or []):
        if isinstance(m, dict) and m.get("role") == "user":
            c = m.get("content", "")
            if isinstance(c, str):
                return c
            if isinstance(c, list):
                return "".join(p.get("text", "") for p in c if isinstance(p, dict) and p.get("type") in ("text", "input_text"))
    return ""


def _ev(tipo: str, **kw) -> str:
    return "data: " + json.dumps({"type": tipo, **kw}, ensure_ascii=False) + "\n\n"


def _memoria(args: list) -> str:
    """Llama a scripts/memoria.py (modo local). Nunca rompe el run."""
    try:
        r = subprocess.run([PY_AGENCIA, os.path.join(AGENCIA, "scripts", "memoria.py")] + args,
                           cwd=AGENCIA, capture_output=True, text=True, timeout=300)
        return (r.stdout or "").strip()
    except Exception as e:
        return "[memoria no disponible: %s]" % str(e)[:100]


@app.get("/health")
def health():
    return {"ok": True, "harness": "colmena-orquestador"}


@app.post("/ag-ui")
async def ag_ui(req: Request):
    if TOKEN and req.headers.get("x-openbot-agent-token", "").strip() != TOKEN:
        return JSONResponse({"error": "unauthorised"}, status_code=401)
    try:
        body = await req.json()
    except Exception:
        return JSONResponse({"error": "json inválido"}, status_code=400)
    thread_id = body.get("threadId", "")
    run_id = body.get("runId", "") or uuid.uuid4().hex[:8]
    instruccion = _texto_instruccion(body.get("messages")).strip()
    if not instruccion:
        def _vacio():
            yield _ev("RUN_STARTED", threadId=thread_id, runId=run_id)
            yield _ev("RUN_ERROR", message="sin instrucción del usuario", code="sin-instruccion")
        return StreamingResponse(_vacio(), media_type="text/event-stream")

    def _gen():
        yield _ev("RUN_STARTED", threadId=thread_id, runId=run_id)
        mid = "m-" + run_id
        yield _ev("TEXT_MESSAGE_START", messageId=mid, role="assistant")
        # Memoria local: contexto previo entra a la instrucción; el resultado se guarda.
        ctx = _memoria(["recordar", instruccion, "-u", MEM_USUARIO])
        if ctx:
            instruccion_full = "Contexto recordado de la agencia:\n" + ctx + "\n\nInstrucción: " + instruccion
        else:
            instruccion_full = instruccion
        try:
            p = subprocess.Popen(
                [PY_AGENCIA, "main.py", "--orquestador", "--modo", "local", "-i", instruccion_full],
                cwd=AGENCIA, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace", bufsize=1,
            )
            for linea in p.stdout:
                linea = linea.rstrip("\n")
                if linea.strip():
                    yield _ev("TEXT_MESSAGE_CONTENT", messageId=mid, delta=linea + "\n")
            rc = p.wait()
            if rc != 0:
                yield _ev("TEXT_MESSAGE_CONTENT", messageId=mid,
                          delta="\n[puente] el orquestador terminó con código %d\n" % rc)
            else:
                _memoria(["guardar", "Se atendió: %s (estado ok)" % instruccion[:300], "-u", MEM_USUARIO])
        except Exception as e:
            yield _ev("TEXT_MESSAGE_CONTENT", messageId=mid, delta="\n[puente] error: %s\n" % str(e)[:300])
        yield _ev("TEXT_MESSAGE_END", messageId=mid)
        yield _ev("RUN_FINISHED", threadId=thread_id, runId=run_id)
    return StreamingResponse(_gen(), media_type="text/event-stream")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=int(os.getenv("PUENTE_PORT", "4210")))
