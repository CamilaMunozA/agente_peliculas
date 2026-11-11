# 🎬 Agente con Memoria Redis — Recomendador de Películas

**Ruta LangChain · Nivel 4: Memory**  
Proveedor LLM: Groq | Memoria persistente: Redis Cloud | Framework API: FastAPI

---

## Descripción

Agente conversacional de recomendaciones de películas construido con LangChain que mantiene **memoria persistente por usuario** usando Redis Cloud. A diferencia de los niveles anteriores de la ruta (donde cada llamada era independiente), este agente recuerda los gustos del usuario a lo largo de toda la conversación, incluso si el entorno de Google Colab se reinicia.

**Ejemplo de comportamiento con memoria:**

```
Usuario: "Me gustan las películas de ciencia ficción"
Agente:  "Te recomiendo Interstellar..."

Usuario: "¿Y algo más antiguo?"
Agente:  "Dado que te gusta la ciencia ficción, podrías ver..."  ← recuerda
```

---

## Arquitectura

```
Usuario
  │
  ▼
chatear(session_id, mensaje)
  │
  ├── 1. obtener_historial(session_id)    → Lee Redis Cloud
  ├── 2. messages[-VENTANA:]              → Aplica ventana (últimos 10 msg)
  ├── 3. chain.invoke({historial, msg})   → Modelo Groq genera respuesta
  ├── 4. add_user_message(mensaje)        → Escribe en Redis
  └── 5. add_ai_message(respuesta)        → Escribe en Redis
```

**Estructura de Redis:**

```
Redis Cloud:
  message_store:<session_id_A>  →  historial del Usuario A
  message_store:<session_id_B>  →  historial del Usuario B
  message_store:<session_id_C>  →  historial del Usuario C
```

Cada conversación es completamente independiente.

---

## Stack tecnológico

| Componente | Tecnología |
|---|---|
| Modelo LLM | `openai/gpt-oss-120b` vía Groq (configurable con `GROQ_MODEL`) |
| Framework IA | LangChain (`langchain`, `langchain-groq`, `langchain-community`) |
| Memoria persistente | Redis Cloud (`RedisChatMessageHistory`) |
| API web | FastAPI + Uvicorn |
| Interfaz demo | Gradio |
| Entorno de desarrollo | Google Colab |
| Despliegue | Render + GitHub |

---

## Conceptos clave

| Concepto | Descripción |
|---|---|
| `session_id` | Identificador único por conversación. Cada usuario tiene el suyo |
| `RedisChatMessageHistory` | Clase de LangChain que guarda y lee el historial en Redis automáticamente |
| `MessagesPlaceholder` | "Hueco" en el template donde LangChain inserta el historial antes de enviar al modelo |
| `TTL` | Tiempo de vida de una conversación: 3600 s (1 hora) sin actividad |
| `VENTANA` | Límite de mensajes enviados al modelo por turno (10 msg = 5 turnos completos). Mantiene el costo de tokens estable |
| `add_user_message` / `add_ai_message` | Métodos para persistir cada turno en Redis |
| `historial.clear()` | Borra el historial de un usuario en Redis |

---

## Estructura del proyecto (producción)

```
agente_peliculas/
├── agente.py          # Lógica del agente: modelo, memoria Redis, función chatear()
├── main.py            # API FastAPI: endpoints /consultar y /limpiar/{session_id}
└── requirements.txt   # Dependencias para Render
```

### `agente.py`

Contiene toda la lógica de IA, independiente del framework de API:

- `obtener_modelo()` crea el cliente Groq una sola vez, la primera vez que se necesita.
- Define el `ChatPromptTemplate` con `MessagesPlaceholder` para insertar el historial.
- `obtener_historial(session_id)` conecta con Redis y retorna el historial del usuario.
- `chatear(session_id, mensaje)` ejecuta el ciclo completo y retorna respuesta + métricas.

### `main.py`

Servidor FastAPI con tres endpoints:

| Método | Endpoint | Descripción |
|---|---|---|
| `GET` | `/` | Health check — verifica que la API está activa |
| `POST` | `/consultar` | Recibe el mensaje del usuario y retorna la respuesta del agente |
| `DELETE` | `/limpiar/{session_id}` | Borra el historial de un usuario en Redis |

---

## Configuración

### Variables de entorno

| Variable | ¿Requerida? | Valor | Dónde obtenerlo |
|---|---|---|---|
| `GROQ_API_KEY` | Sí | `gsk_...` | [console.groq.com/keys](https://console.groq.com/keys) (gratis) |
| `REDIS_URL` | Sí | `redis://default:password@host:port` | Redis Cloud → tu base de datos |
| `GROQ_MODEL` | No | `openai/gpt-oss-120b` (por defecto) | [Modelos de Groq](https://console.groq.com/docs/models) |
| `ALLOWED_ORIGINS` | No | `https://misitio.com,https://www.misitio.com` (por defecto `*`) | El dominio de tu sitio web |

> `openai/gpt-oss-120b` es un modelo abierto de OpenAI **servido por Groq**: se usa con la API key de Groq, no con una de OpenAI.

> **Cambiar de modelo:** Groq retira modelos con frecuencia ([lista de retiros](https://console.groq.com/docs/deprecations)). `llama-3.3-70b-versatile` se retiró del plan gratuito el 16/08/2026. Como el modelo se define con `GROQ_MODEL`, basta con cambiar la variable en Render, sin tocar el código.

### En Google Colab

1. Panel izquierdo → ícono 🔑 **Secrets**
2. **"+ Add new secret"**
3. Agrega `GROQ_API_KEY` y `REDIS_URL`
4. Activa **"Notebook access"** en cada uno

### En Render

Configura las mismas variables en **Environment Variables** del servicio.

---

## Instalación

```bash
pip install -r requirements.txt
```

(Para la demo en Colab agrega `gradio`.)

O en Google Colab:

```bash
!pip install langchain-core langchain-groq langchain-community redis fastapi uvicorn gradio -q
```

---

## Parámetros del modelo

| Parámetro | Valor | Justificación |
|---|---|---|
| `model` | `openai/gpt-oss-120b` | Modelo abierto de 120B parámetros vía Groq (variable `GROQ_MODEL`) |
| `temperature` | `0.7` | Respuestas variadas y naturales |
| `max_tokens` | `1024` | Incluye los tokens de razonamiento de gpt-oss; la respuesta visible sigue siendo corta (máx. 3 líneas) |
| `reasoning_effort` | `low` | Respuestas rápidas — no hace falta razonar mucho para recomendar películas |
| `max_retries` | `2` | Reintento automático ante fallos de red |
| `timeout` | `30` | Tiempo máximo de espera en segundos |
| `VENTANA` | `10 mensajes` | Últimos 5 turnos completos enviados al modelo |
| `TTL` | `3600 s` | Conversación expira tras 1 hora sin actividad |

---

## Despliegue en Render

1. Subir el código a GitHub:

```bash
git config --global user.email "tu@email.com"
git config --global user.name "tu-usuario"
git remote set-url origin https://TOKEN@github.com/usuario/agente-peliculas.git
git branch -M main
git push -u origin main
```

2. En Render: crear un **Web Service** apuntando al repositorio.
3. Configurar las variables de entorno `GROQ_API_KEY` y `REDIS_URL` (y opcionalmente `GROQ_MODEL` y `ALLOWED_ORIGINS`).
4. **Build Command:** `pip install -r requirements.txt` · **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. **Versión de Python:** 3.12, fijada en el archivo `.python-version`.
6. La API queda disponible en `https://tu-servicio.onrender.com`.

---

## Endpoints de la API

### `POST /consultar`

**Request:**
```json
{
  "session_id": "abc-123",
  "mensaje": "Me gustan las películas de terror"
}
```

> `session_id` es opcional. Si no se envía, se genera uno nuevo automáticamente. El cliente debe guardarlo y enviarlo en cada mensaje siguiente.

**Response:**
```json
{
  "session_id": "abc-123",
  "respuesta": "Te recomiendo El Conjuro...",
  "mensajes_en_memoria": 4
}
```

### `DELETE /limpiar/{session_id}`

Borra el historial del usuario en Redis. El agente responderá como si fuera la primera vez.

### Errores

| Código | Cuándo |
|---|---|
| **422** | Falta el campo `mensaje` o el formato del JSON es inválido. |
| **503** | El LLM (Groq) o la memoria (Redis) no están disponibles: clave inválida, modelo retirado, límite de uso o variable de entorno faltante. El detalle queda en los logs de Render. |

---

## Gestión del costo de tokens

Sin ventana de memoria, el costo crece indefinidamente:

| Turno | Sin ventana | Con ventana (10 msg) |
|---|---|---|
| 1 | 50 tokens | 50 tokens |
| 5 | 300 tokens | 300 tokens |
| 20 | 1,500 tokens | ~600 tokens |
| 50 | 5,000+ tokens | ~600 tokens |

Con `VENTANA = 10` el costo se estabiliza en ~600 tokens independientemente de la duración de la conversación.

---

## Casos de uso para limpiar memoria

- El usuario solicita explícitamente "olvidar" lo conversado.
- La sesión expiró y el usuario regresa con una consulta nueva.
- Necesidad de reiniciar el contexto en pruebas o demos.

---

## Parte de la Ruta LangChain

Este notebook corresponde al **Nivel 4: Memory** de la ruta de aprendizaje:

```
N1: LLM Directo
N2: Prompt Templates
N3: Chains
N4: Memory  ◄ este proyecto
N5: Tools / Agents
N6: RAG
N7: RAG + Agent + Memory
```

LLM base: `openai/gpt-oss-120b` (Groq) · Entorno: Google Colab

---

## Licencia

Material educativo — Programa Beca IA Ser ANDI · Nodo EAFIT · Medellín, Colombia.
