from fastapi import FastAPI
from app.api.routers import process as process_router
from app.api.routers import customers as customers_router
from app.core.config import get_settings
from app.services.vector_db import vector_db_service
from app.utils.logger import app_logger
from app.data.knowledge_base import KNOWLEDGE_BASE
from qdrant_client.http.models import PointStruct
import asyncio
import hashlib
from typing import List, Dict, Tuple, Optional

settings = get_settings()

app = FastAPI(
    title="Smart Assistant Backend API",
    description="""
    # Smart Assistant Backend API Documentation

    **Overview**: The Smart Assistant Backend API is a multi-agent LLM system designed to support contact center operators by processing customer queries in real-time. This API enables interaction with customer data and conversation history using `phone_number` (format: `89XXXXXXXXX`) as the unique identifier for customers and `timestamp` (ISO 8601 format) for individual conversation turns. The system is designed to optimize operator workflows with personalized, context-aware suggestions and quality feedback.

    ## Key Features
    - **Customer Management**: Create, retrieve, or delete customer profiles with detailed attributes for personalized support via `/api/v1/customers/create`, `/api/v1/customers/retrieve/{phone_number}`, and `/api/v1/customers/delete/{phone_number}`.
    - **Message Storage**: Store incoming user messages via `/api/v1/process`, returning a `timestamp` to reference the conversation turn. QA and Summary Agents are triggered only after an operator response is submitted.
    - **On-Demand Conversation Analysis**: Allow operators to trigger analysis by Intent, Emotion, Knowledge, and Action Suggestion Agents for specific conversation turns or recent history via `/api/v1/analyze`. This supports batch processing of multiple messages for coherent insights.
    - **Operator Response with Automated Feedback**: Submit operator responses via `/api/v1/submit_operator_response`, triggering QA and Summary Agents for immediate feedback on the response quality and conversation summary.
    - **Manual Agent Trigger**: Manually trigger QA and Summary Agents via `/api/v1/trigger_automated_agents/{phone_number}/{timestamp}` if an operator response is delayed indefinitely.
    - **Personalization**: Integrate customer data (e.g., tariff plans, subscriptions) into agent suggestions for context-aware responses tailored to individual profiles.

    ## Workflow Overview
    1. **Profile Creation**: A customer profile must be created using `/api/v1/customers/create` before any message processing or history updates can occur. The `phone_number` must be in the format `89XXXXXXXXX` (11 digits starting with 89).
    2. **Message Storage**: Incoming user messages are stored via `/api/v1/process`, returning a unique `timestamp` for the conversation turn. Automated QA and Summary Agents are **not run immediately** to ensure feedback is contextually relevant to operator input.
    3. **On-Demand Analysis**: Operators can request detailed analysis on-demand via `/api/v1/analyze`, targeting specific conversation turns (via `timestamps`) or recent history (via `history_limit`). Dependent agents (e.g., Action Suggestion) automatically run prerequisite agents (e.g., Intent, Emotion) for complete analysis.
    4. **Operator Response Submission**: Operator responses are submitted via `/api/v1/submit_operator_response`, triggering QA and Summary Agents to provide feedback and summaries based on the operator's input for the specified `timestamp`.
    5. **Manual Trigger for Delays**: If an operator response is delayed, QA and Summary Agents can be manually triggered via `/api/v1/trigger_automated_agents/{phone_number}/{timestamp}` to generate feedback without waiting for operator input.

    ## Frontend Integration Notes
    - **Strict Phone Number Format Enforcement**: The API strictly enforces the phone number format `89XXXXXXXXX` (11 digits starting with 89). International formats or other variations will be rejected with a HTTP 400 error. Ensure frontend input validation aligns with this requirement to avoid errors.
    - **Timestamp Identifier**: The `/process` endpoint returns a `timestamp` (ISO 8601 format, UTC) for each stored message, which must be used in `/analyze`, `/submit_operator_response`, or `/trigger_automated_agents` calls to reference specific conversation turns.
    - **Delayed Automated Results**: Automated results (QA, Summary) are provided **only after operator response submission** or manual triggering via `/trigger_automated_agents`. Frontend UIs must display placeholders or loading states for these results until they are available.
    - **Error Handling**: Error messages are descriptive and reference `phone_number` and `timestamp` for traceability. Status codes are used consistently (e.g., 400 for bad input like invalid phone number format, 404 for not found, 500 for server errors) to facilitate user-friendly error handling.
    - **Loading States and Triggers**: For seamless user experience, implement placeholders or loading states for QA and Summary feedback after storing a message via `/process`. Update these states once results are available via `/submit_operator_response` or `/trigger_automated_agents`. Consider polling or WebSocket integration if real-time updates are needed for delayed operator responses.

    ## API Endpoints Summary
    - **POST /api/v1/customers/create**: Create or update a customer profile with a normalized phone number (`89XXXXXXXXX`).
    - **GET /api/v1/customers/retrieve/{phone_number}**: Retrieve a customer profile by phone number.
    - **DELETE /api/v1/customers/delete/{phone_number}**: Delete a customer profile and all associated history.
    - **POST /api/v1/process**: Store a user message and return a `timestamp` for the turn (QA/Summary delayed).
    - **POST /api/v1/analyze**: Analyze conversation history for actionable insights (Intent, Emotion, Knowledge, Suggestions).
    - **POST /api/v1/submit_operator_response**: Submit operator response for a turn, triggering QA and Summary feedback.
    - **POST /api/v1/trigger_automated_agents/{phone_number}/{timestamp}**: Manually trigger QA and Summary Agents if operator response is delayed.
    - **GET /health**: Check API operational status.

    For detailed endpoint specifications, parameters, and response formats, refer to the interactive Swagger UI at `/docs` or Redoc at `/redoc`.
    """,
)

# Include API routers for processing and customer management
app.include_router(process_router.router, prefix="/api/v1", tags=["Processing"])
app.include_router(customers_router.router, prefix="/api/v1/customers", tags=["Customers"])


@app.get("/health", tags=["Health"])
async def health_check():
    """Verify the API's operational status with a simple health check endpoint."""
    return {"status": "ok"}


def compute_content_hash(entry: Dict) -> str:
    """Compute a unique hash of a knowledge base entry's content for versioning and comparison purposes."""
    content = f"{entry.get('query', '')}{entry.get('correct_answer', '')}{entry.get('correct_sources', '')}"
    return hashlib.md5(content.encode('utf-8')).hexdigest()


async def generate_embeddings_batch(entries: List[Dict], batch_size: int = 50, max_concurrent_batches: int = 5) -> List[Tuple[Dict, List[float]]]:
    """
    Generate embeddings for knowledge base entries in parallel batches to optimize performance.
    Uses a semaphore to limit concurrent batches and avoid rate limiting issues.
    """
    results = []
    semaphore = asyncio.Semaphore(max_concurrent_batches)
    
    async def process_batch(batch: List[Dict], batch_num: int):
        async with semaphore:
            app_logger.info(f"Generating embeddings for batch {batch_num} ({len(batch)} entries)...")
            tasks = [vector_db_service.get_embedding(entry["query"]) for entry in batch]
            embeddings = await asyncio.gather(*tasks)
            batch_results = []
            for entry, embedding in zip(batch, embeddings):
                if embedding:
                    batch_results.append((entry, embedding))
                else:
                    app_logger.warning(f"Failed to generate embedding for query: {entry.get('query', 'Unknown')[:30]}...")
            app_logger.info(f"Completed batch {batch_num}: {len(batch_results)} embeddings added, total so far: {len(results) + len(batch_results)}")
            return batch_results
    
    # Create tasks for batches and process them concurrently
    batches = [entries[i:i + batch_size] for i in range(0, len(entries), batch_size)]
    tasks = [process_batch(batch, i + 1) for i, batch in enumerate(batches)]
    batch_results = await asyncio.gather(*tasks)
    
    # Flatten the results from all batches
    for batch_result in batch_results:
        results.extend(batch_result)
    
    return results


async def upsert_batch_to_qdrant(points: List[PointStruct], batch_size: int = 200) -> bool:
    """
    Upsert points to Qdrant vector database in batches for efficient storage.
    Uses a larger batch size to reduce network overhead during indexing.
    Returns True if successful, False otherwise.
    """
    try:
        for i in range(0, len(points), batch_size):
            batch = points[i:i + batch_size]
            await asyncio.to_thread(
                vector_db_service.client.upsert,
                collection_name=vector_db_service.collection_name,
                points=batch
            )
            app_logger.info(f"Upserted batch {i // batch_size + 1} with {len(batch)} points to Qdrant.")
        return True
    except Exception as e:
        app_logger.error(f"Failed to upsert batch to Qdrant: {str(e)}")
        return False


async def get_existing_points() -> Dict[str, Dict]:
    """Retrieve existing points from Qdrant to compare with current knowledge base entries for incremental indexing."""
    try:
        existing_points = {}
        offset = None
        batch_size = 1000
        while True:
            result = await asyncio.to_thread(
                vector_db_service.client.scroll,
                collection_name=vector_db_service.collection_name,
                limit=batch_size,
                offset=offset,
                with_payload=True,
                with_vectors=False  # Optimization: Avoid retrieving vectors as they are not needed for comparison
            )
            points, next_offset = result
            for point in points:
                existing_points[point.id] = {
                    "content_hash": point.payload.get("content_hash", ""),
                    "query": point.payload.get("query", "Unknown")
                }
            if not next_offset:
                break
            offset = next_offset
        app_logger.info(f"Retrieved {len(existing_points)} existing points from Qdrant for comparison.")
        return existing_points
    except Exception as e:
        app_logger.error(f"Failed to retrieve existing points from Qdrant: {str(e)}")
        return {}


async def initialize_vector_db() -> bool:
    """
    Initialize vector database collections with error handling.
    Returns True if successful, False otherwise.
    """
    try:
        app_logger.info("Initializing vector database collections...")
        await vector_db_service.ensure_collection()
        
        # Log status of collections for diagnostic purposes
        collection_info_knowledge = await asyncio.to_thread(
            vector_db_service.client.get_collection,
            collection_name=vector_db_service.collection_name
        )
        app_logger.info(f"Collection {vector_db_service.collection_name} status: {collection_info_knowledge.points_count} points")
        
        collection_info_history = await asyncio.to_thread(
            vector_db_service.client.get_collection,
            collection_name=vector_db_service.history_collection_name
        )
        app_logger.info(f"Collection {vector_db_service.history_collection_name} status: {collection_info_history.points_count} points")
        
        collection_info_customers = await asyncio.to_thread(
            vector_db_service.client.get_collection,
            collection_name=vector_db_service.customers_collection_name
        )
        app_logger.info(f"Collection {vector_db_service.customers_collection_name} status: {collection_info_customers.points_count} points")
        
        app_logger.info("Vector database collections initialized successfully.")
        return True
    except Exception as e:
        app_logger.error(f"Failed to initialize vector database: {str(e)}")
        return False


async def check_critical_entries(collection_name: str, critical_keyword: str = "кион") -> bool:
    """
    Check if critical entries exist in the collection, returning False if not found.
    Uses a broader search and detailed logging to debug mismatches for critical keywords.
    Returns True if any entry partially matches the keyword (case-insensitive).
    """
    try:
        search_result = await asyncio.to_thread(
            vector_db_service.client.scroll,
            collection_name=collection_name,
            limit=200,  # Increased limit to ensure broader search
            with_payload=True,
            with_vectors=False
        )
        kion_found = False
        found_entries = []
        for point in search_result[0]:
            query_text = point.payload.get("query", "").lower()
            if critical_keyword.lower() in query_text or "kion" in query_text:
                app_logger.info(f"Found '{critical_keyword}' related entry in Qdrant: {point.payload.get('query', 'Unknown')}")
                kion_found = True
                found_entries.append(point.payload.get('query', 'Unknown'))
            else:
                app_logger.debug(f"Non-matching entry in Qdrant: {point.payload.get('query', 'Unknown')[:50]}...")
        if kion_found:
            app_logger.info(f"Total '{critical_keyword}' related entries found: {len(found_entries)} - {found_entries}")
        else:
            app_logger.warning(f"Did not find any '{critical_keyword}' or 'KION' related entries in Qdrant after checking {len(search_result[0])} entries.")
        return kion_found
    except Exception as e:
        app_logger.error(f"Error checking critical entries in Qdrant for '{critical_keyword}': {str(e)}")
        return False


async def index_knowledge_base(force_reindex: bool = False) -> bool:
    """
    Perform incremental indexing of the knowledge base with optional forced reindexing.
    Returns True if indexing is successful or partially successful, False on critical failure.
    Ensures critical entries are always indexed and adds detailed debugging for mismatches.
    Logs outdated points for review and potential future cleanup.
    """
    try:
        app_logger.info(f"Starting knowledge base indexing (force_reindex={force_reindex})...")
        collection_info = await asyncio.to_thread(
            vector_db_service.client.get_collection,
            collection_name=vector_db_service.collection_name
        )
        app_logger.info(f"Collection {vector_db_service.collection_name} status: {collection_info.points_count} points")

        app_logger.info(f"Loaded {len(KNOWLEDGE_BASE)} knowledge base entries for indexing.")
        # Log specific entries related to 'кион' for debugging purposes
        critical_keyword = "кион"
        kion_entries = [entry for entry in KNOWLEDGE_BASE if critical_keyword in entry.get("query", "").lower() or "kion" in entry.get("query", "").lower()]
        app_logger.info(f"Found {len(kion_entries)} entries related to '{critical_keyword}/KION' in KNOWLEDGE_BASE")
        for i, entry in enumerate(kion_entries):
            app_logger.info(f"Kion Entry {i+1}: Query='{entry['query']}', Content Preview='{entry['correct_answer'][:100]}...'")

        # Check for critical entries before deciding on reindexing
        critical_found = await check_critical_entries(vector_db_service.collection_name, critical_keyword)
        if not critical_found and force_reindex:
            app_logger.warning(f"Critical entries for '{critical_keyword}' missing. Forcing reindexing of knowledge base.")
            await asyncio.to_thread(
                vector_db_service.client.delete_collection,
                collection_name=vector_db_service.collection_name
            )
            await asyncio.to_thread(
                vector_db_service.client.create_collection,
                collection_name=vector_db_service.collection_name,
                vectors_config={
                    "size": vector_db_service.vector_size if vector_db_service.vector_size else 1024,
                    "distance": "Cosine"
                }
            )
            app_logger.info(f"Recreated collection {vector_db_service.collection_name} for forced reindexing.")

        # Implement incremental indexing to update only new or changed entries
        existing_points = await get_existing_points()
        to_index = []
        kb_hashes = {}
        for entry in KNOWLEDGE_BASE:
            query_text = entry.get("query", "Unknown Query")
            content_text = entry.get("correct_answer", "No content available.")
            point_id = vector_db_service.generate_point_id(query_text, content_text)
            content_hash = compute_content_hash(entry)
            kb_hashes[point_id] = content_hash
            
            # Add to index list if new, updated, critical (e.g., 'кион' related), or if forced reindexing
            if point_id not in existing_points or force_reindex or critical_keyword in query_text.lower() or "kion" in query_text.lower():
                app_logger.debug(f"Indexing item (new or critical): {query_text[:30]}... (ID: {point_id})")
                to_index.append(entry)
            elif existing_points.get(point_id, {}).get("content_hash", "") != content_hash:
                app_logger.debug(f"Updated item detected: {query_text[:30]}... (ID: {point_id})")
                to_index.append(entry)
            else:
                app_logger.debug(f"Item unchanged: {query_text[:30]}... (ID: {point_id})")

        # Log summary of incremental indexing needs
        app_logger.info(f"Incremental indexing: {len(to_index)} items to index ({len(KNOWLEDGE_BASE) - len(to_index)} unchanged).")

        # Generate embeddings only for new or updated entries to save resources
        if to_index:
            successful_indices = 0
            failed_indices = 0
            app_logger.info(f"Generating embeddings for {len(to_index)} new or updated entries in parallel batches...")
            results = await generate_embeddings_batch(to_index, batch_size=50, max_concurrent_batches=5)
            successful_indices = len(results)
            failed_indices = len(to_index) - successful_indices
            app_logger.info(f"Embeddings generated: {successful_indices} successful, {failed_indices} failed.")

            # Prepare points for upserting with content hash for future comparison
            points = []
            kion_points = []
            for entry, embedding in results:
                try:
                    query_text = entry.get("query", "Unknown Query")
                    correct_answer = entry.get("correct_answer", "No content available.")
                    correct_sources = entry.get("correct_sources", "")
                    point_id = vector_db_service.generate_point_id(query_text, correct_answer)
                    content_hash = compute_content_hash(entry)
                    point = PointStruct(
                        id=point_id,
                        vector=embedding,
                        payload={
                            "query": query_text,
                            "text": correct_answer,
                            "sources": correct_sources,
                            "content_hash": content_hash  # Store hash for future comparisons
                        }
                    )
                    points.append(point)
                    if critical_keyword in query_text.lower() or "kion" in query_text.lower():
                        kion_points.append(point)
                        app_logger.info(f"Prepared critical '{critical_keyword}' entry for upsert: {query_text}")
                except Exception as e:
                    app_logger.error(f"Error preparing point for query {entry.get('query', 'Unknown')[:30]}...: {str(e)}")
                    failed_indices += 1
                    successful_indices -= 1

            # Upsert new or updated points to Qdrant in batches
            if points:
                app_logger.info(f"Upserting {len(points)} points to Qdrant in batches, including {len(kion_points)} critical '{critical_keyword}' entries...")
                if await upsert_batch_to_qdrant(points, batch_size=200):
                    app_logger.info(f"Incremental indexing completed: {successful_indices} entries indexed, {failed_indices} entries skipped due to errors.")
                else:
                    app_logger.error("Failed to upsert points to Qdrant. Indexing incomplete.")
                    return False
            else:
                app_logger.warning("No new or updated points to upsert to Qdrant.")
        else:
            app_logger.info("No new or updated items to index. Skipping embedding and upsert steps.")

        # Log outdated points but do not delete them to prevent potential data loss
        # Instead, collect them for review or potential future cleanup
        outdated_points = []
        for point_id in existing_points:
            if point_id not in kb_hashes:
                outdated_points.append({
                    "id": point_id,
                    "query": existing_points[point_id]['query'],
                })
                app_logger.warning(f"Item no longer in knowledge base, but NOT deleting to avoid data loss: {existing_points[point_id]['query'][:30]}... (ID: {point_id})")
        if outdated_points:
            app_logger.info(f"Found {len(outdated_points)} potentially outdated points in Qdrant, but skipping deletion for safety.")
            # Log a summary of outdated points for review (could be written to a file or database for future cleanup)
            app_logger.info(f"Outdated points summary logged for review. Consider manual cleanup or backup if needed.")
            # Optionally, save outdated points IDs to a file for administrative review
            try:
                import json
                from datetime import datetime
                outdated_log_file = f"outdated_points_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                with open(outdated_log_file, 'w', encoding='utf-8') as f:
                    json.dump(outdated_points, f, ensure_ascii=False, indent=2)
                app_logger.info(f"Outdated points details saved to {outdated_log_file} for review.")
            except Exception as e:
                app_logger.warning(f"Could not save outdated points to file: {str(e)}")
        else:
            app_logger.info("No potentially outdated points found in Qdrant.")

        # Final check post-indexing for critical entries with broader search to ensure data integrity
        critical_found_post = await check_critical_entries(vector_db_service.collection_name, critical_keyword)
        if not critical_found_post:
            app_logger.warning(f"Post-indexing check: No '{critical_keyword}/KION' related entries found in Qdrant even after reindexing. Check embedding generation, storage logic, or Qdrant data. API will still start.")
            app_logger.warning("Continuing startup despite missing critical entries to avoid blocking API.")
            return True

        app_logger.info(f"Knowledge base indexing successful with critical '{critical_keyword}' entries confirmed.")
        return True
    except Exception as e:
        app_logger.error(f"Failed to perform incremental indexing of knowledge base: {str(e)}")
        app_logger.warning("Continuing startup despite indexing failure to avoid blocking API.")
        return True  # Changed to True to avoid blocking startup on indexing errors

async def cleanup_orphaned_history() -> bool:
    """
    Perform strict cleanup of orphaned conversation history entries to maintain data integrity.
    Returns True if successful, False otherwise.
    """
    try:
        app_logger.info("Performing strict cleanup of orphaned conversation history entries...")
        deleted_count = await vector_db_service.delete_orphaned_history()
        app_logger.info(f"Strict cleanup completed: {deleted_count} orphaned history entries deleted.")
        return True
    except Exception as e:
        app_logger.error(f"Error during strict cleanup of orphaned history entries: {str(e)}")
        return False


@app.on_event("startup")
async def startup_event():
    """
    Initialize essential application services on startup with modularized operations.
    Handles vector database setup, knowledge base indexing, and data cleanup with robust error handling.
    Ensures partial initialization does not prevent API from starting unless critical failures occur.
    """
    app_logger.info("Starting up Smart Assistant Backend...")
    startup_success = True

    # Step 1: Initialize vector database collections (critical)
    if not await initialize_vector_db():
        app_logger.error("Critical failure: Vector database initialization failed. API may not function correctly.")
        startup_success = False

    # Step 2: Index knowledge base (non-critical, can retry later if fails)
    if startup_success and not await index_knowledge_base(force_reindex=False):
        app_logger.warning("Knowledge base indexing failed. API can still operate with existing data.")
        startup_success = False

    # Step 3: Cleanup orphaned history (non-critical, can be deferred)
    if startup_success and not await cleanup_orphaned_history():
        app_logger.warning("Orphaned history cleanup failed. Data integrity may be compromised but API remains functional.")
        startup_success = False

    # Finalize startup status
    if startup_success:
        app_logger.info("Startup completed successfully.")
    else:
        app_logger.warning("Startup completed with partial failures. Check logs for details.")


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources and log the shutdown process for the Smart Assistant Backend."""
    app_logger.info("Shutting down Smart Assistant Backend...")
