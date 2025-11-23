# Development Guide

## Development Commands

### Environment Setup
```bash
# Install dependencies (uses uv package manager)
make install

# Create environment file
cp .env.example .env.development
# Edit .env.development with your API keys and configuration
```

### Running the Application
```bash
# Development (with auto-reload and uvloop)
make dev

# Staging
make staging

# Production
make prod

# Access Swagger UI at http://localhost:8000/docs
```

### Docker Operations
```bash
# Build and run with Docker (app + PostgreSQL only)
make docker-build-env ENV=development
make docker-run-env ENV=development
make docker-logs ENV=development
make docker-stop ENV=development

# Run full stack (includes Prometheus + Grafana + cAdvisor)
make docker-compose-up ENV=development
make docker-compose-logs ENV=development
make docker-compose-down ENV=development

# Access monitoring:
# - API: http://localhost:8000
# - Prometheus: http://localhost:9090
# - Grafana: http://localhost:3000 (admin/admin)
```

### Code Quality
```bash
make lint      # Lint with ruff
make format    # Format with ruff and black
```

## Architecture Deep Dive

### Application Entry Point
- **`app/main.py`**: FastAPI app initialization with lifespan manager, middleware stack, exception handlers, and router registration

### Middleware Stack (Applied in Order)
1. **LoggingContextMiddleware** (`app/core/middleware.py`): Extracts user_id/session_id from JWT tokens and binds to logging context
2. **MetricsMiddleware** (`app/core/middleware.py`): Records HTTP request metrics (duration, status, method, endpoint)
3. **PrometheusMiddleware**: Exports metrics to `/metrics` endpoint
4. **CORSMiddleware**: Handles CORS preflight requests

### API Routes (`app/api/v1/`)
- **`auth.py`**: Registration, login, session management (JWT-based)
- **`chatbot.py`**: Chat endpoint, streaming chat, message history, history clearing
- All endpoints have rate limiting via `@limiter.limit()` decorator

### LangGraph Agent Architecture (`app/core/langgraph/graph.py`)
**Graph Workflow**:
- Two-node workflow: `chat` → `tool_call` → `chat` (conditional loop)
- **chat node**: LLM invocation with system prompt, long-term memory context, tool calling capability
- **tool_call node**: Executes tools (DuckDuckGo search) based on LLM tool calls
- **State Schema**: `app/schemas/graph.py` - messages list + request context
- **Persistence**: `AsyncPostgresSaver` checkpoints state to PostgreSQL
- **Memory Integration**: mem0ai retrieves/stores semantic memories per user
- **Resilience**: Automatic retries (tenacity), circular model fallback, streaming support

### LLM Service (`app/services/llm.py`)
- **Model Registry**: gpt-5, gpt-5-mini, gpt-5-nano, gpt-4o, gpt-4o-mini
- **Retry Logic**: 3 attempts with exponential backoff (1s → 2s → 4s)
- **Circular Fallback**: Tries next model in registry on rate limit/timeout failures
- **GPT-5 Reasoning**: Configurable reasoning effort levels (minimal, low, medium, high)

### Database Architecture

**Models** (`app/models/`):
- **User** (`user.py`): Auto-increment ID, unique email (indexed), bcrypt password, one-to-many sessions
- **Session** (`session.py`): UUID primary key, foreign key to user, optional name, timestamps

**Database Service** (`app/services/database.py`):
- Async connection pooling (configurable pool_size/max_overflow)
- Connection pre-ping for health checks
- 30-minute connection recycling
- CRUD operations for users/sessions

### Authentication Flow (`app/utils/auth.py`)
1. User registers → JWT with `user_id` in `sub` claim
2. User creates session → JWT with `session_id` in `sub` claim
3. All requests use session token: `Authorization: Bearer <token>`
4. Dependencies: `get_current_user()`, `get_current_session()` for protected routes

### Security Implementation (`app/utils/sanitization.py`)
- HTML escaping (XSS prevention)
- Script tag detection
- Null byte removal
- Bcrypt password hashing
- Password strength validation (8+ chars, uppercase, lowercase, number, special char)
- Per-endpoint rate limiting (configurable via environment)

### Logging System (`app/core/logging.py`)
- **Framework**: structlog with stdlib integration
- **Outputs**: Console (dev) + JSONL file (production)
- **Event Naming**: `lowercase_with_underscores` required
- **NO f-strings**: Pass variables as kwargs for proper filtering
- **Context Binding**: request_id, session_id, user_id auto-attached via middleware
- **Example**: `logger.info("user_login", user_id=user.id, session_id=session.id)`

### Metrics Collection (`app/core/metrics.py`)
- HTTP requests: count + duration (by method/endpoint)
- LLM inference: duration (by model)
- Database: active connection count
- Prometheus endpoint: `/metrics`

### Environment Configuration (`app/core/config.py`)
**Supported Environments**: `development`, `staging`, `production`, `test`

**Environment File Loading Order**:
1. `.env.{env}.local`
2. `.env.{env}`
3. `.env.local`
4. `.env`

**Environment Differences**:
- **Dev**: DEBUG=true, console logs, relaxed rate limits, auto-reload
- **Staging**: DEBUG=false, INFO level, moderate limits
- **Production**: DEBUG=false, WARNING level, strict limits, uvloop optimization

### Long-Term Memory (`mem0ai`)
- **Backend**: AsyncMemory with pgvector
- **Storage**: Per-user semantic memory
- **Methods**: `add()`, `get()`, `search()`, `delete()`
- **Config**: Collection name, LLM model, embedder model (via environment)
- **Usage**: Auto-retrieval during chat, background memory addition

## Key Architectural Patterns

### 1. Circular Fallback Pattern
When LLM calls fail (rate limits, timeouts), the service automatically tries the next model in the registry, cycling through all available models before final failure.

### 2. Async/Await Throughout
All I/O operations use async/await:
- Database queries (asyncpg)
- LLM calls (async clients)
- Memory operations (mem0ai async)
- Graph execution (LangGraph async)

### 3. Dependency Injection
FastAPI `Depends()` for:
- Authentication: `get_current_user`, `get_current_session`
- Services: Singleton `DatabaseService`, `LLMService`

### 4. Request-Scoped Logging
Middleware binds context (request_id, session_id, user_id) to structlog, automatically included in all log messages.

### 5. State Persistence via Checkpointing
LangGraph's `AsyncPostgresSaver` persists conversation state to PostgreSQL, enabling:
- Crash recovery
- Multi-turn conversations
- Workflow replay/debugging

## Common Development Tasks

### Adding a New API Endpoint
1. Create route in `app/api/v1/{module}.py`
2. Add rate limiting: `@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["name"][0])`
3. Define schemas in `app/schemas/`
4. Add auth if needed: `session: Session = Depends(get_current_session)`
5. Register router in `app/api/v1/api.py`

### Adding a LangGraph Tool
1. Create tool class in `app/core/langgraph/tools/` extending `BaseTool`
2. Implement `_run()` and `_arun()` methods
3. Export in `app/core/langgraph/tools/__init__.py`
4. Add to `tools` list in `app/core/langgraph/graph.py`

### Modifying Agent Behavior
- **System Prompt**: Edit `app/core/prompts/system.md`
- **Graph Structure**: Modify `app/core/langgraph/graph.py`
- **State Schema**: Update `app/schemas/graph.py` (may break checkpoints!)

### Adding an LLM Model
1. Add config to `LLMService.create_registry()` in `app/services/llm.py`
2. Set model parameters (temperature, max_tokens, reasoning effort)
3. Update `DEFAULT_LLM_MODEL` in `.env` if desired

### Extending Database Models
1. Update SQLModel in `app/models/`
2. Add methods to `DatabaseService` in `app/services/database.py`
3. Update Pydantic schemas in `app/schemas/`
4. Note: May require manual SQL migration

## Code Style Examples

### Correct Logging Pattern
```python
# CORRECT
logger.info("user_login_successful", user_id=user.id, session_id=session.id)

# INCORRECT - No f-strings
logger.info(f"User {user.id} logged in")
```

### Correct Error Handling Pattern
```python
# CORRECT - Early returns, guard clauses
async def process_chat(message: str, session: Session) -> Response:
    if not message.strip():
        raise HTTPException(status_code=400, detail="Empty message")

    if len(message) > 3000:
        raise HTTPException(status_code=400, detail="Message too long")

    # Happy path last
    return await agent.process(message, session)
```

### Correct Retry Pattern
```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10)
)
async def call_llm(prompt: str) -> str:
    return await llm.ainvoke(prompt)
```

### Correct Rate Limiting Pattern
```python
from app.core.limiter import limiter

@router.post("/chat")
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["chat"][0])
async def chat(request: Request, data: ChatRequest) -> ChatResponse:
    pass
```

## What to Modify vs. What to Avoid

### Safe to Modify
- System prompts (`app/core/prompts/`)
- Tools (`app/core/langgraph/tools/`)
- API endpoints (`app/api/v1/`)
- LLM models (`.env` files)
- Evaluation metrics (`evals/metrics/prompts/`)
- Rate limits (`.env` files)

### Avoid Modifying
- Core auth flow (security-critical)
- Middleware ordering (breaks observability)
- Database schema (breaks existing data)
- LangGraph state structure (breaks checkpoints)
- Logging configuration (structured format)

## Production Deployment

1. Set `APP_ENV=production`
2. Generate JWT secret: `openssl rand -hex 32`
3. Configure external PostgreSQL
4. Set appropriate rate limits
5. Configure LangSmith keys (optional, for observability)
6. Set up Prometheus/Grafana
7. Review CORS settings
8. Enable uvloop (via Makefile)
9. Configure log aggregation
10. Set DB pool size for load
