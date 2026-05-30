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
| Modelo LLM | `llama-3.3-70b-versatile` vía Groq |
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

- Instancia el modelo Groq una sola vez al arrancar el servidor.
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

### Secretos requeridos

| Variable | Valor | Dónde obtenerlo |
|---|---|---|
| `GROQ_API_KEY` | `gsk_...` | [console.groq.com](https://console.groq.com) |
| `REDIS_URL` | `redis://default:password@host:port` | Redis Cloud → tu base de datos |

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
pip install langchain langchain-groq langchain-community redis fastapi uvicorn gradio
```

O en Google Colab:

```bash
!pip install langchain langchain-groq langchain-community redis fastapi uvicorn gradio -q
```

---

## Parámetros del modelo

| Parámetro | Valor | Justificación |
|---|---|---|
| `model` | `llama-3.3-70b-versatile` | Modelo de 70B parámetros vía Groq |
| `temperature` | `0.7` | Respuestas variadas y naturales |
| `max_tokens` | `512` | Respuestas cortas — es un chat de películas |
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
3. Configurar las variables de entorno `GROQ_API_KEY` y `REDIS_URL`.
4. Render detecta `requirements.txt` e instala las dependencias automáticamente.
5. La API queda disponible en `https://tu-servicio.onrender.com`.

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

LLM base: `gpt-4o-mini` (OpenAI) o `llama-3.3-70b-versatile` (Groq) · Entorno: Google Colab

---

## Licencia

Material educativo — Programa Beca IA Ser ANDI · Nodo EAFIT · Medellín, Colombia.
