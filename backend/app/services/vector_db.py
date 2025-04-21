import asyncio
import aiohttp
import hashlib
from qdrant_client import QdrantClient
from qdrant_client.http.models import PointStruct, VectorParams, Distance, FieldCondition, MatchValue
from app.core.config import get_settings
from app.utils.logger import app_logger
from typing import List, Dict, Optional
from app.models.schemas import Customer

class VectorDBService:
    """Manages interactions with Qdrant vector database for storing and retrieving knowledge base data, customer profiles, and conversation history."""
    def __init__(self):
        self.settings = get_settings()
        self.client = QdrantClient(
            url=self.settings.QDRANT_URL,
            api_key=self.settings.QDRANT_API_KEY,
            timeout=10.0
        )
        self.collection_name = self.settings.KNOWLEDGE_COLLECTION_NAME
        self.history_collection_name = "conversation_history"
        self.customers_collection_name = "customers"
        self.embedding_model = self.settings.EMBEDDING_MODEL
        self.vector_size = None  # Set dynamically after first embedding generation
        self.timeout = aiohttp.ClientTimeout(total=self.settings.REQUEST_TIMEOUT)

    async def ensure_collection(self):
        """
        Ensures the existence of collections for knowledge base, conversation history, and customer profiles in Qdrant.
        Dynamically sets vector size based on embedding model and creates payload indexes on phone_number for efficient filtering.
        """
        try:
            collections = await asyncio.to_thread(self.client.get_collections)
            collection_names = [c.name for c in collections.collections]

            # Handle knowledge base collection for storing domain-specific information
            if self.collection_name not in collection_names:
                if self.vector_size is None:
                    app_logger.info("Vector size not set, generating a sample embedding to determine dimension...")
                    sample_embedding = await self.get_embedding("тест")
                    if sample_embedding:
                        self.vector_size = len(sample_embedding)
                        app_logger.info(f"Determined vector size: {self.vector_size}")
                    else:
                        app_logger.error("Failed to generate sample embedding, defaulting to 1024")
                        self.vector_size = 1024  # Fallback vector size if embedding fails

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

            # Handle conversation history collection with index for efficient lookups by phone_number and timestamp
            if self.history_collection_name not in collection_names:
                await asyncio.to_thread(
                    self.client.create_collection,
                    collection_name=self.history_collection_name,
                    vectors_config=VectorParams(size=self.vector_size, distance=Distance.COSINE)
                )
                await asyncio.to_thread(
                    self.client.create_payload_index,
                    collection_name=self.history_collection_name,
                    field_name="phone_number",
                    field_type="keyword"
                )
                await asyncio.to_thread(
                    self.client.create_payload_index,
                    collection_name=self.history_collection_name,
                    field_name="timestamp",
                    field_type="keyword"
                )
                app_logger.info(f"Created collection {self.history_collection_name} with indexes on phone_number and timestamp")
            else:
                app_logger.debug(f"Collection {self.history_collection_name} already exists")
                # Ensure indexes exist for performance optimization
                indexes = await asyncio.to_thread(
                    self.client.get_collection,
                    collection_name=self.history_collection_name
                )
                if not any(index.field_name == "phone_number" for index in indexes.payload_schema.values()):
                    await asyncio.to_thread(
                        self.client.create_payload_index,
                        collection_name=self.history_collection_name,
                        field_name="phone_number",
                        field_type="keyword"
                    )
                    app_logger.info(f"Added index on phone_number for {self.history_collection_name}")
                if not any(index.field_name == "timestamp" for index in indexes.payload_schema.values()):
                    await asyncio.to_thread(
                        self.client.create_payload_index,
                        collection_name=self.history_collection_name,
                        field_name="timestamp",
                        field_type="keyword"
                    )
                    app_logger.info(f"Added index on timestamp for {self.history_collection_name}")


            # Handle customers collection with index for fast retrieval by phone_number
            if self.customers_collection_name not in collection_names:
                await asyncio.to_thread(
                    self.client.create_collection,
                    collection_name=self.customers_collection_name,
                    vectors_config=VectorParams(size=self.vector_size, distance=Distance.COSINE)
                )
                await asyncio.to_thread(
                    self.client.create_payload_index,
                    collection_name=self.customers_collection_name,
                    field_name="phone_number",
                    field_type="keyword"
                )
                app_logger.info(f"Created collection {self.customers_collection_name} with index on phone_number")
            else:
                app_logger.debug(f"Collection {self.customers_collection_name} already exists")
                indexes = await asyncio.to_thread(
                    self.client.get_collection,
                    collection_name=self.customers_collection_name
                )
                if not any(index.field_name == "phone_number" for index in indexes.payload_schema.values()):
                    await asyncio.to_thread(
                        self.client.create_payload_index,
                        collection_name=self.customers_collection_name,
                        field_name="phone_number",
                        field_type="keyword"
                    )
                    app_logger.info(f"Added index on phone_number for {self.customers_collection_name}")
        except Exception as e:
            app_logger.error(f"Error creating or retrieving collections in Qdrant: {e}")

    async def get_embedding(self, text: str) -> Optional[List[float]]:
        """Generate embedding for text using MWS API with validation to ensure proper vector size."""
        retries = 0
        while retries < self.settings.MAX_RETRIES:
            try:
                app_logger.debug(f"Generating embedding for text: {text[:50]}... using model {self.embedding_model}")
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
                        if not isinstance(data, dict) or "data" not in data or not data["data"]:
                            app_logger.error("MWS Embedding API response invalid or missing 'data' field")
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
                            app_logger.info(f"Set vector size to {self.vector_size} from first embedding")
                        elif len(embedding) != self.vector_size:
                            app_logger.error(f"Embedding size {len(embedding)} mismatches expected {self.vector_size}")
                            retries += 1
                            await asyncio.sleep(2 ** retries)
                            continue
                        app_logger.debug(f"Successfully generated embedding for text: {text[:50]}... (length: {len(embedding)})")
                        return embedding
                    else:
                        app_logger.warning(f"MWS Embedding API failed with status {response.status}")
                        retries += 1
                        await asyncio.sleep(2 ** retries)
            except Exception as e:
                app_logger.error(f"MWS Embedding API error for text '{text[:50]}...': {e}")
                retries += 1
                await asyncio.sleep(2 ** retries)
        app_logger.error(f"Max retries reached for embedding generation for text: {text[:30]}...")
        return None

    def generate_point_id(self, query_text: str, content_text: str = "") -> str:
        """Generate a unique ID for Qdrant points using a hash of query and content text for uniqueness."""
        combined = query_text + content_text
        return hashlib.md5(combined.encode('utf-8')).hexdigest()

    async def query_vector_db(self, query_text: str, top_k: int = 3) -> List[Dict]:
        """
        Query the vector DB for relevant documents based on text similarity for knowledge retrieval.
        Returns a list of matched documents with content and relevance scores for the Knowledge Agent.
        Optimized to retrieve only necessary payload fields.
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
            app_logger.debug(f"Retrieved {len(results)} documents from Vector DB for query: {query_text[:30]}...")
            return results
        except Exception as e:
            app_logger.error(f"Error querying Vector DB for query '{query_text[:30]}...': {e}")
            return []

    async def store_conversation_turn(self, phone_number: str, user_text: str, operator_response: str = "", timestamp: str = "") -> Optional[str]:
        """
        Store a conversation turn in the history collection for long-term memory.
        Validates customer existence to prevent orphaned entries. Returns the timestamp if successful, None otherwise.
        Strictly enforces that a customer profile must exist before storing any history.
        Assumes phone number is normalized to format 89XXXXXXXXX via model validation.
        """
        if not phone_number:
            app_logger.error("No phone number provided for storing conversation turn")
            return None

        try:
            # Strictly enforce customer existence before storing history
            customer = await self.retrieve_customer(phone_number)
            if not customer:
                app_logger.error(f"Cannot store turn: No customer found with phone number {phone_number}")
                return None

            app_logger.debug(f"Storing conversation turn for customer {phone_number}")
            content = f"User: {user_text}\nOperator: {operator_response}" if operator_response else f"User: {user_text}"
            embedding = await self.get_embedding(content)
            if embedding is None:
                app_logger.error(f"Failed to generate embedding for turn for customer {phone_number}")
                return None

            point_id = hashlib.md5(f"{phone_number}_{timestamp}_{user_text}".encode('utf-8')).hexdigest()
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
            app_logger.info(f"Stored conversation turn for customer {phone_number} at timestamp {timestamp}")
            return timestamp
        except Exception as e:
            app_logger.error(f"Error storing conversation turn for customer {phone_number} at timestamp {timestamp}: {e}")
            return None

    async def update_conversation_turn(self, phone_number: str, timestamp: str, operator_response: str) -> bool:
        """
        Update a conversation turn with the operator's response using phone_number and timestamp.
        Returns True if successful, False otherwise.
        Strictly enforces that a customer profile must exist before updating history.
        Assumes phone number is normalized to format 89XXXXXXXXX via model validation.
        Optimized to retrieve only necessary data during search.
        """
        if not phone_number or not timestamp:
            app_logger.error("No phone number or timestamp provided for updating conversation turn")
            return False

        try:
            # Strictly enforce customer existence before updating history
            customer = await self.retrieve_customer(phone_number)
            if not customer:
                app_logger.error(f"Cannot update turn: No customer found with phone number {phone_number}")
                return False

            search_result = await asyncio.to_thread(
                self.client.scroll,
                collection_name=self.history_collection_name,
                scroll_filter={
                    "must": [
                        {"key": "phone_number", "match": {"value": phone_number}},
                        {"key": "timestamp", "match": {"value": timestamp}}
                    ]
                },
                limit=1,
                with_payload=True,
                with_vectors=False  # Changed to False since vector is not used; new embedding will be generated
            )
            if not search_result[0]:
                app_logger.error(f"No conversation turn found for customer {phone_number} at timestamp {timestamp}")
                return False

            point = search_result[0][0]
            user_text = point.payload.get("user_text", "")
            content = f"User: {user_text}\nOperator: {operator_response}"
            embedding = await self.get_embedding(content)
            if embedding is None:
                app_logger.error(f"Failed to generate updated embedding for turn for customer {phone_number} at timestamp {timestamp}")
                return False

            updated_point = PointStruct(
                id=point.id,
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
                points=[updated_point]
            )
            app_logger.info(f"Updated conversation turn with operator response for customer {phone_number} at timestamp {timestamp}")
            return True
        except Exception as e:
            app_logger.error(f"Error updating conversation turn for customer {phone_number} at timestamp {timestamp}: {e}")
            return False

    async def retrieve_conversation_history(self, phone_number: str, limit: int = 10) -> List[Dict]:
        """
        Retrieve conversation history for a customer by phone_number, limited to recent turns.
        Validates customer existence and uses indexed field for performance. Sorts by timestamp for chronological order.
        Returns an empty list if no customer profile exists.
        Assumes phone number is normalized to format 89XXXXXXXXX via model validation.
        Optimized to avoid retrieving unnecessary vector data.
        Assigns sequence numbers for frontend ordering.
        """
        if not phone_number:
            app_logger.error("No phone number provided for retrieving conversation history")
            return []

        try:
            # Validate customer existence before retrieval
            customer = await self.retrieve_customer(phone_number)
            if not customer:
                app_logger.error(f"Cannot retrieve history: No customer found with phone number {phone_number}")
                return []

            app_logger.debug(f"Retrieving conversation history for customer {phone_number}")
            search_result = await asyncio.to_thread(
                self.client.scroll,
                collection_name=self.history_collection_name,
                scroll_filter={"must": [{"key": "phone_number", "match": {"value": phone_number}}]},
                limit=limit,
                with_payload=True,
                with_vectors=False  # Optimization: Avoid retrieving vectors as they are not needed for history display
            )
            history = [
                {
                    "phone_number": point.payload.get("phone_number", ""),
                    "user_text": point.payload.get("user_text", ""),
                    "operator_response": point.payload.get("operator_response", ""),
                    "timestamp": point.payload.get("timestamp", ""),
                    # Role logic: assistant if operator response exists, else user if user text exists
                    "role": (
                        "assistant" if point.payload.get("operator_response", "").strip()
                        else "user" if point.payload.get("user_text", "").strip()
                        else "unknown"
                    ),
                    "sequence_number": 0  # Placeholder, will be updated below
                }
                for point in search_result[0]
            ]
            # Log debug messages for ambiguous role assignments to monitor data consistency
            for entry in history:
                user_text_present = bool(entry["user_text"].strip())
                operator_resp_present = bool(entry["operator_response"].strip())
                if entry["role"] == "unknown":
                    app_logger.debug(f"Unknown role for history entry for customer {phone_number}: Neither user_text nor operator_response present")
                elif user_text_present and operator_resp_present and entry["role"] == "assistant":
                    app_logger.debug(f"Both fields present for history entry for customer {phone_number}: Assigned role={entry['role']} prioritizing operator_response")

            # Sort by timestamp and assign sequence numbers for frontend ordering
            history.sort(key=lambda x: x.get("timestamp", "0"), reverse=False)
            for index, entry in enumerate(history):
                entry["sequence_number"] = index + 1

            app_logger.info(f"Retrieved {len(history)} conversation turns for customer {phone_number}")
            return history
        except Exception as e:
            app_logger.error(f"Error retrieving conversation history for customer {phone_number}: {e}")
            return []

    async def upsert_customer(self, customer: Customer) -> bool:
        """
        Upsert a customer profile into the customers collection for personalized agent responses.
        Uses a dummy vector since retrieval is based on exact match via payload index for efficiency.
        Returns True if successful, False otherwise.
        Assumes phone number is normalized to format 89XXXXXXXXX via model validation.
        """
        try:
            app_logger.debug(f"Upserting customer profile for {customer.phone_number}")
            # Use a dummy vector instead of generating an embedding since retrieval is payload-based
            dummy_vector = [0.0] * self.vector_size if self.vector_size else [0.0] * 1024
            point_id = self.generate_point_id(customer.phone_number)
            # Use a dummy zero vector since Qdrant requires vectors for collections
            dummy_vector = [0.0] * self.vector_size if self.vector_size else [0.0] * 1024
            point = PointStruct(
                id=point_id,
                vector=dummy_vector,  # Dummy vector as semantic search is not used for customers
                payload=customer.dict()
            )
            await asyncio.to_thread(
                self.client.upsert,
                collection_name=self.customers_collection_name,
                points=[point]
            )
            app_logger.info(f"Successfully upserted customer profile for {customer.phone_number} with dummy vector")
            return True
        except Exception as e:
            app_logger.error(f"Error upserting customer profile for {customer.phone_number}: {e}")
            return False

    async def retrieve_customer(self, phone_number: str) -> Optional[Customer]:
        """
        Retrieve a customer profile by phone_number using indexed field for fast lookup.
        Returns Customer object if found, None otherwise.
        Assumes phone number is normalized to format 89XXXXXXXXX via model validation.
        Optimized to avoid retrieving unnecessary vector data.
        """
        if not phone_number:
            app_logger.error("No phone number provided for retrieving customer profile")
            return None

        try:
            app_logger.debug(f"Retrieving customer profile for {phone_number}")
            search_result = await asyncio.to_thread(
                self.client.scroll,
                collection_name=self.customers_collection_name,
                scroll_filter={"must": [{"key": "phone_number", "match": {"value": phone_number}}]},
                limit=1,
                with_payload=True,
                with_vectors=False  # Optimization: Avoid retrieving vectors as they are not needed for customer data
            )
            if search_result[0]:
                customer_data = search_result[0][0].payload
                app_logger.info(f"Retrieved customer profile for {phone_number}")
                return Customer(**customer_data)
            else:
                app_logger.info(f"No customer found with phone number {phone_number}")
                return None
        except Exception as e:
            app_logger.error(f"Error retrieving customer profile for {phone_number}: {e}")
            return None

    async def delete_orphaned_history(self) -> int:
        """
        Delete history entries without corresponding customer profiles to maintain data integrity.
        Returns the number of deleted entries. Enforces strict cleanup as backward compatibility is not a concern.
        This is a maintenance operation to ensure no history exists without a customer.
        Optimized to retrieve minimal data during scan.
        """
        try:
            app_logger.info("Starting strict cleanup of orphaned history entries")
            history_entries = []
            offset = None
            batch_size = 1000
            while True:
                result = await asyncio.to_thread(
                    self.client.scroll,
                    collection_name=self.history_collection_name,
                    limit=batch_size,
                    offset=offset,
                    with_payload=True,
                    with_vectors=False  # Optimization: Avoid retrieving vectors as they are not needed for cleanup
                )
                points, next_offset = result
                history_entries.extend(points)
                if not next_offset:
                    break
                offset = next_offset

            app_logger.info(f"Retrieved {len(history_entries)} history entries for orphaned check")

            deleted_count = 0
            points_to_delete = []
            for point in history_entries:
                phone_number = point.payload.get("phone_number", "")
                if not phone_number:
                    points_to_delete.append(point.id)
                    deleted_count += 1
                    app_logger.debug(f"Marked for deletion: History entry with no phone_number (ID: {point.id})")
                    continue
                customer = await self.retrieve_customer(phone_number)
                if not customer:
                    points_to_delete.append(point.id)
                    deleted_count += 1
                    app_logger.debug(f"Marked for deletion: Orphaned history entry for non-existent customer {phone_number} (ID: {point.id})")

            if points_to_delete:
                await asyncio.to_thread(
                    self.client.delete,
                    collection_name=self.history_collection_name,
                    points_selector=points_to_delete
                )
                app_logger.info(f"Strictly deleted {deleted_count} orphaned history entries without corresponding customers")
            else:
                app_logger.info("No orphaned history entries found to delete during strict cleanup")

            return deleted_count
        except Exception as e:
            app_logger.error(f"Error during strict cleanup of orphaned history entries: {e}")
            return 0

    async def delete_customer_and_history(self, phone_number: str) -> bool:
        """
        Delete a customer profile and all associated conversation history to maintain data consistency.
        Ensures that no history remains if a customer profile is deleted.
        Returns True if both customer and history are successfully deleted, False otherwise.
        Assumes phone number is normalized to format 89XXXXXXXXX via model validation.
        Optimized to retrieve minimal data during deletion.
        Handles partial failures by tracking success of each deletion step.
        """
        if not phone_number:
            app_logger.error("No phone number provided for deleting customer and history")
            return False

        try:
            # Check if customer exists
            customer = await self.retrieve_customer(phone_number)
            if not customer:
                app_logger.info(f"No customer found with phone number {phone_number} to delete")
                return False

            customer_deleted = False
            history_deleted = True  # Default to true if no history to delete

            # Delete customer profile
            customer_search = await asyncio.to_thread(
                self.client.scroll,
                collection_name=self.customers_collection_name,
                scroll_filter={"must": [{"key": "phone_number", "match": {"value": phone_number}}]},
                limit=1,
                with_payload=False,  # Optimization: Minimal data retrieval
                with_vectors=False
            )
            if customer_search[0]:
                customer_id = customer_search[0][0].id
                await asyncio.to_thread(
                    self.client.delete,
                    collection_name=self.customers_collection_name,
                    points_selector=[customer_id]
                )
                customer_deleted = True
                app_logger.info(f"Deleted customer profile for {phone_number}")
            else:
                app_logger.error(f"Failed to find customer profile for deletion for {phone_number}")
                customer_deleted = False

            # Delete all associated history entries
            history_points = []
            offset = None
            batch_size = 1000
            while True:
                result = await asyncio.to_thread(
                    self.client.scroll,
                    collection_name=self.history_collection_name,
                    scroll_filter={"must": [{"key": "phone_number", "match": {"value": phone_number}}]},
                    limit=batch_size,
                    offset=offset,
                    with_payload=False,  # Optimization: Minimal data retrieval
                    with_vectors=False
                )
                points, next_offset = result
                history_points.extend([p.id for p in points])
                if not next_offset:
                    break
                offset = next_offset

            if history_points:
                await asyncio.to_thread(
                    self.client.delete,
                    collection_name=self.history_collection_name,
                    points_selector=history_points
                )
                history_deleted = True
                app_logger.info(f"Deleted {len(history_points)} history entries for customer {phone_number}")
            else:
                app_logger.info(f"No history entries found for customer {phone_number}")
                history_deleted = True

            if not customer_deleted:
                app_logger.error(f"Failed to delete customer profile for {phone_number}, though history deletion status: {history_deleted}")
                return False
            if not history_deleted:
                app_logger.error(f"Failed to delete history for {phone_number}, though customer profile was deleted")
                return False

            return True
        except Exception as e:
            app_logger.error(f"Error deleting customer and history for {phone_number}: {e}")
            return False

vector_db_service = VectorDBService()
