# import os
# import re
# import time
# import requests
# from datetime import datetime
# from bs4 import BeautifulSoup
# import psycopg2
# from psycopg2.extras import execute_values

# # CONFIGURATION & CREDENTIALS
# # ==========================================
# # SEC requirements state you must declare a user-agent string containing Company Name & Email
# SEC_HEADERS = {
#     "User-Agent": "Shiva Dubey 123shivadubey@gmail.com",
#     "Accept-Encoding": "gzip, deflate"
# }

# MODAL_ENDPOINT_URL = "https://shivadubey--qwen-7b-summarizer-qwenmodel-summarize.modal.run"

# DB_CONFIG = {
#     "dbname": "financial_db",
#     "user": "postgres",
#     "password": "123shivadubey@gmail.com",
#     "host": "localhost",
#     "port": 5432
# }

# TARGET_ITEMS = ["Item 1", "Item 1A", "Item 7", "Item 2", "Item 3", "Item 8", "Item 9A"]

# # SEC FETCHING ENGINE
# # ==========================================
# def get_cik_from_ticker(ticker: str) -> str:
#     """Fetches the 10-digit padded CIK string for a given stock ticker."""
#     url = "https://www.sec.gov/files/company_tickers.json"
#     res = requests.get(url, headers=SEC_HEADERS)
#     res.raise_for_status()
#     data = res.json()
    
#     for item in data.values():
#         if item["ticker"].upper() == ticker.upper():
#             return str(item["cik_str"]).zfill(10)
#     raise ValueError(f"Ticker {ticker} not found in SEC database.")

# def fetch_filings_metadata(cik: str):
#     """Retrieves metadata for all historical submissions for a given CIK."""
#     url = f"https://data.sec.gov/submissions/CIK{cik}.json"
#     res = requests.get(url, headers=SEC_HEADERS)
#     res.raise_for_status()
#     return res.json()

# def extract_filing_urls(cik: str, metadata: dict, target_ticker: str):
#     """Filters metadata to extract URLs for 2 years of 10-K, 1 year of 10-Q, and DEF 14A."""
#     current_year = datetime.now().year
#     recent_filings = metadata["filings"]["recent"]
    
#     selected_filings = []
    
#     for i in range(len(recent_filings["accessionNumber"])):
#         f_type = recent_filings["form"][i]
#         f_date_str = recent_filings["filingDate"][i]
#         f_date = datetime.strptime(f_date_str, "%Y-%m-%d")
#         f_year = f_date.year
        
#         acc_num = recent_filings["accessionNumber"][i].replace("-", "")
#         doc_name = recent_filings["primaryDocument"][i]
        
#         # Build document retrieval URL
#         filing_url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc_num}/{doc_name}"
        
#         is_target = False
#         if f_type == "10-K" and (current_year - f_year) <= 2:
#             is_target = True
#         elif f_type == "10-Q" and (current_year - f_year) <= 1:
#             is_target = True
#         elif f_type == "DEF 14A" and (current_year - f_year) <= 1:
#             is_target = True
            
#         if is_target:
#             selected_filings.append({
#                 "ticker": target_ticker,
#                 "cik": cik,
#                 "type": f_type,
#                 "date": f_date_str,
#                 "url": filing_url
#             })
            
#     return selected_filings

# # PARSING & SEGREGATION LOGIC
# # ==========================================
# def clean_and_parse_html(html_content: str) -> str:
#     """Removes messy inline styles, scripts, and normalizes whitespaces from HTML filings."""
#     soup = BeautifulSoup(html_content, "lxml")
#     for element in soup(["script", "style", "table"]): 
#         element.decompose() # Dropping giant raw data tables to preserve semantic text tokens
#     text = soup.get_text(separator="\n")
#     # Normalize spacing variations
#     text = re.sub(r'\s+', ' ', text)
#     return text

# def extract_sec_items(full_text: str, form_type: str) -> dict:
#     """
#     Attempts to segment the document by Item sections using Regex anchor points.
#     Fails softly back to full document processing if sections are strictly obscured.
#     """
#     extracted_sections = {}
#     if form_type == "DEF 14A":
#         return {"Proxy Statement": full_text}

#     # Generate lookahead boundaries for explicit items
#     for item in TARGET_ITEMS:
#         # Match variations of 'Item X.' or 'Item X ' at paragraph baselines
#         pattern = rf"(?:{item}\.?\s+)(.*?)(?=Item\s+\d+[A-Z]?\.?\s+|$)"
#         match = re.search(pattern, full_text, re.IGNORECASE | re.DOTALL)
#         if match:
#             extracted_sections[item] = match.group(1).strip()
#         else:
#             extracted_sections[item] = "" # Item missing or undetected in this iteration
            
#     return extracted_sections

# def categorize_to_due_diligence_segment(item_name: str, item_text: str, form_type: str) -> dict:
#     """
#     Allocates filing components natively into specific Due Diligence domains.
#     Expands categorization beyond 4 requested baselines up to 6 distinct target pillars.
#     """
#     segments = {
#         "Company & Operational Risks": "",
#         "Supply Chain & Infrastructure Health": "",
#         "Consumer Health & Market Share": "",
#         "Legal & Regulatory Risks": "",
#         "Financial Performance & Solvency": "",
#         "Corporate Governance & Structure": ""
#     }
    
#     if form_type == "DEF 14A":
#         segments["Corporate Governance & Structure"] = item_text
#         return segments

#     # Itemized rule mapping
#     if item_name == "Item 1A":
#         segments["Company & Operational Risks"] = item_text
#     elif item_name == "Item 1":
#         # Business Overview usually details core operational structures and markets
#         segments["Supply Chain & Infrastructure Health"] = "Business Scope / Sourcing context: " + item_text[:len(item_text)//2]
#         segments["Consumer Health & Market Share"] = "Market Strategy context: " + item_text[len(item_text)//2:]
#     elif item_name == "Item 3":
#         segments["Legal & Regulatory Risks"] = item_text
#     elif item_name in ["Item 7", "Item 8"]:
#         segments["Financial Performance & Solvency"] = item_text
#     elif item_name in ["Item 2", "Item 9A"]:
#         segments["Company & Operational Risks"] = f"[{item_name} Context]: " + item_text
        
#     return segments

# # PROCESSING PIPELINE: CHUNKING & INFERENCE
# # ==========================================
# def chunk_text(text: str, max_chars: int = 4000, overlap: int = 400):
#     """Splits text into contextually viable, overlapping character groups."""
#     chunks = []
#     start = 0
#     while start < len(text):
#         end = start + max_chars
#         chunks.append(text[start:end])
#         start += (max_chars - overlap)
#     return chunks

# def call_qwen_summarizer(chunk_text: str) -> str:
#     """Executes network request to the remote Modal container housing Qwen 7B."""
#     try:
#         response = requests.post(MODAL_ENDPOINT_URL, json={"text": chunk_text}, timeout=60)
#         if response.status_with == 200:
#             return response.json().get("summary", "Summary processing error.")
#         else:
#             print(f"Inference warning, non-200 output received: {response.text}")
#             return "[Error: Dynamic reduction skipped]"
#     except Exception as e:
#         print(f"Failed to communicate with Modal endpoint: {e}")
#         return "[Error: Pipeline Connection Failure]"

# # DATA WRITER (POSTGRESQL)
# # ==========================================
# def save_chunks_to_db(data_rows):
#     """Performs continuous transactional bulk insertions into local DB instance."""
#     query = """
#         INSERT INTO financial_due_diligence_chunks 
#         (ticker, cik, filing_type, filing_date, segment_name, sec_item, original_chunk, summary_bullet_points)
#         VALUES %s;
#     """
#     conn = None
#     try:
#         conn = psycopg2.connect(**DB_CONFIG)
#         cur = conn.cursor()
#         execute_values(cur, query, data_rows)
#         conn.commit()
#         cur.close()
#     except Exception as e:
#         print(f"Database insertion crash error occurred: {e}")
#         if conn:
#             conn.rollback()
#     finally:
#         if conn:
#             conn.close()

# # PIPELINE ORCHESTRATOR
# # ==========================================
# def run_ingestion_pipeline(ticker: str):
#     print(f"[*] Initializing pipeline tracking for: {ticker}")
#     cik = get_cik_from_ticker(ticker)
#     print(f"[*] Resolved active CIK string: {cik}")
    
#     metadata = fetch_filings_metadata(cik)
#     target_filings = extract_filing_urls(cik, metadata, ticker)
#     print(f"[*] Found {len(target_filings)} relevant SEC matches across the designated timeframe criteria.")
    
#     for f in target_filings:
#         print(f"[+] Downloading file details: {f['type']} filed on {f['date']} ({f['url']})")
#         res = requests.get(f["url"], headers=SEC_HEADERS)
        
#         # Guard against hitting rate limits aggressively on SEC endpoints
#         time.sleep(0.11) 
#         if res.status_code != 200:
#             print(f"[-] Bypassing file download block; status code: {res.status_code}")
#             continue
            
#         raw_text = clean_and_parse_html(res.text)
#         sections = extract_sec_items(raw_text, f["type"])
        
#         rows_to_insert = []
        
#         for item_name, item_text in sections.items():
#             if not item_text:
#                 continue
                
#             # Classify raw segments into explicit financial targets
#             mapped_segments = categorize_to_due_diligence_segment(item_name, item_text, f["type"])
            
#             for segment_name, segment_content in mapped_segments.items():
#                 if not segment_content:
#                     continue
                
#                 # Split content down into semantic processing slices
#                 chunks = chunk_text(segment_content)
#                 print(f"    -> Processing internal section [{item_name}] mapped to [{segment_name}]. Splitting into {len(chunks)} text chunks...")
                
#                 for idx, chunk in enumerate(chunks):
#                     # Request dense 75% compressed key performance indicators/bullet summaries
#                     summary_bullets = call_qwen_summarizer(chunk)
                    
#                     # Store data row definition matching relational database entity
#                     rows_to_insert.append((
#                         f["ticker"],
#                         f["cik"],
#                         f["type"],
#                         f["date"],
#                         segment_name,
#                         item_name if f["type"] != "DEF 14A" else "Proxy",
#                         chunk,
#                         summary_bullets
#                     ))
                    
#         # Commit chunks batch-by-batch per complete filing to safe-keep RAM resources
#         if rows_to_insert:
#             print(f"[**] Committing {len(rows_to_insert)} generated paired blocks cleanly into Database.")
#             save_chunks_to_db(rows_to_insert)

# if __name__ == "__main__":
#     # Execute extraction target parameters
#     # Input example ticker list to run sequence pipelines sequentially
#     target_company_ticker = "AAPL" 
#     run_ingestion_pipeline(target_company_ticker)
import time
import requests
from datetime import datetime
from edgar import set_identity, Company
import psycopg2
from psycopg2.extras import execute_values

# CONFIGURATION & CREDENTIALS
# ==========================================

set_identity("Shiva Dubey 123shivadubey@gmail.com")

MODAL_ENDPOINT_URL = "https://shivadubey--qwen-7b-summarizer-qwenmodel-summarize.modal.run"

DB_CONFIG = {
    "dbname": "financial_db",
    "user": "postgres",
    "password": "123shivadubey@gmail.com",
    "host": "localhost",
    "port": 5432
}

TARGET_ITEMS = ["Item 1", "Item 1A", "Item 7", "Item 2", "Item 3", "Item 8", "Item 9A"]
# FINANCIAL DUE DILIGENCE SEGREGATION
# ==========================================
def categorize_to_due_diligence_segment(item_name: str, item_text: str, form_type: str) -> dict:
    """Allocates filing pieces cleanly into 6 custom diligence buckets."""
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
# ==========================================
def chunk_text(text: str, max_chars: int = 4000, overlap: int = 400):
    chunks = []
    start = 0
    while start < len(text):
        end = start + max_chars
        chunks.append(text[start:end])
        start += (max_chars - overlap)
    return chunks

def call_qwen_summarizer(chunk_text: str) -> str:
    try:
        response = requests.post(MODAL_ENDPOINT_URL, json={"text": chunk_text}, timeout=600)
        if response.status_code == 200:
            return response.json().get("summary", "Summary processing error.")
        return "[Error: Dynamic reduction skipped]"
    except Exception as e:
        print(f"Failed to communicate with Modal endpoint: {e}")
        return "[Error: Pipeline Connection Failure]"

def save_chunks_to_db(data_rows):
    query = """
        INSERT INTO financial_due_diligence_chunks 
        (ticker, cik, filing_type, filing_date, segment_name, sec_item, original_chunk, summary_bullet_points)
        VALUES %s;
    """
    conn = None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        execute_values(cur, query, data_rows)
        conn.commit()
        cur.close()
    except Exception as e:
        print(f"Database insertion crash error occurred: {e}")
        if conn: conn.rollback()
    finally:
        if conn: conn.close()
# REFACTORIZED EDGARTOOLS ORCHESTRATOR
# ==========================================
def run_ingestion_pipeline(ticker: str):
    print(f"[*] Initializing edgartools tracking for: {ticker}")
    company = Company(ticker)
    cik = company.cik
    current_year = datetime.now().year
    
    # Fetch all targeted forms via edgartools API
    filings_10k = company.get_filings(form="10-K")
    filings_10q = company.get_filings(form="10-Q")
    filings_def14a = company.get_filings(form="DEF 14A")
    
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
        filing_obj = f.obj()
        
        if f.form == "DEF 14A":
            # For proxy statements, pull text directly
            text_content = f.text()
            mapped_segments = categorize_to_due_diligence_segment("Proxy", text_content, f.form)
            
            for segment_name, segment_content in mapped_segments.items():
                if not segment_content: continue
                chunks = chunk_text(segment_content)
                for chunk in chunks:
                    summary_bullets = call_qwen_summarizer(chunk)
                    rows_to_insert.append((ticker, cik, f.form, f.filing_date, segment_name, "Proxy", chunk, summary_bullets))
        
        else:
            # For 10-K and 10-Q, use edgartools native section map extraction
            for item in TARGET_ITEMS:
                try:
                    # Extracts structural sections natively by name safely without Regex hacks!
                    item_text = filing_obj.extract_section(item)
                    if not item_text: continue
                    
                    mapped_segments = categorize_to_due_diligence_segment(item, item_text, f.form)
                    for segment_name, segment_content in mapped_segments.items():
                        if not segment_content: continue
                        chunks = chunk_text(segment_content)
                        print(f"    -> {item} mapped to {segment_name} ({len(chunks)} chunks)")
                        
                        for chunk in chunks:
                            summary_bullets = call_qwen_summarizer(chunk)
                            rows_to_insert.append((ticker, cik, f.form, f.filing_date, segment_name, item, chunk, summary_bullets))
                except Exception as ex:
                    # Soft bypass if a specific sub-item isn't packaged in that quarter's filing 
                    continue
                    
        if rows_to_insert:
            print(f"[**] Batch inserting {len(rows_to_insert)} records into local Database.")
            save_chunks_to_db(rows_to_insert)
        time.sleep(0.1) # Courteous breathing room for your Modal endpoint tasks

if __name__ == "__main__":
    run_ingestion_pipeline("AAPL")