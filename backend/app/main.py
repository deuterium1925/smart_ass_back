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
from typing import List, Dict, Tuple

settings = get_settings()

app = FastAPI(
    title="Smart Assistant Backend API",
    description="""
    **Smart Assistant Backend API** is a multi-agent LLM system designed to support contact center operators by processing customer queries in real-time.
    This API enables interaction with customer data and dialogue history using phone numbers as unique identifiers.
    Key features include:
    - **Customer Management**: Create and retrieve customer profiles with detailed attributes for personalized support.
    - **Dialogue Processing**: Process customer messages, retrieve conversation history, and generate tailored suggestions for operators.
    - **Personalization**: Integrate customer data (e.g., tariff plans, subscriptions) into agent suggestions for context-aware responses.
    
    All endpoints require a valid phone number as the customer identifier to ensure data consistency and integrity.
    """,
)

# Include API routers for processing and customer management
app.include_router(process_router.router, prefix="/api/v1", tags=["Processing"])
app.include_router(customers_router.router, prefix="/api/v1/customers", tags=["Customers"])

@app.get("/health", tags=["Health"])
async def health_check():
    """Verify the API's operational status with a simple health check."""
    return {"status": "ok"}

def compute_content_hash(entry: Dict) -> str:
    """Compute a unique hash of a knowledge base entry's content for versioning and comparison."""
    content = f"{entry.get('query', '')}{entry.get('correct_answer', '')}{entry.get('correct_sources', '')}"
    return hashlib.md5(content.encode('utf-8')).hexdigest()

async def generate_embeddings_batch(entries: List[Dict], batch_size: int = 50) -> List[Tuple[Dict, List[float]]]:
    """Generate embeddings for knowledge base entries in batches to optimize performance."""
    results = []
    for i in range(0, len(entries), batch_size):
        batch = entries[i:i + batch_size]
        app_logger.info(f"Generating embeddings for batch {i // batch_size + 1} ({len(batch)} entries)...")
        tasks = [vector_db_service.get_embedding(entry["query"]) for entry in batch]
        embeddings = await asyncio.gather(*tasks)
        for entry, embedding in zip(batch, embeddings):
            if embedding:
                results.append((entry, embedding))
            else:
                app_logger.warning(f"Failed to generate embedding for query: {entry.get('query', 'Unknown')[:30]}...")
        app_logger.info(f"Completed batch {i // batch_size + 1}: {len(results)} embeddings generated so far.")
    return results

async def upsert_batch_to_qdrant(points: List[PointStruct], batch_size: int = 100):
    """Upsert points to Qdrant vector database in batches for efficient storage."""
    for i in range(0, len(points), batch_size):
        batch = points[i:i + batch_size]
        await asyncio.to_thread(
            vector_db_service.client.upsert,
            collection_name=vector_db_service.collection_name,
            points=batch
        )
        app_logger.info(f"Upserted batch {i // batch_size + 1} with {len(batch)} points to Qdrant.")

async def get_existing_points() -> Dict[str, Dict]:
    """Retrieve existing points from Qdrant to compare with current knowledge base entries."""
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
            with_vectors=False
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

@app.on_event("startup")
async def startup_event():
    """
    Initialize application services on startup, including vector database collections and
    incremental indexing of the knowledge base to support real-time query processing by agents.
    Implements smart indexing by only updating new or changed entries to optimize performance.
    """
    app_logger.info("Starting up Smart Assistant Backend...")
    await vector_db_service.ensure_collection()

    try:
        # Log status of knowledge base collection
        collection_info_knowledge = await asyncio.to_thread(
            vector_db_service.client.get_collection,
            collection_name=vector_db_service.collection_name
        )
        app_logger.info(f"Collection {vector_db_service.collection_name} status: {collection_info_knowledge.points_count} points")

        # Verify specific knowledge base entry for debugging
        search_result = await asyncio.to_thread(
            vector_db_service.client.scroll,
            collection_name=vector_db_service.collection_name,
            scroll_filter={"must": [{"key": "query", "match": {"value": "Безлимит кион"}}]},
            limit=1,
            with_payload=True,
            with_vectors=False
        )
        if search_result[0]:
            app_logger.info(f"Found 'Безлимит кион' in Qdrant: {search_result[0][0].payload}")
        else:
            app_logger.warning("Did not find 'Безлимит кион' in Qdrant. Data may not be indexed properly.")

        # Log status of conversation history collection
        collection_info_history = await asyncio.to_thread(
            vector_db_service.client.get_collection,
            collection_name=vector_db_service.history_collection_name
        )
        app_logger.info(f"Collection {vector_db_service.history_collection_name} status: {collection_info_history.points_count} points")

        # Log status of customer profiles collection
        collection_info_customers = await asyncio.to_thread(
            vector_db_service.client.get_collection,
            collection_name=vector_db_service.customers_collection_name
        )
        app_logger.info(f"Collection {vector_db_service.customers_collection_name} status: {collection_info_customers.points_count} points")

        # Perform cleanup of orphaned history entries to maintain data integrity
        app_logger.info("Performing cleanup of orphaned conversation history entries...")
        deleted_count = await vector_db_service.delete_orphaned_history()
        app_logger.info(f"Cleanup completed: {deleted_count} orphaned history entries deleted.")

        # Log the total number of knowledge base entries loaded for indexing
        app_logger.info(f"Loaded {len(KNOWLEDGE_BASE)} knowledge base entries for indexing.")

        # Implement incremental indexing to update only new or changed knowledge base entries
        app_logger.info("Starting incremental indexing of knowledge base...")
        existing_points = await get_existing_points()

        # Compute hashes for current knowledge base to identify changes
        to_index = []
        kb_hashes = {}
        for entry in KNOWLEDGE_BASE:
            query_text = entry.get("query", "Unknown Query")
            content_text = entry.get("correct_answer", "No content available.")
            point_id = vector_db_service.generate_point_id(query_text, content_text)
            content_hash = compute_content_hash(entry)
            kb_hashes[point_id] = content_hash
            
            # Add to index list if new or updated
            if point_id not in existing_points:
                app_logger.debug(f"New item detected: {query_text[:30]}... (ID: {point_id})")
                to_index.append(entry)
            elif existing_points[point_id]["content_hash"] != content_hash:
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
            results = await generate_embeddings_batch(to_index, batch_size=50)
            successful_indices = len(results)
            failed_indices = len(to_index) - successful_indices
            app_logger.info(f"Embeddings generated: {successful_indices} successful, {failed_indices} failed.")

            # Prepare points for upserting with content hash for future comparison
            points = []
            for entry, embedding in results:
                try:
                    query_text = entry.get("query", "Unknown Query")
                    correct_answer = entry.get("correct_answer", "No content available.")
                    correct_sources = entry.get("correct_sources", "")
                    point_id = vector_db_service.generate_point_id(query_text, correct_answer)
                    content_hash = compute_content_hash(entry)
                    points.append(PointStruct(
                        id=point_id,
                        vector=embedding,
                        payload={
                            "query": query_text,
                            "text": correct_answer,
                            "sources": correct_sources,
                            "content_hash": content_hash  # Store hash for future comparisons
                        }
                    ))
                except Exception as e:
                    app_logger.error(f"Error preparing point for query {entry.get('query', 'Unknown')[:30]}...: {str(e)}")
                    failed_indices += 1
                    successful_indices -= 1

            # Upsert new or updated points to Qdrant in batches
            if points:
                app_logger.info(f"Upserting {len(points)} points to Qdrant in batches...")
                await upsert_batch_to_qdrant(points, batch_size=100)
                app_logger.info(f"Incremental indexing completed: {successful_indices} entries indexed, {failed_indices} entries skipped due to errors.")
            else:
                app_logger.warning("No new or updated points to upsert to Qdrant.")
        else:
            app_logger.info("No new or updated items to index. Skipping embedding and upsert steps.")

        # Handle deletion of outdated knowledge base entries no longer present in KNOWLEDGE_BASE
        points_to_delete = []
        for point_id in existing_points:
            if point_id not in kb_hashes:
                app_logger.debug(f"Item no longer in knowledge base, marking for deletion: {existing_points[point_id]['query'][:30]}... (ID: {point_id})")
                points_to_delete.append(point_id)
        if points_to_delete:
            app_logger.info(f"Deleting {len(points_to_delete)} outdated points from Qdrant.")
            await asyncio.to_thread(
                vector_db_service.client.delete,
                collection_name=vector_db_service.collection_name,
                points_selector=points_to_delete
            )
        else:
            app_logger.info("No outdated points to delete from Qdrant.")

    except Exception as e:
        app_logger.error(f"Failed to perform incremental indexing of knowledge base: {str(e)}")
    
    app_logger.info("Startup completed.")

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources and log shutdown process for the Smart Assistant Backend."""
    app_logger.info("Shutting down Smart Assistant Backend...")
