"""This file contains the LangGraph Agent/workflow and interactions with the LLM."""

import asyncio
from typing import (
    AsyncGenerator,
    Optional,
)

import sentry_sdk
from asgiref.sync import sync_to_async
from langchain_core.messages import (
    BaseMessage,
    ToolMessage,
    convert_to_openai_messages,
)
from langgraph.checkpoint.mongodb import MongoDBSaver
from langgraph.graph import (
    END,
    StateGraph,
)
from langgraph.graph.state import (
    Command,
    CompiledStateGraph,
)
from langgraph.types import (
    RunnableConfig,
    StateSnapshot,
)
from mem0 import AsyncMemory
from pymongo import MongoClient

from app.core.config import (
    Environment,
    settings,
)
from app.core.langgraph.tools import tools
from app.core.logging import logger
from app.core.metrics import llm_inference_duration_seconds
from app.core.prompts import load_system_prompt
from app.schemas import (
    GraphState,
    Message,
)
from app.services.llm import llm_service
from app.utils import (
    dump_messages,
    prepare_messages,
    process_llm_response,
)


class LangGraphAgent:
    """Manages the LangGraph Agent/workflow and interactions with the LLM.

    This class handles the creation and management of the LangGraph workflow,
    including LLM interactions, database connections, and response processing.
    """

    def __init__(self):
        """Initialize the LangGraph Agent with necessary components."""
        # Use the LLM service with tools bound
        self.llm_service = llm_service
        self.llm_service.bind_tools(tools)
        self.tools_by_name = {tool.name: tool for tool in tools}
        self._graph: Optional[CompiledStateGraph] = None
        self._checkpointer: Optional[MongoDBSaver] = None
        self.memory: Optional[AsyncMemory] = None
        logger.info(
            "langgraph_agent_initialized",
            model=settings.DEFAULT_LLM_MODEL,
            environment=settings.ENVIRONMENT.value,
        )

    async def _long_term_memory(self) -> AsyncMemory:
        """Initialize the long term memory."""
        if self.memory is None:
            self.memory = await AsyncMemory.from_config(
                config_dict={
                    "vector_store": {
                        "provider": "mongodb",
                        "config": {
                            "mongo_uri": settings.MONGODB_URI,
                            "db_name": settings.MONGODB_DB_NAME,
                            "collection_name": settings.LONG_TERM_MEMORY_COLLECTION_NAME,
                        },
                    },
                    "llm": {
                        "provider": "openai",
                        "config": {"model": settings.LONG_TERM_MEMORY_MODEL},
                    },
                    "embedder": {"provider": "openai", "config": {"model": settings.LONG_TERM_MEMORY_EMBEDDER_MODEL}},
                    # "custom_fact_extraction_prompt": load_custom_fact_extraction_prompt(),
                }
            )
        return self.memory

    async def _get_checkpointer(self) -> Optional[MongoDBSaver]:
        """Get a MongoDB checkpointer using environment-specific settings.

        Returns:
            Optional[MongoDBSaver]: A MongoDB checkpointer or None if initialization fails.
        """
        if self._checkpointer is None:
            try:
                # Connect to MongoDB cluster
                client = MongoClient(settings.MONGODB_URI)

                # Initialize the MongoDB checkpointer with the client
                # The checkpointer will use the database specified in MONGODB_DB_NAME
                self._checkpointer = MongoDBSaver(client, db_name=settings.MONGODB_DB_NAME)

                logger.info(
                    "mongodb_checkpointer_created",
                    mongodb_uri=settings.MONGODB_URI,
                    mongodb_db_name=settings.MONGODB_DB_NAME,
                    environment=settings.ENVIRONMENT.value
                )
            except Exception as e:
                logger.error(
                    "mongodb_checkpointer_creation_failed",
                    error=str(e),
                    environment=settings.ENVIRONMENT.value
                )
                # In production, we might want to degrade gracefully
                if settings.ENVIRONMENT == Environment.PRODUCTION:
                    logger.warning(
                        "continuing_without_checkpointer",
                        environment=settings.ENVIRONMENT.value
                    )
                    return None
                raise e
        return self._checkpointer

    async def _get_relevant_memory(self, user_id: str, query: str) -> str:
        """Get the relevant memory for the user and query.

        Args:
            user_id (str): The user ID.
            query (str): The query to search for.

        Returns:
            str: The relevant memory.
        """
        try:
            memory = await self._long_term_memory()
            results = await memory.search(user_id=str(user_id), query=query)
            print(results)
            return "\n".join([f"* {result['memory']}" for result in results["results"]])
        except Exception as e:
            logger.error("failed_to_get_relevant_memory", error=str(e), user_id=user_id, query=query)
            return ""

    async def _update_long_term_memory(self, user_id: str, messages: list[dict], metadata: dict = None) -> None:
        """Update the long term memory.

        Args:
            user_id (str): The user ID.
            messages (list[dict]): The messages to update the long term memory with.
            metadata (dict): Optional metadata to include.
        """
        try:
            memory = await self._long_term_memory()
            await memory.add(messages, user_id=str(user_id), metadata=metadata)
            logger.info("long_term_memory_updated_successfully", user_id=user_id)
        except Exception as e:
            logger.exception(
                "failed_to_update_long_term_memory",
                user_id=user_id,
                error=str(e),
            )

    async def _chat(self, state: GraphState, config: RunnableConfig) -> Command:
        """Process the chat state and generate a response.

        Args:
            state (GraphState): The current state of the conversation.

        Returns:
            Command: Command object with updated state and next node to execute.
        """
        # Get the current LLM instance for metrics
        current_llm = self.llm_service.get_llm()
        model_name = (
            current_llm.model_name
            if current_llm and hasattr(current_llm, "model_name")
            else settings.DEFAULT_LLM_MODEL
        )

        # Add Sentry breadcrumb
        session_id = config["configurable"]["thread_id"]
        sentry_sdk.add_breadcrumb(
            category="langgraph",
            message="Processing chat node",
            level="info",
            data={
                "session_id": session_id,
                "message_count": len(state.messages),
            },
        )

        SYSTEM_PROMPT = load_system_prompt(long_term_memory=state.long_term_memory)

        # Prepare messages with system prompt
        messages = prepare_messages(state.messages, current_llm, SYSTEM_PROMPT)

        try:
            # Use LLM service with automatic retries and circular fallback
            with llm_inference_duration_seconds.labels(model=model_name).time():
                response_message = await self.llm_service.call(dump_messages(messages))

            # Process response to handle structured content blocks
            response_message = process_llm_response(response_message)

            logger.info(
                "llm_response_generated",
                session_id=config["configurable"]["thread_id"],
                model=model_name,
                environment=settings.ENVIRONMENT.value,
            )

            # Determine next node based on whether there are tool calls
            if response_message.tool_calls:
                goto = "tool_call"
            else:
                goto = END

            return Command(update={"messages": [response_message]}, goto=goto)
        except Exception as e:
            logger.error(
                "llm_call_failed_all_models",
                session_id=config["configurable"]["thread_id"],
                error=str(e),
                environment=settings.ENVIRONMENT.value,
            )
            raise Exception(f"failed to get llm response after trying all models: {str(e)}")

    # Define our tool node
    async def _tool_call(self, state: GraphState) -> Command:
        """Process tool calls from the last message.

        Args:
            state: The current agent state containing messages and tool calls.

        Returns:
            Command: Command object with updated messages and routing back to chat.
        """
        outputs = []
        for tool_call in state.messages[-1].tool_calls:
            tool_result = await self.tools_by_name[tool_call["name"]].ainvoke(tool_call["args"])
            outputs.append(
                ToolMessage(
                    content=tool_result,
                    name=tool_call["name"],
                    tool_call_id=tool_call["id"],
                )
            )
        return Command(update={"messages": outputs}, goto="chat")

    async def create_graph(self) -> Optional[CompiledStateGraph]:
        """Create and configure the LangGraph workflow.

        Returns:
            Optional[CompiledStateGraph]: The configured LangGraph instance or None if init fails
        """
        if self._graph is None:
            try:
                graph_builder = StateGraph(GraphState)
                graph_builder.add_node("chat", self._chat, ends=["tool_call", END])
                graph_builder.add_node("tool_call", self._tool_call, ends=["chat"])
                graph_builder.set_entry_point("chat")
                graph_builder.set_finish_point("chat")

                # Get MongoDB checkpointer (may be None in production if DB unavailable)
                checkpointer = await self._get_checkpointer()
                if checkpointer is None and settings.ENVIRONMENT != Environment.PRODUCTION:
                    raise Exception("MongoDB checkpointer initialization failed")

                self._graph = graph_builder.compile(
                    checkpointer=checkpointer, name=f"{settings.PROJECT_NAME} Agent ({settings.ENVIRONMENT.value})"
                )

                logger.info(
                    "graph_created",
                    graph_name=f"{settings.PROJECT_NAME} Agent",
                    environment=settings.ENVIRONMENT.value,
                    has_checkpointer=checkpointer is not None,
                )
            except Exception as e:
                logger.error("graph_creation_failed", error=str(e), environment=settings.ENVIRONMENT.value)
                # In production, we don't want to crash the app
                if settings.ENVIRONMENT == Environment.PRODUCTION:
                    logger.warning("continuing_without_graph")
                    return None
                raise e

        return self._graph

    async def get_response(
        self,
        messages: list[Message],
        session_id: str,
        user_id: Optional[str] = None,
    ) -> list[dict]:
        """Get a response from the LLM.

        Args:
            messages (list[Message]): The messages to send to the LLM.
            session_id (str): The session ID for LangSmith tracking.
            user_id (Optional[str]): The user ID for LangSmith tracking.

        Returns:
            list[dict]: The response from the LLM.
        """
        if self._graph is None:
            self._graph = await self.create_graph()

        # Set Sentry transaction name
        sentry_sdk.set_transaction_name("langgraph.get_response")

        config = {
            "configurable": {"thread_id": session_id},
            "metadata": {
                "user_id": user_id,
                "session_id": session_id,
                "environment": settings.ENVIRONMENT.value,
                "debug": settings.DEBUG,
            },
        }
        relevant_memory = (
            await self._get_relevant_memory(user_id, messages[-1].content)
        ) or "No relevant memory found."
        try:
            response = await self._graph.ainvoke(
                input={"messages": dump_messages(messages), "long_term_memory": relevant_memory},
                config=config,
            )
            # Run memory update in background without blocking the response
            asyncio.create_task(
                self._update_long_term_memory(
                    user_id, convert_to_openai_messages(response["messages"]), config["metadata"]
                )
            )
            return self.__process_messages(response["messages"])
        except Exception as e:
            # Add context before re-raising
            sentry_sdk.set_context(
                "langgraph_error",
                {
                    "session_id": session_id,
                    "user_id": user_id,
                    "message_count": len(messages),
                },
            )
            logger.error(f"Error getting response: {str(e)}")
            raise

    async def get_stream_response(
        self, messages: list[Message], session_id: str, user_id: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """Get a stream response from the LLM.

        Args:
            messages (list[Message]): The messages to send to the LLM.
            session_id (str): The session ID for the conversation.
            user_id (Optional[str]): The user ID for the conversation.

        Yields:
            str: Tokens of the LLM response.
        """
        # Set Sentry transaction name
        sentry_sdk.set_transaction_name("langgraph.get_stream_response")

        config = {
            "configurable": {"thread_id": session_id},
            "metadata": {
                "user_id": user_id,
                "session_id": session_id,
                "environment": settings.ENVIRONMENT.value,
                "debug": settings.DEBUG,
            },
        }
        if self._graph is None:
            self._graph = await self.create_graph()

        relevant_memory = (
            await self._get_relevant_memory(user_id, messages[-1].content)
        ) or "No relevant memory found."

        try:
            async for token, _ in self._graph.astream(
                {"messages": dump_messages(messages), "long_term_memory": relevant_memory},
                config,
                stream_mode="messages",
            ):
                try:
                    yield token.content
                except Exception as token_error:
                    logger.error("Error processing token", error=str(token_error), session_id=session_id)
                    # Continue with next token even if current one fails
                    continue

            # After streaming completes, get final state and update memory in background
            state: StateSnapshot = await sync_to_async(self._graph.get_state)(config=config)
            if state.values and "messages" in state.values:
                asyncio.create_task(
                    self._update_long_term_memory(
                        user_id, convert_to_openai_messages(state.values["messages"]), config["metadata"]
                    )
                )
        except Exception as stream_error:
            # Add context before re-raising
            sentry_sdk.set_context(
                "langgraph_stream_error",
                {
                    "session_id": session_id,
                    "user_id": user_id,
                    "message_count": len(messages),
                },
            )
            logger.error("Error in stream processing", error=str(stream_error), session_id=session_id)
            raise stream_error

    async def get_chat_history(self, session_id: str) -> list[Message]:
        """Get the chat history for a given thread ID.

        Args:
            session_id (str): The session ID for the conversation.

        Returns:
            list[Message]: The chat history.
        """
        if self._graph is None:
            self._graph = await self.create_graph()

        state: StateSnapshot = await sync_to_async(self._graph.get_state)(
            config={"configurable": {"thread_id": session_id}}
        )
        return self.__process_messages(state.values["messages"]) if state.values else []

    def __process_messages(self, messages: list[BaseMessage]) -> list[Message]:
        openai_style_messages = convert_to_openai_messages(messages)
        # keep just assistant and user messages
        return [
            Message(role=message["role"], content=str(message["content"]))
            for message in openai_style_messages
            if message["role"] in ["assistant", "user"] and message["content"]
        ]

    async def clear_chat_history(self, session_id: str) -> None:
        """Clear all chat history for a given thread ID.

        Args:
            session_id: The ID of the session to clear history for.

        Raises:
            Exception: If there's an error clearing the chat history.
        """
        try:
            # Get the checkpointer
            checkpointer = await self._get_checkpointer()
            if checkpointer is None:
                raise Exception("MongoDB checkpointer not available")

            # Access the underlying MongoDB database through the checkpointer's connection
            # The database name is parsed from the connection string
            db = checkpointer.db

            # Delete from checkpoints collection
            checkpoint_result = await sync_to_async(db.checkpoints.delete_many)(
                {"thread_id": session_id}
            )

            # Delete from writes collection
            writes_result = await sync_to_async(db.checkpoint_writes.delete_many)(
                {"thread_id": session_id}
            )

            logger.info(
                "chat_history_cleared",
                session_id=session_id,
                checkpoints_deleted=checkpoint_result.deleted_count,
                writes_deleted=writes_result.deleted_count
            )
        except Exception as e:
            logger.error("failed_to_clear_chat_history", error=str(e), session_id=session_id)
            raise
