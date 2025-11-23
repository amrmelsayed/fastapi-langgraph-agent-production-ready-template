# FastAPI LangGraph Agent Template

A production-ready FastAPI template for building AI agent applications with LangGraph integration. This template provides a robust foundation for building scalable, secure, and maintainable AI agent services.

## 🌟 Features

- **Production-Ready Architecture**

  - FastAPI for high-performance async API endpoints with uvloop optimization
  - LangGraph integration for AI agent workflows with state persistence
  - LangSmith for LLM observability and monitoring
  - Sentry for error tracking and performance monitoring
  - Structured logging with environment-specific formatting and request context
  - Rate limiting with configurable rules per endpoint
  - MongoDB Atlas for LangGraph checkpointing and mem0ai memory storage
  - Docker and Docker Compose support
  - Prometheus metrics and Grafana dashboards for monitoring

- **AI & LLM Features**

  - Long-term memory with mem0ai and MongoDB for semantic memory storage
  - LLM Service with automatic retry logic using tenacity
  - Multiple LLM model support (GPT-4o, GPT-4o-mini, GPT-5, GPT-5-mini, GPT-5-nano)
  - Streaming responses for real-time chat interactions
  - Tool calling and function execution capabilities

- **Security**

  - JWK (JSON Web Key) authentication with external auth service
  - Client-managed conversation sessions
  - Input sanitization
  - CORS configuration
  - Rate limiting protection

- **Developer Experience**

  - Environment-specific configuration with automatic .env file loading
  - Comprehensive logging system with context binding
  - Clear project structure following best practices
  - Type hints throughout for better IDE support
  - Easy local development setup with Makefile commands
  - Automatic retry logic with exponential backoff for resilience

## 🚀 Quick Start

### Prerequisites

- Python 3.13+
- MongoDB Atlas account (for LangGraph checkpointing and mem0ai)
- External authentication service with JWKS endpoint
- Docker and Docker Compose (optional)

### Environment Setup

1. Clone the repository:

```bash
git clone <repository-url>
cd <project-directory>
```

2. Create and activate a virtual environment:

```bash
uv sync
```

3. Copy the example environment file:

```bash
cp .env.example .env.[development|staging|production] # e.g. .env.development
```

4. Update the `.env` file with your configuration (see `.env.example` for reference)

### MongoDB Atlas Setup

1. Create a MongoDB Atlas cluster at https://cloud.mongodb.com
2. Get your connection string
3. Update the MongoDB connection in your `.env` file:

```bash
MONGODB_URI=mongodb+srv://<username>:<password>@<cluster>.mongodb.net/?retryWrites=true&w=majority
```

### Authentication Setup

1. Configure your external authentication service JWKS endpoint
2. Update the authentication settings in your `.env` file:

```bash
AUTH_URL="https://your-auth-service.com"
JWT_ISSUER="https://your-auth-service.com"
JWT_AUDIENCE="your-audience"
```

### Running the Application

#### Local Development

1. Install dependencies:

```bash
uv sync
```

2. Run the application:

```bash
make [dev|staging|prod] # e.g. make dev
```

1. Go to Swagger UI:

```bash
http://localhost:8000/docs
```

#### Using Docker

1. Build and run with Docker Compose:

```bash
make docker-build-env ENV=[development|staging|production] # e.g. make docker-build-env ENV=development
make docker-run-env ENV=[development|staging|production] # e.g. make docker-run-env ENV=development
```

2. Access the monitoring stack:

```bash
# Prometheus metrics
http://localhost:9090

# Grafana dashboards
http://localhost:3000
Default credentials:
- Username: admin
- Password: admin
```

The Docker setup includes:

- FastAPI application
- Prometheus for metrics collection
- Grafana for metrics visualization
- Pre-configured dashboards for:
  - API performance metrics
  - Rate limiting statistics
  - LLM inference metrics
  - System resource usage

## 🔧 Configuration

The application uses a flexible configuration system with environment-specific settings:

- `.env.development` - Local development settings
- `.env.staging` - Staging environment settings
- `.env.production` - Production environment settings

### Environment Variables

Key configuration variables include:

```bash
# Application
APP_ENV=development
PROJECT_NAME="FastAPI LangGraph Agent"
DEBUG=true

# MongoDB (for LangGraph checkpointing and mem0ai)
MONGODB_URI=mongodb+srv://<username>:<password>@<cluster>.mongodb.net/?retryWrites=true&w=majority

# JWK Authentication
AUTH_URL="https://your-auth-service.com"
JWT_ISSUER="https://your-auth-service.com"
JWT_AUDIENCE="your-audience"

# LLM Configuration
OPENAI_API_KEY=your_openai_api_key
DEFAULT_LLM_MODEL=gpt-4o
DEFAULT_LLM_TEMPERATURE=0.7
MAX_TOKENS=4096

# Long-Term Memory
LONG_TERM_MEMORY_COLLECTION_NAME=agent_memories
LONG_TERM_MEMORY_MODEL=gpt-4o-mini
LONG_TERM_MEMORY_EMBEDDER_MODEL=text-embedding-3-small

# Observability (Optional - LangSmith)
LANGCHAIN_TRACING_V2=false  # Set to true to enable LangSmith tracing
LANGCHAIN_API_KEY=your_langsmith_api_key
LANGCHAIN_PROJECT=langgraph-fastapi-template
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com

# Rate Limiting
RATE_LIMIT_ENABLED=true
```

## 🧠 Long-Term Memory

The application includes a sophisticated long-term memory system powered by mem0ai and MongoDB:

### Features

- **Semantic Memory Storage**: Stores and retrieves memories based on semantic similarity
- **User-Specific Memories**: Each user has their own isolated memory space
- **Automatic Memory Management**: Memories are automatically extracted, stored, and retrieved
- **Vector Search**: Uses MongoDB Atlas for efficient similarity search
- **Configurable Models**: Separate models for memory processing and embeddings

### How It Works

1. **Memory Addition**: During conversations, important information is automatically extracted and stored
2. **Memory Retrieval**: Relevant memories are retrieved based on conversation context
3. **Memory Search**: Semantic search finds related memories across conversations
4. **Memory Updates**: Existing memories can be updated as new information becomes available

## 🤖 LLM Service

The LLM service provides robust, production-ready language model interactions with automatic retry logic and multiple model support.

### Features

- **Multiple Model Support**: Pre-configured support for GPT-4o, GPT-4o-mini, GPT-5, and GPT-5 variants
- **Automatic Retries**: Uses tenacity for exponential backoff retry logic
- **Reasoning Configuration**: GPT-5 models support configurable reasoning effort levels
- **Environment-Specific Tuning**: Different parameters for development vs production
- **Fallback Mechanisms**: Graceful degradation when primary models fail

### Supported Models

| Model       | Use Case                | Reasoning Effort |
| ----------- | ----------------------- | ---------------- |
| gpt-5       | Complex reasoning tasks | Medium           |
| gpt-5-mini  | Balanced performance    | Low              |
| gpt-5-nano  | Fast responses          | Minimal          |
| gpt-4o      | Production workloads    | N/A              |
| gpt-4o-mini | Cost-effective tasks    | N/A              |

### Retry Configuration

- Automatically retries on API timeouts, rate limits, and temporary errors
- **Max Attempts**: 3
- **Wait Strategy**: Exponential backoff (1s, 2s, 4s)
- **Logging**: All retry attempts are logged with context

## 📝 Advanced Logging

The application uses structlog for structured, contextual logging with automatic request tracking.

### Features

- **Structured Logging**: All logs are structured with consistent fields
- **Request Context**: Automatic binding of request_id, session_id, and user_id
- **Environment-Specific Formatting**: JSON in production, colored console in development
- **Performance Tracking**: Automatic logging of request duration and status
- **Exception Tracking**: Full stack traces with context preservation

### Logging Context Middleware

Every request automatically gets:
- Unique request ID
- User ID (from JWK token)
- Conversation ID (from client)
- Request path and method
- Response status and duration

### Log Format Standards

- **Event Names**: lowercase_with_underscores
- **No F-Strings**: Pass variables as kwargs for proper filtering
- **Context Binding**: Always include relevant IDs and context
- **Appropriate Levels**: debug, info, warning, error, exception

## ⚡ Performance Optimizations

### uvloop Integration

The application uses uvloop for enhanced async performance (automatically enabled via Makefile):

**Performance Improvements**:
- 2-4x faster asyncio operations
- Lower latency for I/O-bound tasks
- Better connection pool management
- Reduced CPU usage for concurrent requests

### Connection Pooling

- **MongoDB**: Connection pooling for LangGraph checkpointing and mem0ai
- **Redis** (optional): Connection pool for caching

### Caching Strategy

- Only successful responses are cached
- Configurable TTL based on data volatility
- Cache invalidation on updates
- Supports Redis or in-memory caching

## 🔌 API Reference

### Chat Endpoints

All chat endpoints require:
- **Authorization**: Bearer token (JWK from external auth service)
- **conversation_id**: Client-provided conversation identifier in request body

Endpoints:
- `POST /api/v1/chatbot/chat` - Send message and receive response
- `POST /api/v1/chatbot/chat/stream` - Send message with streaming response
- `GET /api/v1/chatbot/messages?conversation_id={id}` - Get conversation history
- `DELETE /api/v1/chatbot/messages?conversation_id={id}` - Clear chat history

### Health & Monitoring

- `GET /health` - Health check with service status
- `GET /metrics` - Prometheus metrics endpoint

For detailed API documentation, visit `/docs` (Swagger UI) or `/redoc` (ReDoc) when running the application.

## 📚 Project Structure

```
langgraph-fastapi-template/
├── app/
│   ├── api/
│   │   └── v1/
│   │       ├── chatbot.py           # Chat endpoints
│   │       └── api.py               # API router aggregation
│   ├── core/
│   │   ├── config.py                # Configuration management
│   │   ├── logging.py               # Logging setup
│   │   ├── metrics.py               # Prometheus metrics
│   │   ├── middleware.py            # Custom middleware
│   │   ├── limiter.py               # Rate limiting
│   │   ├── langgraph/
│   │   │   ├── graph.py             # LangGraph agent
│   │   │   └── tools.py             # Agent tools
│   │   └── prompts/
│   │       ├── __init__.py          # Prompt loader
│   │       └── system.md            # System prompts
│   ├── schemas/
│   │   ├── chat.py                  # Chat schemas
│   │   └── graph.py                 # Graph state schemas
│   ├── services/
│   │   └── llm.py                   # LLM service with retries
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── jwk_auth.py              # JWK authentication
│   │   └── graph.py                 # Graph utility functions
│   └── main.py                      # Application entry point
├── evals/
│   ├── evaluator.py                 # Evaluation logic
│   ├── main.py                      # Evaluation CLI
│   ├── metrics/
│   │   └── prompts/                 # Evaluation metric definitions
│   └── reports/                     # Generated evaluation reports
├── grafana/                         # Grafana dashboards
├── prometheus/                      # Prometheus configuration
├── scripts/                         # Utility scripts
├── docker-compose.yml               # Docker Compose configuration
├── Dockerfile                       # Application Docker image
├── Makefile                         # Development commands
├── pyproject.toml                   # Python dependencies
├── SECURITY.md                      # Security policy
└── README.md                        # This file
```

## 🛡️ Security

For security concerns, please review our [Security Policy](SECURITY.md).

## 📄 License

This project is licensed under the terms specified in the [LICENSE](LICENSE) file.

## 🤝 Contributing

Contributions are welcome! Please ensure:

1. Code follows the project's coding standards
2. All tests pass
3. New features include appropriate tests
4. Documentation is updated
5. Commit messages follow conventional commits format

## 📞 Support

For issues, questions, or contributions, please open an issue on the project repository
