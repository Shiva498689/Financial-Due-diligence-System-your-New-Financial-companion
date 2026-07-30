import asyncio
from datetime import datetime
from edgar import set_identity, Company
import asyncpg
import uuid
from qdrant_client.models import PointStruct, Document, VectorParams, Distance
from qdrant_client import AsyncQdrantClient ,models
# from qdrant_client import model

    # self.DB_CONFIG = {
        #     "dbname": "financial_db",
        #     "user": "postgres",
        #     "password": "123shivadubey@gmail.com",
        #     "host": "localhost",
        #     "port": 5432
        # }
class IngestionAgent():
    def __init__(self , ticker):
        set_identity("Shiva Dubey 123shivadubey@gmail.com")

        self.qdrant_client = AsyncQdrantClient(
            url="https://3e3b954a-76d4-425b-992b-51d1b942e2dd.eu-west-1-0.aws.cloud.qdrant.io:6333", 
            api_key=os.getenv("QDRANT_API_KEY"),
            cloud_inference=True
        )
        self.embedding_model = "sentence-transformers/all-MiniLM-L6-v2"
        self.collection_name = "financial_due_diligence_chunks"
        self.TARGET_ITEMS = ["Item 1", "Item 1A", "Item 7", "Item 2", "Item 3", "Item 8", "Item 9A"]

    async def create_collection(self):
        if not await self.qdrant_client.collection_exists(collection_name=self.collection_name):
            await self.qdrant_client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=384,
                    distance=Distance.COSINE
                )
            )

            await self.qdrant_client.create_payload_index(
                collection_name=self.collection_name,
                field_name="ticker",
                field_schema=models.PayloadSchemaType.KEYWORD,
            )


    def categorize_to_due_diligence_segment(self, item_name: str, item_text: str, form_type: str) -> dict:
        segments = {
            "Company & Operational Risks": "",
            "Supply Chain & Infrastructure Health": "",
            "Consumer Health & Market Share": "",
            "Legal & Regulatory Risks": "",
            "Financial Performance & Solvency": "",
            "Corporate Governance & Structure": ""
        }
        
        if form_type == "DEF 14A":
            segments["Corporate Governance & Structure"] = item_text
            return segments

        if item_name == "Item 1A":
            segments["Company & Operational Risks"] = item_text
        elif item_name == "Item 1":
            segments["Supply Chain & Infrastructure Health"] = "Business Scope / Sourcing context: " + item_text[:len(item_text)//2]
            segments["Consumer Health & Market Share"] = "Market Strategy context: " + item_text[len(item_text)//2:]
        elif item_name == "Item 3":
            segments["Legal & Regulatory Risks"] = item_text
        elif item_name in ["Item 7", "Item 8"]:
            segments["Financial Performance & Solvency"] = item_text
        elif item_name in ["Item 2", "Item 9A"]:
            segments["Company & Operational Risks"] = f"[{item_name} Context]: " + item_text
            
        return segments
    # PROCESSING UTILITIES
    def chunk_text(self, text: str, max_chars: int = 1500, overlap: int = 150):
        chunks = []
        start = 0
        while start < len(text):
            end = start + max_chars
            chunks.append(text[start:end])
            start += (max_chars - overlap)
        return chunks

    async def save_chunks_to_db(self, data_rows):
        points = []
        for row in data_rows:
            ticker, cik, filing_type, filing_date, segment_name, sec_item, chunk = row
            points.append(
                PointStruct(
                    id=str(uuid.uuid4()),
                    payload={
                        "ticker": ticker,
                        "cik": cik,
                        "filing_type": filing_type,
                        "filing_date": str(filing_date),
                        "segment_name": segment_name,
                        "sec_item": sec_item,
                        "chunk": chunk

                    },
                    vector=Document(
                        text=chunk,
                        model=self.embedding_model
                    )
                )
            )
            
        BATCH_SIZE = 50
        for i in range(0, len(points), BATCH_SIZE):
            batch = points[i:i+BATCH_SIZE]
            try:
                await self.qdrant_client.upsert(
                    collection_name=self.collection_name,
                    points=batch
                )
                print(f"    -> Successfully inserted batch of {len(batch)} chunks to Qdrant Cloud.")
                await asyncio.sleep(2)
            except Exception as e:
                import traceback
                print(f"Qdrant insertion crash error occurred: {repr(e)}\n{traceback.format_exc()}")
    # REFACTORIZED EDGARTOOLS ORCHESTRATOR
async def get_company_async(ticker):
    return await asyncio.to_thread(Company, ticker)

async def run_ingestion_pipeline( ticker: str):
        obj = IngestionAgent(ticker)
        await obj.create_collection()
        print(f"[*] Initializing edgartools tracking for: {ticker}")
        company = await get_company_async(ticker)
        cik = company.cik
        current_year = datetime.now().year
        
        # Fetch all targeted forms via edgartools API
        filings_10k = await asyncio.to_thread(company.get_filings, form="10-K")
        filings_10q = await asyncio.to_thread(company.get_filings, form="10-Q")
        filings_def14a = await asyncio.to_thread(company.get_filings, form="DEF 14A")
        
        target_filings = []

        # 1. Gather 2 Years of 10-K
    # 1. Gather 2 Years of 10-K
        for f in filings_10k:
            f_year = f.filing_date.year  # Directly access the year property
            if (current_year - f_year) <= 2:
                target_filings.append(f)
                
        # 2. Gather 1 Year of 10-Q
        for f in filings_10q:
            f_year = f.filing_date.year  # Directly access the year property
            if (current_year - f_year) <= 1:
                target_filings.append(f)

        # 3. Gather 1 Year of DEF 14A (Proxy)
        for f in filings_def14a:
            f_year = f.filing_date.year  # Directly access the year property
            if (current_year - f_year) <= 1:
                target_filings.append(f)

        print(f"[*] Found {len(target_filings)} pristine filings via edgartools API.")

        for f in target_filings:
            print(f"[+] Processing {f.form} filed on {f.filing_date}")
            rows_to_insert = []
            
            # edgartools automatically fetches, handles rate limiting, and extracts structural objects
            filing_obj = await asyncio.to_thread(f.obj)
            
            if f.form == "DEF 14A":
                # For proxy statements, pull text directly
                text_content = await asyncio.to_thread(f.text)
                mapped_segments = obj.categorize_to_due_diligence_segment("Proxy", text_content, f.form)
                
                for segment_name, segment_content in mapped_segments.items():
                    if not segment_content: continue
                    chunks = obj.chunk_text(segment_content)
                    for chunk in chunks:
                        rows_to_insert.append((ticker, cik, f.form, f.filing_date, segment_name, "Proxy", chunk))
            
            else:
                # For 10-K and 10-Q, use edgartools native section map extraction
                for item in obj.TARGET_ITEMS:
                    try:
                        # Extracts structural sections natively by name safely without Regex hacks!
                        item_text = filing_obj[item]
                        if not item_text: continue
                        
                        mapped_segments = obj.categorize_to_due_diligence_segment(item, item_text, f.form)
                        for segment_name, segment_content in mapped_segments.items():
                            if not segment_content: continue
                            chunks = obj.chunk_text(segment_content)
                            print(f"    -> {item} mapped to {segment_name} ({len(chunks)} chunks)")
                            
                            for chunk in chunks:
                                rows_to_insert.append((ticker, cik, f.form, f.filing_date, segment_name, item, chunk))
                    except Exception as ex:
                        # Soft bypass if a specific sub-item isn't packaged in that quarter's filing 
                        continue
                        
            if rows_to_insert:
                print(f"[**] Batch inserting {len(rows_to_insert)} records into qdrant  Database.")
                await obj.save_chunks_to_db(rows_to_insert)
            await asyncio.sleep(0.1)

# if __name__ == "__main__":
#         run_ingestion_pipeline("AAPL")