
# ─────────────────────────────────────────────────────────────────────
# main.py
# Es el servidor de la API. Define los endpoints (URLs) que el sitio
# web puede llamar para hablar con el agente.
#
# Cuando Render arranca el proyecto, ejecuta este archivo.
# ─────────────────────────────────────────────────────────────────────

import logging
import os
import uuid
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from agente import chatear, obtener_historial

log = logging.getLogger("agente_peliculas")


# ── La aplicación ─────────────────────────────────────────────────────
# Creamos la app FastAPI con metadatos que aparecen en /docs
# /docs es la documentación automática — muy útil para probar la API
app = FastAPI(
    title="Agente Recomendador de Películas",
    description="API con memoria persistente en Redis",
    version="1.0.0"
)


# ── CORS ──────────────────────────────────────────────────────────────
# CORS es un mecanismo de seguridad de los navegadores.
# Sin esto, el sitio web no podría llamar la API desde otro dominio.
# En Render define ALLOWED_ORIGINS con el dominio de tu sitio, por ejemplo:
#   ALLOWED_ORIGINS=https://misitio.com,https://www.misitio.com
# Si no se define, se permite cualquier dominio ("*").
ORIGENES = [o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "*").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=ORIGENES,
    allow_methods=["*"],
    allow_headers=["*"]
)


# ── Modelos de datos ──────────────────────────────────────────────────
# Pydantic valida que los datos que llegan y salen tengan
# el formato correcto. Si falta un campo requerido, FastAPI
# retorna un error automáticamente sin que escribamos código extra.

class Consulta(BaseModel):
    """
    Lo que el sitio web envía al endpoint /consultar.

    session_id es opcional:
    - Si no viene → usuario nuevo → generamos un session_id nuevo
    - Si viene    → usuario existente → retomamos su conversación en Redis

    Ejemplo de llamada desde el sitio web:
    {
        "session_id": "abc-123",   (opcional)
        "mensaje": "Me gustan las películas de terror"
    }
    """
    session_id: str | None = None  # opcional — None si es usuario nuevo
    mensaje:    str                # requerido — lo que escribió el usuario


class Respuesta(BaseModel):
    """
    Lo que la API retorna al sitio web.

    El sitio web debe guardar el session_id y enviarlo
    en cada mensaje siguiente para mantener el contexto.

    Ejemplo de respuesta:
    {
        "session_id": "abc-123",
        "respuesta": "Te recomiendo El Conjuro...",
        "mensajes_en_memoria": 4
    }
    """
    session_id:            str  # el sitio web debe guardarlo
    respuesta:             str  # la respuesta del agente
    mensajes_en_memoria:   int  # cuántos mensajes hay en Redis


# ── Endpoints ─────────────────────────────────────────────────────────

@app.get("/")
def raiz():
    """
    Health check — verifica que la API está activa.
    Render y cualquier sistema de monitoreo pueden llamar
    este endpoint para saber si el servidor está funcionando.
    """
    return {"estado": "activo", "agente": "Recomendador de Películas"}


@app.post("/consultar", response_model=Respuesta)
def consultar(consulta: Consulta):
    """
    Endpoint principal — recibe el mensaje y retorna la respuesta.

    Si no viene session_id generamos uno nuevo con uuid4().
    uuid4() crea un ID único de 36 caracteres garantizado.
    El sitio web debe guardar este ID y enviarlo en el próximo mensaje.
    """
    # Si es usuario nuevo generamos su session_id
    session_id = consulta.session_id or str(uuid.uuid4())

    # Llamamos al agente
    try:
        resultado = chatear(
            session_id=session_id,
            mensaje=consulta.mensaje
        )
    except KeyError as e:
        # Falta una variable de entorno (REDIS_URL)
        log.exception("Configuración incompleta")
        raise HTTPException(status_code=503, detail=f"Servicio mal configurado: falta la variable {e}.")
    except Exception as e:
        # Errores de Groq (clave inválida, modelo retirado, límite de uso) o de Redis.
        # Se registra el detalle en los logs de Render y se responde 503 en vez de un 500 opaco.
        log.exception("Error al consultar el agente")
        raise HTTPException(
            status_code=503,
            detail=f"El agente no está disponible en este momento ({type(e).__name__}). Intenta de nuevo más tarde.",
        )

    return Respuesta(
        session_id=          session_id,
        respuesta=           resultado["respuesta"],
        mensajes_en_memoria= resultado["mensajes_en_memoria"]
    )


@app.delete("/limpiar/{session_id}")
def limpiar(session_id: str):
    """
    Borra el historial de un usuario en Redis.
    Útil cuando el usuario quiere empezar una conversación nueva.

    Ejemplo de llamada:
    DELETE https://tu-api.onrender.com/limpiar/abc-123
    """
    try:
        obtener_historial(session_id).clear()
    except Exception as e:
        log.exception("Error al limpiar el historial")
        raise HTTPException(status_code=503, detail=f"No se pudo acceder a la memoria ({type(e).__name__}).")
    return {"mensaje": f"Historial '{session_id}' eliminado"}
