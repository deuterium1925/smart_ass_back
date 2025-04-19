from fastapi import FastAPI
from app.api.routers import process as process_router
from app.core.config import get_settings
from app.services.vector_db import vector_db_service
from app.utils.logger import app_logger
from app.data.knowledge_base import KNOWLEDGE_BASE  # Import the dynamically loaded knowledge base
from qdrant_client.http.models import PointStruct, VectorParams, Distance
import asyncio
from typing import List

settings = get_settings()

app = FastAPI(
    title="Smart Assistant Backend API",
)

# Include API routers
app.include_router(process_router.router, prefix="/api/v1", tags=["Processing"])

@app.get("/health", tags=["Health"])
async def health_check():
    """Basic health check endpoint."""
    return {"status": "ok"}

async def generate_embeddings_batch(entries: List[dict], batch_size: int = 50) -> List[tuple]:
    """Generate embeddings for a batch of entries in parallel."""
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
    """Upsert points to Qdrant in batches."""
    for i in range(0, len(points), batch_size):
        batch = points[i:i + batch_size]
        await asyncio.to_thread(
            vector_db_service.client.upsert,
            collection_name=vector_db_service.collection_name,
            points=batch
        )
        app_logger.info(f"Upserted batch {i // batch_size + 1} with {len(batch)} points to Qdrant.")

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    app_logger.info("Starting up Smart Assistant Backend...")
    await vector_db_service.ensure_collection()
    
    try:
        # Check and log status of both collections
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

        # Log the size of the loaded knowledge base
        app_logger.info(f"Loaded {len(KNOWLEDGE_BASE)} knowledge base entries for indexing.")

        # Check if reindexing is needed based on size mismatch
        if collection_info_knowledge.points_count == len(KNOWLEDGE_BASE):
            app_logger.info(f"Collection {vector_db_service.collection_name} already has {collection_info_knowledge.points_count} points, matching knowledge base size. Skipping indexing.")
        else:
            app_logger.info(f"Collection size ({collection_info_knowledge.points_count}) does not match knowledge base size ({len(KNOWLEDGE_BASE)}), starting full reindexing...")
            # Clear the existing collection to reindex all data
            app_logger.info(f"Clearing existing collection {vector_db_service.collection_name} to reindex all data.")
            await asyncio.to_thread(
                vector_db_service.client.delete_collection,
                collection_name=vector_db_service.collection_name
            )
            await asyncio.to_thread(
                vector_db_service.client.create_collection,
                collection_name=vector_db_service.collection_name,
                vectors_config=VectorParams(size=vector_db_service.vector_size, distance=Distance.COSINE)
            )
            app_logger.info(f"Recreated collection {vector_db_service.collection_name} for fresh indexing.")

            # Generate embeddings in parallel batches
            successful_indices = 0
            failed_indices = 0
            app_logger.info(f"Generating embeddings for {len(KNOWLEDGE_BASE)} entries in parallel batches...")
            results = await generate_embeddings_batch(KNOWLEDGE_BASE, batch_size=50)
            successful_indices = len(results)
            failed_indices = len(KNOWLEDGE_BASE) - successful_indices
            app_logger.info(f"Embeddings generated: {successful_indices} successful, {failed_indices} failed.")

            # Prepare points for upserting with error handling for missing fields
            points = []
            for entry, embedding in results:
                try:
                    query_text = entry.get("query", "Unknown Query")
                    correct_answer = entry.get("correct_answer", "No content available.")
                    correct_sources = entry.get("correct_sources", "")
                    point_id = vector_db_service.generate_point_id(query_text)
                    points.append(PointStruct(
                        id=point_id,
                        vector=embedding,
                        payload={
                            "query": query_text,
                            "text": correct_answer,
                            "sources": correct_sources
                        }
                    ))
                except Exception as e:
                    app_logger.error(f"Error preparing point for query {entry.get('query', 'Unknown')[:30]}...: {str(e)}")
                    failed_indices += 1
                    successful_indices -= 1

            # Upsert points to Qdrant in batches
            if points:
                app_logger.info(f"Upserting {len(points)} points to Qdrant in batches...")
                await upsert_batch_to_qdrant(points, batch_size=100)
                app_logger.info(f"Indexing completed: {successful_indices} entries indexed, {failed_indices} entries skipped due to errors.")
            else:
                app_logger.warning("No points to upsert to Qdrant.")
    except Exception as e:
        app_logger.error(f"Failed to check or index knowledge base: {str(e)}")
    
    app_logger.info("Startup completed.")

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources on shutdown."""
    app_logger.info("Shutting down Smart Assistant Backend...")
