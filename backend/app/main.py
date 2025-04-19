from fastapi import FastAPI
from app.api.routers import process as process_router
from app.core.config import get_settings
from app.services.vector_db import vector_db_service
from app.utils.logger import app_logger
from app.data.knowledge_base import KNOWLEDGE_BASE
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
    # Existing logic (omitted for brevity)
    pass

async def upsert_batch_to_qdrant(points: List[PointStruct], batch_size: int = 100):
    # Existing logic (omitted for brevity)
    pass

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    app_logger.info("Starting up Smart Assistant Backend...")
    await vector_db_service.ensure_collection()
    
    try:
        # Check and log status of all collections
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

        # Existing logic for knowledge base indexing (omitted for brevity)
        if collection_info_knowledge.points_count == len(KNOWLEDGE_BASE):
            app_logger.info(f"Collection {vector_db_service.collection_name} already has {collection_info_knowledge.points_count} points, matching knowledge base size. Skipping indexing.")
        else:
            # Logic for reindexing knowledge base (omitted for brevity)
            pass
    except Exception as e:
        app_logger.error(f"Failed to check or index collections: {str(e)}")
    
    app_logger.info("Startup completed.")

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources on shutdown."""
    app_logger.info("Shutting down Smart Assistant Backend...")
