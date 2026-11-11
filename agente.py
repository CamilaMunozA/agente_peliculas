
# ─────────────────────────────────────────────────────────────────────
# agente.py
# Contiene toda la lógica del agente: el modelo, la memoria en Redis
# y la función principal que procesa cada mensaje del usuario.
#
# Este archivo es independiente de la API — si mañana cambias FastAPI
# por otro framework, este archivo no necesita modificaciones.
# ─────────────────────────────────────────────────────────────────────

import os
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_community.chat_message_histories import RedisChatMessageHistory


# ── El modelo ─────────────────────────────────────────────────────────
# GROQ_API_KEY se lee automáticamente de las variables de entorno (Render).
# El modelo se puede cambiar con la variable GROQ_MODEL sin tocar el código
# (Groq retira modelos con frecuencia: https://console.groq.com/docs/deprecations).
# llama-3.3-70b-versatile se retiró del plan gratuito el 16/08/2026;
# Groq recomienda openai/gpt-oss-120b como reemplazo.
#
# El cliente se crea una sola vez, la primera vez que se necesita (no al
# importar): así, si falta GROQ_API_KEY, el servidor arranca igual y el
# error se reporta de forma clara en /consultar.
_modelo = None


def obtener_modelo() -> ChatGroq:
    global _modelo
    if _modelo is None:
        _modelo = ChatGroq(
            model=os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b"),
            temperature=0.7,   # 0.7 = respuestas naturales y variadas
            # gpt-oss es un modelo de razonamiento: los tokens de razonamiento
            # cuentan dentro de max_tokens, por eso el margen es mayor (antes 512).
            # La respuesta sigue siendo corta porque el prompt pide máximo 3 líneas.
            max_tokens=1024,
            reasoning_effort="low",   # respuestas rápidas; no hace falta razonar mucho
            max_retries=2,            # reintento automático ante fallos de red
            timeout=30,               # segundos máximos de espera
        )
    return _modelo


# ── El template ───────────────────────────────────────────────────────
# Define cómo se arma el prompt antes de enviarlo al modelo.
# Tiene tres partes:
#   1. system            → instrucciones de comportamiento del agente
#   2. MessagesPlaceholder → aquí se insertan los mensajes anteriores de Redis
#   3. human             → el mensaje actual del usuario
#
# Sin MessagesPlaceholder el agente no tendría memoria —
# cada mensaje llegaría al modelo sin contexto previo.
template = ChatPromptTemplate.from_messages([
    ("system", """Eres un asistente experto en recomendaciones de películas.
    Conoces todo tipo de géneros, directores y actores.
    Recuerdas las preferencias que el usuario ha mencionado durante
    la conversación y las usas para hacer recomendaciones personalizadas.
    Respondes de forma breve y amigable, máximo 3 líneas."""),
    MessagesPlaceholder(variable_name="historial"),
    ("human", "{mensaje}")
])


# ── Ventana de memoria ────────────────────────────────────────────────
# Cuántos mensajes del historial enviamos al modelo en cada llamada.
# 10 mensajes = 5 turnos completos (5 preguntas + 5 respuestas).
# Sin este límite, el historial crecería indefinidamente
# y el costo de tokens subiría con cada mensaje.
VENTANA = 10


def obtener_historial(session_id: str) -> RedisChatMessageHistory:
    """
    Conecta con Redis y retorna el historial de un usuario específico.

    Cada usuario tiene su propio session_id — una clave única que
    identifica su conversación en Redis. Si el usuario es nuevo,
    Redis crea un historial vacío automáticamente.

    ttl=3600 → la conversación se borra si no hay actividad en 1 hora.
    """
    return RedisChatMessageHistory(
        session_id=session_id,
        url=os.environ["REDIS_URL"],  # Render lee esta variable automáticamente
        ttl=3600
    )


def chatear(session_id: str, mensaje: str) -> dict:
    """
    Función principal del agente.
    Recibe el mensaje del usuario y retorna la respuesta.

    Flujo interno:
        1. Lee el historial de este usuario desde Redis
        2. Toma solo los últimos VENTANA mensajes
        3. Arma el prompt y genera la respuesta con el modelo
        4. Guarda el turno nuevo en Redis
        5. Retorna la respuesta con métricas

    Parámetros:
        session_id → identifica al usuario en Redis
        mensaje    → lo que escribió el usuario

    Retorna:
        dict con la respuesta, el session_id y cuántos mensajes
        hay guardados en Redis para este usuario
    """

    # Paso 1 — traemos el historial de este usuario desde Redis
    historial_redis = obtener_historial(session_id)

    # Paso 2 — aplicamos la ventana: solo los últimos N mensajes
    # [-VENTANA:] es Python estándar para "dame los últimos N elementos"
    mensajes_recientes = historial_redis.messages[-VENTANA:]

    # Paso 3 — construimos la chain y generamos la respuesta
    # template  → arma el prompt con el historial y el mensaje actual
    # modelo    → genera la respuesta
    # StrOutputParser → convierte la respuesta a texto plano
    chain     = template | obtener_modelo() | StrOutputParser()
    respuesta = chain.invoke({
        "historial": mensajes_recientes,
        "mensaje":   mensaje
    })

    # Paso 4 — guardamos este turno en Redis
    # En el próximo mensaje, estos dos líneas estarán en el historial
    historial_redis.add_user_message(mensaje)
    historial_redis.add_ai_message(respuesta)

    # Paso 5 — retornamos el resultado
    return {
        "respuesta":           respuesta,
        "session_id":          session_id,
        "mensajes_en_memoria": len(historial_redis.messages)
    }
