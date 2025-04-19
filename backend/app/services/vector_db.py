import asyncio
import aiohttp
import hashlib
from qdrant_client import QdrantClient
from qdrant_client.http.models import PointStruct, VectorParams, Distance
from app.core.config import get_settings
from app.utils.logger import app_logger
from typing import List, Dict, Optional
from app.models.schemas import Customer

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

            # Handle knowledge base collection
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
                app_logger.info(f"Created collection {self.customers_collection_name} in Qdrant for customer profiles")
            else:
                app_logger.debug(f"Collection {self.customers_collection_name} already exists")
        except Exception as e:
            app_logger.error(f"Error creating or retrieving collections in Qdrant: {e}")

    async def get_embedding(self, text: str) -> Optional[List[float]]:
        """Generate embedding for the given text using MWS API with stricter response validation."""
        retries = 0
        while retries < self.settings.MAX_RETRIES:
            try:
                async with aiohttp.ClientSession(timeout=self.timeout) as session:
                    response = await session.post(
                        url=self.settings.MWS_EMBEDDING_URL,
                        headers={
                            "Authorization": f"Bearer {self.settings.MWS_API_KEY}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": self.embedding_model,
                            "input": text
                        }
                    )
                    if response.status == 200:
                        data = await response.json()
                        if not isinstance(data, dict):
                            app_logger.error("MWS Embedding API returned invalid response type, not a dictionary")
                            retries += 1
                            await asyncio.sleep(2 ** retries)
                            continue
                        if "data" not in data or not isinstance(data["data"], list) or len(data["data"]) == 0:
                            app_logger.error("MWS Embedding API response missing 'data' field or invalid format")
                            retries += 1
                            await asyncio.sleep(2 ** retries)
                            continue
                        if "embedding" not in data["data"][0] or not isinstance(data["data"][0]["embedding"], list):
                            app_logger.error("MWS Embedding API response missing 'embedding' field or invalid format")
                            retries += 1
                            await asyncio.sleep(2 ** retries)
                            continue
                        embedding = data["data"][0]["embedding"]
                        if not all(isinstance(x, (int, float)) for x in embedding):
                            app_logger.error("MWS Embedding API returned invalid embedding values, not all numbers")
                            retries += 1
                            await asyncio.sleep(2 ** retries)
                            continue
                        if self.vector_size is None:
                            self.vector_size = len(embedding)
                            app_logger.info(f"Set vector size dynamically to {self.vector_size} based on first embedding")
                        elif len(embedding) != self.vector_size:
                            app_logger.error(f"MWS Embedding API returned embedding of size {len(embedding)}, expected {self.vector_size}")
                            retries += 1
                            await asyncio.sleep(2 ** retries)
                            continue
                        return embedding
                    else:
                        app_logger.warning(f"MWS Embedding API call failed with status {response.status}")
                        retries += 1
                        await asyncio.sleep(2 ** retries)
            except Exception as e:
                app_logger.error(f"MWS Embedding API call error: {e}")
                retries += 1
                await asyncio.sleep(2 ** retries)
        app_logger.error(f"Max retries reached for embedding generation for text: {text[:30]}...")
        return None

    def generate_point_id(self, query_text: str) -> str:
        """Generate a unique ID for Qdrant points based on the hash of the query text."""
        return hashlib.md5(query_text.encode('utf-8')).hexdigest()

    async def query_vector_db(self, query_text: str, top_k: int = 3) -> List[Dict]:
        """
        Query the vector DB for relevant documents based on the query text using MWS embeddings.
        """
        try:
            app_logger.debug(f"Querying Vector DB for: {query_text[:30]}...")
            query_vector = await self.get_embedding(query_text)
            if query_vector is None:
                app_logger.error("Failed to generate embedding for query text")
                return []

            search_result = await asyncio.to_thread(
                self.client.search,
                collection_name=self.collection_name,
                query_vector=query_vector,
                limit=top_k,
                with_payload=True
            )
            results = [
                {
                    "id": hit.id,
                    "query": hit.payload.get("query", "unknown"),
                    "text": hit.payload.get("text", ""),
                    "score": hit.score,
                    "sources": hit.payload.get("sources", "")
                }
                for hit in search_result
            ]
            app_logger.debug(f"Retrieved {len(results)} documents from Vector DB")
            return results
        except Exception as e:
            app_logger.error(f"Error querying Vector DB: {e}")
            return []

    async def store_conversation_turn(self, phone_number: str, user_text: str, operator_response: str = "", timestamp: str = "") -> bool:
        """
        Store a single conversation turn in the history collection for long-term memory.
        Returns True if successful, False otherwise, with detailed logging for failures.
        """
        try:
            app_logger.debug(f"Storing conversation turn for customer {phone_number}")
            content = f"User: {user_text}\nOperator: {operator_response}" if operator_response else f"User: {user_text}"
            embedding = await self.get_embedding(content)
            if embedding is None:
                app_logger.error(f"Failed to generate embedding for conversation turn for customer {phone_number}")
                return False

            point_id = hashlib.md5(f"{phone_number}_{timestamp}_{content}".encode('utf-8')).hexdigest()
            point = PointStruct(
                id=point_id,
                vector=embedding,
                payload={
                    "phone_number": phone_number,
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
            app_logger.info(f"Stored conversation turn for customer {phone_number}")
            return True
        except Exception as e:
            app_logger.error(f"Error storing conversation turn for customer {phone_number}: {e}")
            return False

    async def retrieve_conversation_history(self, phone_number: str, limit: int = 10) -> List[Dict]:
        """
        Retrieve conversation history for a given phone_number from the history collection.
        Improved role determination and timestamp sorting with fallback for missing/invalid data.
        """
        try:
            app_logger.debug(f"Retrieving conversation history for customer {phone_number}")
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
                    "phone_number": point.payload.get("phone_number", ""),
                    "user_text": point.payload.get("user_text", ""),
                    "operator_response": point.payload.get("operator_response", ""),
                    "timestamp": point.payload.get("timestamp", ""),
                    # Improved role logic: Check for non-empty content
                    "role": "user" if point.payload.get("user_text", "") != ""
                            else "assistant" if point.payload.get("operator_response", "") != ""
                            else "unknown"
                }
                for point in search_result[0]  # search_result[0] contains the list of points
            ]
            # Log warnings for ambiguous roles
            for entry in history:
                if entry["role"] == "unknown":
                    app_logger.warning(f"Ambiguous role for history entry for customer {phone_number}: {entry}")

            # Sort by timestamp with fallback for missing or invalid values
            history.sort(
                key=lambda x: x.get("timestamp", "0"),  # Fallback to "0" if timestamp is missing
                reverse=False
            )
            app_logger.info(f"Retrieved {len(history)} conversation turns for customer {phone_number}")
            return history
        except Exception as e:
            app_logger.error(f"Error retrieving conversation history for customer {phone_number}: {e}")
            return []

    async def upsert_customer(self, customer: Customer) -> bool:
        """
        Upsert a customer profile into the customers collection.
        Returns True if successful, False otherwise.
        """
        try:
            app_logger.debug(f"Upserting customer profile for {customer.phone_number}")
            # Generate an embedding for the phone number or a summary of customer data
            embedding_text = f"Customer: {customer.phone_number}"
            embedding = await self.get_embedding(embedding_text)
            if embedding is None:
                app_logger.error(f"Failed to generate embedding for customer {customer.phone_number}")
                return False

            # Use hashed phone number as point ID for uniqueness
            point_id = self.generate_point_id(customer.phone_number)
            point = PointStruct(
                id=point_id,
                vector=embedding,
                payload=customer.dict()
            )
            await asyncio.to_thread(
                self.client.upsert,
                collection_name=self.customers_collection_name,
                points=[point]
            )
            app_logger.info(f"Successfully upserted customer profile for {customer.phone_number}")
            return True
        except Exception as e:
            app_logger.error(f"Error upserting customer profile for {customer.phone_number}: {e}")
            return False

    async def retrieve_customer(self, phone_number: str) -> Optional[Customer]:
        """
        Retrieve a customer profile by phone number from the customers collection.
        Returns the Customer object if found, None otherwise.
        """
        try:
            app_logger.debug(f"Retrieving customer profile for {phone_number}")
            search_result = await asyncio.to_thread(
                self.client.scroll,
                collection_name=self.customers_collection_name,
                scroll_filter={"must": [{"key": "phone_number", "match": {"value": phone_number}}]},
                limit=1,
                with_payload=True,
                with_vectors=False
            )
            if search_result[0]:  # search_result[0] contains the list of points
                customer_data = search_result[0][0].payload  # First result
                app_logger.info(f"Retrieved customer profile for {phone_number}")
                return Customer(**customer_data)
            else:
                app_logger.info(f"No customer found with phone number {phone_number}")
                return None
        except Exception as e:
            app_logger.error(f"Error retrieving customer profile for {phone_number}: {e}")
            return None

vector_db_service = VectorDBService()
