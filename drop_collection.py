import asyncio
from qdrant_client import AsyncQdrantClient
import os 
async def drop():
    qdrant_client = AsyncQdrantClient(
        url="https://3e3b954a-76d4-425b-992b-51d1b942e2dd.eu-west-1-0.aws.cloud.qdrant.io:6333", 
        api_key=os.getenv("QDRANT_API_KEY"),
    )
    collection_name = "financial_due_diligence_chunks"
    try:
        await qdrant_client.delete_collection(collection_name=collection_name)
        print(f"Collection {collection_name} deleted successfully.")
    except Exception as e:
        print(f"Error deleting collection: {e}")

if __name__ == "__main__":
    asyncio.run(drop())
