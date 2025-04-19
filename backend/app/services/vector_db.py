import asyncio
import aiohttp
import hashlib
from qdrant_client import QdrantClient
from qdrant_client.http.models import PointStruct, VectorParams, Distance
from app.core.config import get_settings
from app.utils.logger import app_logger
from typing import List, Dict, Optional

class VectorDBService:
    def __init__(self):
        self.settings = get_settings()
        self.client = QdrantClient(
            url=self.settings.QDRANT_URL,
            api_key=self.settings.QDRANT_API_KEY,
            timeout=10.0
        )
        self.collection_name = self.settings.KNOWLEDGE_COLLECTION_NAME
        self.history_collection_name = "conversation_history"
        self.customers_collection_name = "customers"  # New collection for customer data
        self.embedding_model = self.settings.EMBEDDING_MODEL
        self.vector_size = None  # Will be set dynamically after first embedding
        self.timeout = aiohttp.ClientTimeout(total=self.settings.REQUEST_TIMEOUT)

    async def ensure_collection(self):
        """Ensure the knowledge base, history, and customers collections exist in Qdrant with dynamic vector size."""
        try:
            collections = await asyncio.to_thread(self.client.get_collections)
            collection_names = [c.name for c in collections.collections]

            # Handle knowledge base collection (existing logic)
            if self.collection_name not in collection_names:
                if self.vector_size is None:
                    app_logger.info("Vector size not set, generating a sample embedding to determine dimension...")
                    sample_embedding = await self.get_embedding("тест")
                    if sample_embedding:
                        self.vector_size = len(sample_embedding)
                        app_logger.info(f"Determined vector size: {self.vector_size}")
                    else:
                        app_logger.error("Failed to generate sample embedding, defaulting to 1024")
                        self.vector_size = 1024  # Fallback value

                await asyncio.to_thread(
                    self.client.create_collection,
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(size=self.vector_size, distance=Distance.COSINE)
                )
                app_logger.info(f"Created collection {self.collection_name} in Qdrant with vector size {self.vector_size}")
            else:
                app_logger.debug(f"Collection {self.collection_name} already exists")
                if self.vector_size is None:
                    collection_info = await asyncio.to_thread(
                        self.client.get_collection,
                        collection_name=self.collection_name
                    )
                    self.vector_size = collection_info.config.params.vectors.size
                    app_logger.info(f"Retrieved vector size from existing collection: {self.vector_size}")

            # Handle conversation history collection
            if self.history_collection_name not in collection_names:
                await asyncio.to_thread(
                    self.client.create_collection,
                    collection_name=self.history_collection_name,
                    vectors_config=VectorParams(size=self.vector_size, distance=Distance.COSINE)
                )
                app_logger.info(f"Created collection {self.history_collection_name} in Qdrant for conversation history")
            else:
                app_logger.debug(f"Collection {self.history_collection_name} already exists")

            # Handle customers collection
            if self.customers_collection_name not in collection_names:
                await asyncio.to_thread(
                    self.client.create_collection,
                    collection_name=self.customers_collection_name,
                    vectors_config=VectorParams(size=self.vector_size, distance=Distance.COSINE)
                )
                app_logger.info(f"Created collection {self.customers_collection_name} in Qdrant for customer data")
            else:
                app_logger.debug(f"Collection {self.customers_collection_name} already exists")

        except Exception as e:
            app_logger.error(f"Error creating or retrieving collections in Qdrant: {e}")

    # Existing methods like get_embedding, query_vector_db remain unchanged

    async def store_conversation_turn(self, phone_number: str, user_text: str, operator_response: str = "", timestamp: str = "") -> bool:
        """
        Store a single conversation turn in the history collection for long-term memory using phone_number.
        Returns True if successful, False otherwise, with detailed logging for failures.
        """
        try:
            app_logger.debug(f"Storing conversation turn for phone_number {phone_number}")
            content = f"User: {user_text}\nOperator: {operator_response}" if operator_response else f"User: {user_text}"
            embedding = await self.get_embedding(content)
            if embedding is None:
                app_logger.error(f"Failed to generate embedding for conversation turn for phone_number {phone_number}")
                return False

            point_id = hashlib.md5(f"{phone_number}_{timestamp}_{content}".encode('utf-8')).hexdigest()
            point = PointStruct(
                id=point_id,
                vector=embedding,
                payload={
                    "phone_number": phone_number,  # Replace session_id with phone_number
                    "user_text": user_text,
                    "operator_response": operator_response,
                    "timestamp": timestamp,
                    "content": content
                }
            )
            await asyncio.to_thread(
                self.client.upsert,
                collection_name=self.history_collection_name,
                points=[point]
            )
            app_logger.info(f"Stored conversation turn for phone_number {phone_number}")
            return True
        except Exception as e:
            app_logger.error(f"Error storing conversation turn for phone_number {phone_number}: {e}")
            return False

    async def retrieve_conversation_history(self, phone_number: str, limit: int = 10) -> List[Dict]:
        """
        Retrieve conversation history for a given phone_number from the history collection.
        Improved role determination and timestamp sorting with fallback for missing/invalid data.
        """
        try:
            app_logger.debug(f"Retrieving conversation history for phone_number {phone_number}")
            search_result = await asyncio.to_thread(
                self.client.scroll,
                collection_name=self.history_collection_name,
                scroll_filter={"must": [{"key": "phone_number", "match": {"value": phone_number}}]},
                limit=limit,
                with_payload=True,
                with_vectors=False
            )
            history = [
                {
                    "user_text": point.payload.get("user_text", ""),
                    "operator_response": point.payload.get("operator_response", ""),
                    "timestamp": point.payload.get("timestamp", ""),
                    "role": "user" if point.payload.get("user_text", "") != ""
                            else "assistant" if point.payload.get("operator_response", "") != ""
                            else "unknown"
                }
                for point in search_result[0]  # search_result[0] contains the list of points
            ]
            # Log warnings for ambiguous roles
            for entry in history:
                if entry["role"] == "unknown":
                    app_logger.warning(f"Ambiguous role for history entry for phone_number {phone_number}: {entry}")

            # Sort by timestamp with fallback for missing or invalid values
            history.sort(
                key=lambda x: x.get("timestamp", "0"),  # Fallback to "0" if timestamp is missing
                reverse=False
            )
            app_logger.info(f"Retrieved {len(history)} conversation turns for phone_number {phone_number}")
            return history
        except Exception as e:
            app_logger.error(f"Error retrieving conversation history for phone_number {phone_number}: {e}")
            return []

vector_db_service = VectorDBService()