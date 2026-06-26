
import os
import json

from langgraph.graph import StateGraph, END
from sentence_transformers import SentenceTransformer
import re
import time
import psycopg2
import numpy as np
from typing_extensions import TypedDict
from typing import List, Dict, Any, Literal
import warnings
warnings.filterwarnings("ignore", category=FutureWarning)
local_embedder = SentenceTransformer('all-MiniLM-L6-v2')
from edgar import Company, set_identity
set_identity("Shiva Dubey 123shivadubey@gmail.com")
from groq import Groq
GROQ_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"
API_KEYS = [
    "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",
    "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"
]

current_key_index = 0
groq_client = Groq(api_key=API_KEYS[current_key_index])

def switch_api_key():
    global current_key_index, groq_client
    current_key_index = (current_key_index + 1) % len(API_KEYS)
    print(f"\n    [!] Quota Limit Reached: Switching to API Key #{current_key_index + 1}...")
    groq_client = Groq(api_key=API_KEYS[current_key_index])

def execute_groq_call(prompt: str, temperature: float = 0.0, response_format=None, system_directive: str = None) -> str:
    max_retries = len(API_KEYS) * 2
    for attempt in range(max_retries):
        try:
            messages = []
            if system_directive:
                messages.append({"role": "system", "content": system_directive})
            messages.append({"role": "user", "content": prompt})
            kwargs = {
                "model": GROQ_MODEL,
                "messages": messages,
                "temperature": temperature,
                # "max_tokens": ______
            }
            if response_format:
                kwargs["response_format"] = response_format
                
            response = groq_client.chat.completions.create(**kwargs)
            return response.choices[0].message.content
        except Exception as e:
            error_msg = str(e).lower()
            if "429" in error_msg or "quota" in error_msg or "exhausted" in error_msg or "rate_limit" in error_msg:
                switch_api_key()
                time.sleep(4)
            else:
                switch_api_key()
                time.sleep(2)
    raise Exception("Execution Error: All available Groq endpoints are exhausted.")
DILIGENCE_QUESTIONS = [
    "Strategic Moat & Disruption: How does management qualitatively define their long-term competitive moat and strategic defenses against emerging technological or low-cost disruptors?",
    "Consumer Shift Rationale: What specific narrative explanations does management provide for recent structural shifts in consumer preferences, behavior, or product mix demand?",
    "Pricing Power Execution: What is the company's explicit strategy for managing pricing adjustments under inflationary pressures, and how is customer volume elasticity characterized?",
    "Underpenetrated Growth Vectors: How does the company define its qualitative value proposition and expansion roadmap for newly targeted or underpenetrated market segments?",
    "M&A Integration Friction: What operational challenges, culture clashes, or timeline delays did management encounter during recent corporate restructurings or post-merger integrations?",
    "FX Operational Adaptation: Beyond financial hedging instruments, what structural adjustments (such as local sourcing or localized pricing) is the company executing to manage foreign currency volatility?",
    "Incentive Compensation Alignment: How are executive incentive metrics and performance targets qualitatively structured to align leadership with long-term enterprise value creation over short-term earnings?",
    "Human Capital & Labor Vitality: What does the human capital disclosure reveal about the health of labor relations, employee turnover risks, and the company's ability to retain highly specialized talent?",
    "Key-Person & Succession Risk: To what extent does the business suffer from founder-led dependency, key-person risk, or structural gaps in executive succession planning?",
    "Board Oversight of Emerging Technology: How are the board of directors and executive committees explicitly structured to oversee data privacy, cybersecurity governance, and artificial intelligence adoption?",
    "Related-Party Transaction Risks: What qualitative descriptions are provided around related-party transactions involving executives or major shareholders that could indicate governance conflicts?",
    "ESG & Decarbonization Mandates: How does management characterize environmental compliance costs, carbon reduction goals, or climate transit risks as drivers of fundamental capital allocation shifts?",
    "Single-Source Sourcing Chokepoints: What specific component or raw material dependencies are highlighted where the company relies on a single or sole-source vendor without immediate alternatives?",
    "Logistics & Manufacturing Concentration: How does the company describe the physical and geographic concentration of its internal manufacturing facilities or outsourced third-party logistics hubs?",
    "Raw Material Scarcity Strategies: What narrative details are provided regarding long-term procurement contract negotiations, raw material scarcity, or structural leverage shifts in favor of suppliers?",
    "Intellectual Property & Patent Horizons: How does the company characterize its structural reliance on third-party licenses, proprietary patents, and the qualitative threat of impending patent expirations?",
    "Vendor Switching Frictions: What qualitative operational complexities, data migration issues, or financial switching costs are cited as barriers to changing major cloud, SaaS, or infrastructure vendors?",
    "Geopolitical & Trade Tariff Exposure: How is management actively modifying its footprint to mitigate sovereign interventions, cross-border trade friction, local protectionism, or international tariffs?",
    "Brand-Damaging Litigation: What is the qualitative substance of active lawsuits, class-actions, or intellectual property disputes that pose material threats to brand equity or operational continuity?",
    "Data Privacy Regulatory Shocks: How does the company assess its ongoing compliance vulnerabilities and exposure to changing cross-border data protection frameworks like GDPR, CCPA, or localized privacy mandates?",
    "Legacy Environmental Liabilities: What specific qualitative exposures exist regarding historical environmental remediation mandates, toxic waste site cleanups, or outstanding EPA violations?",
    "Uncertain Tax Positions & Audits: What narrative rationale is provided for unrecognized tax benefits, pending international transfer pricing audits, or the potential loss of regional tax holidays?",
    "Internal Controls Weakness Root Causes: What specific root causes, structural deficiencies, or cultural factors are cited by management for any identified material weaknesses in internal controls over financial reporting?",
    "Anti-Bribery & FCPA Exposures: How does the company manage, police, and describe its regulatory compliance risks regarding the Foreign Corrupt Practices Act (FCPA) within high-risk emerging markets?",
    "Post-Closing Strategic Shifts: What subsequent events disclosures indicate post-period asset divestitures, material debt issuances, or strategic execution changes not captured in the core financial tables?",
    "Risk Factor Narrative Evolution: How has the ordering, framing, or inclusion of top-tier risk factors evolved over the past fiscal periods to reflect emerging operational or systemic threats?",
    "Product Recalls & Safety Inquiries: What qualitative disclosures are provided regarding ongoing product safety testing, consumer recalls, federal safety probes, or product liability claims?",
    "Capital Allocation Philosophy Nuances: How does management describe its qualitative framework for balancing shareholder return programs (buybacks/dividends) against capital reinvestment into business preservation?",
    "Restrictive Covenant Bottlenecks: What qualitative operating restrictions, negative pledges, or strategic bottlenecks are imposed on management by current credit agreements and debt covenants?",
    "Labor Disruption & Unionization Threats: How does management characterize its exposure to active labor organizing, collective bargaining timelines, or the structural threat of strikes and work stoppages?"
]

RETRIEVAL_STATEMENTS = [
    "Narrative disclosures in the Business Description or MD&A outlining competitive landscape defenses, entry barriers, disruptive technology responses, and unique market differentiation.",
    "Management commentary in MD&A explaining shift drivers in consumer preferences, consumption habits, volume adjustments, and product mix alterations.",
    "MD&A discussion of pricing strategies, implementation schedules, input cost pass-through capabilities, and qualitative consumer volume responses to price hikes.",
    "Strategic growth vectors, commercial expansion blueprints, customer value propositions, and market penetration targeting details in Item 1 or Item 7.",
    "Restructuring disclosures, merger integration friction points, synergy capture execution updates, and post-merger operational alignment descriptions in the footnotes or MD&A.",
    "Qualitative descriptions of supply chain relocation, localized sourcing initiatives, structural price adjustments, or operational changes deployed to mitigate foreign currency transaction impacts.",
    "Proxy Statement (Def 14A) or Item 11 disclosures concerning executive short-term and long-term incentive award metrics, qualitative performance scorecards, and clawback triggers.",
    "Human capital management summaries, workforce turnover statistics narrative, employee relations disclosures, collective bargaining descriptions, and talent recruitment strategies under Item 1.",
    "Risk factor text or corporate governance listings identifying key-person dependencies, single-executive risk, founder exit exposure, or executive succession vulnerabilities.",
    "Corporate governance, proxy disclosures, or Risk Factor statements outlining board-level oversight setups for data security, digital infrastructure vulnerabilities, and generative AI adoption rules.",
    "Footnote disclosures or proxy items summarizing transactions with related entities, executive-owned vendor arrangements, conflict of interest declarations, and evaluation controls.",
    "Sustainability disclosures, climate transition risk adjustments, regulatory carbon constraints, and capital deployment impacts caused by environmental mandates within MD&A or Risk Factors.",
    "Risk Factor or Business section notifications highlighting single-source raw material vendors, sole component manufacturing agreements, and supply chain single-points-of-failure.",
    "Item 2 properties summaries or operational overviews outlining manufacturing plant concentrations, logistics hub singlepoints, or centralized distribution choke points.",
    "MD&A descriptions of vendor concentration risk, long-term procurement purchase commitments, material availability issues, and structural procurement bargaining power shifts.",
    "Item 1 Business summaries regarding active patent portfolios, license agreement durations, key patent cliff horizons, cross-licensing dependencies, and IP enforcement litigation.",
    "Risk disclosures concerning software-as-a-service vendor migrations, core database switching friction, proprietary tech infrastructure dependencies, and vendor lock-in exposures.",
    "Geopolitical disruption disclosures, trade policy adaptations, tariff impact mitigations, international factory re-shoring initiatives, and sovereign risk mitigation commentary.",
    "Item 3 Legal Proceedings narratives or contingency footnotes outlining class-action lawsuits, regulatory enforcement proceedings, intellectual property challenges, and estimated loss narratives.",
    "Risk Factor or regulatory compliance segments detailing exposure to global privacy regimes, data processing liabilities, cross-border transfer compliance tracking, and security posture overhauls.",
    "Commitments and contingencies footnotes or legal summaries highlighting Superfund site designations, environmental clean-up remediation liabilities, and open regulatory compliance actions.",
    "Income tax footnote text describing unrecognized tax distributions, deferred assets valuations allowances, ongoing IRS or foreign audits, and tax mitigation status.",
    "Item 9A or Item 4 internal control evaluations detailing identified material weaknesses, control environment deficiencies, and management's programmatic remediation narratives.",
    "Risk factors or legal disclosures concerning Foreign Corrupt Practices Act (FCPA) tracking systems, anti-corruption investigation updates, and emerging market regulatory enforcement risk.",
    "Subsequent Events footnotes detailing unrecorded asset sales, newly entered material credit agreements, ongoing structural re-organizations, or post-balance sheet liability events.",
    "Comparative textual review of Item 1A Risk Factors highlighting newly introduced, escalated, or structurally re-worded systemic, industry, or operational risk items.",
    "Warranty reserves footnotes, MD&A safety adjustments, or legal updates regarding product liability lawsuits, federal safety agency recalls, or product design vulnerabilities.",
    "MD&A Liquidity and Capital Resources statements defining corporate cash priorities, balance between equity repurchases vs capital expenditures, and strategic investment criteria.",
    "Debt footnote provisions, financing lines agreements text, or MD&A descriptions detailing negative covenants, operational flexibility caps, or leverage covenant limits.",
    "Risk items or Business section segments detailing union organizing activities, ongoing collective bargaining renewal timetables, and potential labor strike exposures."
]
def get_embedding(text: str) -> list:
    return local_embedder.encode(text).tolist()
def cosine_similarity(v1, v2) -> float:
    return float(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))) if np.linalg.norm(v1) > 0 else 0.0
def get_db_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"), database=os.getenv("DB_NAME", "postgres"),
        user=os.getenv("DB_USER", "postgres"), password=os.getenv("DB_PASSWORD", "123shivadubey@gmail.com"),
        port=os.getenv("DB_PORT", "5432")
    )
def execute_quant_extraction_pipeline(ticker: str) -> Dict[str, Any]:
   
    quant_registry = {}
    try:
        company = Company(ticker)
        tenk_filings = company.get_filings(form="10-K").head(1)
        target_sections = {
            "Item 2": "Properties & Footprint Data",
            "Item 7": "MD&A Variance Metrics",
            "Item 8": "Core GAAP Financial Metrics",
            "Item 11": "Executive Compensation Structure",
            "Item 12": "Beneficial Ownership Shares"
        }
        if len(tenk_filings) > 0:
            tenk = tenk_filings[0].obj()
            for item_key, explanation in target_sections.items():
                try:
                    section_raw = tenk[item_key]
                    if section_raw:
                        clean_section = re.sub(r'<[^>]+>', ' ', section_raw)
                        clean_section = re.sub(r'\s+', ' ', clean_section)[0:10000] # Safe slice to protect context window
                        
                        extraction_prompt = f"""You are a specialized quantitative parser. Identify the most critical numerical values, dollar metrics, rates, counts, or balances within this SEC {item_key} data.
                        For every major value extracted, provide a strict 1-line context explanation.
                        OUTPUT COMPLYING TO THE FOLLOWING JSON OBJECT FORMAT:
                        {{"metrics": [{{"value": "string representing number/percentage", "explanation": "1-line description of what this metric represents"}}]}}
                        DATA TEXT:
                        {clean_section}"""
                        time.sleep(1.5)
                        raw_json_res = execute_groq_call(
                            prompt=extraction_prompt, 
                            temperature=0.0, 
                            response_format={"type": "json_object"},
                            system_directive="You output strict financial JSON models. No markdown text formatting allowed."
                        )
                        parsed_metrics = json.loads(raw_json_res)
                        quant_registry[item_key] = parsed_metrics.get("metrics", [])
                except Exception as ex:
                    quant_registry[item_key] = [{"value": "Extraction Timeout/Failed", "explanation": str(ex)[:60]}]
        print(f"    [+] Pulling supplemental corporate Proxy disclosures (DEF 14A)...")
        proxy_filings = company.get_filings(form="DEF 14A").head(1)
        if len(proxy_filings) > 0:
            try:
                proxy_txt = proxy_filings[0].obj().text
                clean_proxy = re.sub(r'<[^>]+>', ' ', proxy_txt)
                clean_proxy = re.sub(r'\s+', ' ', clean_proxy)[:10000] # Figuring out to do more number of tokens restricted to 1000 because of api limit issues .
                
                proxy_prompt = f"""Parse the critical numerical values for executive cash packages, total stock allocation values, and clawback parameters from this DEF 14A snippet. Provide a strict 1-line explanation for each metric.
                OUTPUT FORMAT: {{"metrics": [{{"value": "value", "explanation": "1-line context"}}]}}
                TEXT: {clean_proxy}"""
                
                time.sleep(1.5)
                proxy_json_res = execute_groq_call(prompt=proxy_prompt, temperature=0.0, response_format={"type": "json_object"})
                quant_registry["DEF 14A"] = json.loads(proxy_json_res).get("metrics", [])
            except Exception:
                quant_registry["DEF 14A"] = [{"value": "Not Found/Omitted", "explanation": "Proxy data incorporated inside Part III of 10-K or delayed filing."}]
        else:
             quant_registry["DEF 14A"] = [{"value": "Unavailable", "explanation": "No distinct DEF 14A form resolved via EDGAR indexing."}]
             
    except Exception as e:
        print(f"*****Quant Execution Error for {ticker}: {e}")
        
    return quant_registry
def gather_general_narrative_text(ticker: str) -> str:
    combined_text = ""
    try:
        company = Company(ticker)
        tenk_filings = company.get_filings(form="10-K").head(1)
        if len(tenk_filings) > 0:
            tenk = tenk_filings[0].obj()

            for item in ["Item 1", "Item 1A", "Item 7","Item 2" , "Item 3" , "Item 8" , "Item 9A"]:
                try:
                    section_content = tenk[item]
                    if section_content:
                        combined_text += f"\n--- 10-K {item} ---\n{section_content}\n"
                except Exception:
                    pass
    except Exception:
        pass
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', combined_text))
def chunk_and_vectorize(raw_text: str, max_words: int = 100) -> tuple[List[str], List[Any]]:
    if not raw_text.strip():
        return ["No narrative file context found."], [get_embedding("Empty standard text context.")]
    raw_sentences = raw_text.split('. ')
    chunks, current_chunk, current_words = [], [], 0
    for sentence in raw_sentences:
        sentence = sentence.strip()
        if not sentence: continue
        words_count = len(sentence.split())
        if current_words + words_count > max_words:
            chunks.append(". ".join(current_chunk) + ".")
            current_chunk = [sentence]
            current_words = words_count
        else:
            current_chunk.append(sentence)
            current_words += words_count
    if current_chunk: chunks.append(". ".join(current_chunk) + ".")
    return chunks, [get_embedding(c) for c in chunks]
def retrieve_top_k_chunks(retrieval_query: str, chunks: List[str], embeddings: List[Any], k: int = 3) -> List[str]:
    q_vec = get_embedding(retrieval_query)
    scored_chunks = []
    for idx, c_vec in enumerate(embeddings):
        sim = cosine_similarity(q_vec, c_vec)
        if sim > 0.280:
            scored_chunks.append((sim, chunks[idx]))
    scored_chunks.sort(key=lambda x: x[0], reverse=True)
    return [c[1] for c in scored_chunks[:k]]
class ConsumerQuantState(TypedDict):
    target_embeddings: List[Any]
    competitor_embeddings: List[Any]
    target_quant_pipeline_data: Dict[str, Any]
    competitor_quant_pipeline_data: Dict[str, Any]
    current_company: Literal["target", "competitor"]
    target_ticker: str
    competitor_ticker: str
    target_chunks: List[str]
    competitor_chunks: List[str]
    q_index: int
    target_answers: Dict[str, Any]
    competitor_answers: Dict[str, Any]
    final_report: str

def ingest_and_quant_pipeline_node(state: ConsumerQuantState):
    t_quant = execute_quant_extraction_pipeline(state['target_ticker'])
    c_quant = execute_quant_extraction_pipeline(state['competitor_ticker'])
    t_raw = gather_general_narrative_text(state['target_ticker'])
    c_raw = gather_general_narrative_text(state['competitor_ticker'])
    
    t_chunks, t_embeds = chunk_and_vectorize(t_raw)
    c_chunks, c_embeds = chunk_and_vectorize(c_raw)
    
    return {
        "target_chunks": t_chunks, "target_embeddings": t_embeds,
        "competitor_chunks": c_chunks, "competitor_embeddings": c_embeds,
        "target_quant_pipeline_data": t_quant, "competitor_quant_pipeline_data": c_quant,
        "q_index": 0, "target_answers": {}, "competitor_answers": {}
    }
def consumer_qa_node(state: ConsumerQuantState):
    idx = state["q_index"]
    question = DILIGENCE_QUESTIONS[idx]
    retrieval_query = RETRIEVAL_STATEMENTS[idx]
    
    is_target = state["current_company"] == "target"
    ticker = state["target_ticker"] if is_target else state["competitor_ticker"]
    chunks = state["target_chunks"] if is_target else state["competitor_chunks"]
    embeds = state["target_embeddings"] if is_target else state["competitor_embeddings"]
    quant_context = state["target_quant_pipeline_data"] if is_target else state["competitor_quant_pipeline_data"]
    print(f"    -> [Q{idx+1}/{len(DILIGENCE_QUESTIONS)}] Evaluating ({ticker}): {question[:60]}...")
    top_chunks = retrieve_top_k_chunks(retrieval_query, chunks, embeds, k=3)
    semantic_context_str = "\n".join(top_chunks)
    injected_quant_str = json.dumps(quant_context)
    prompt = f"""You are an advanced financial analyst. Answer the following question about {ticker} using the qualitative text context AND the structured pipeline metrics.
    QUESTION: {question}
    OUTPUT SPECIFICATION FORMAT (STRICT JSON OBJECT):
    {{"status": "Disclosed" | "Undisclosed", "answer": "text summary including raw data and metrics", "citations": ["exact matches from text"]}}
    STRUCTURED PIPELINE QUANT METRICS (Item 2, 7, 8, 11, 12, DEF 14A):
    {injected_quant_str}
    TEXT CONTEXT:
    {semantic_context_str}"""

    time.sleep(2.0) # to remove the api rate limit reached . time to sleep is in seconds .
    
    
    try:
        raw_response = execute_groq_call(
            prompt=prompt, 
            temperature=0.0, 
            response_format={"type": "json_object"},
            system_directive="Answer solely based on the structural context provided. No fabrications."
        )
        answer_json = json.loads(raw_response)
    except Exception as e:
        answer_json = {"status": "Error", "answer": f"Parsing interface bypassed: {str(e)[:50]}", "citations": []}
        
    if is_target:
        state["target_answers"][question] = answer_json
    else:
        state["competitor_answers"][question] = answer_json
        
    return {"q_index": idx + 1, "target_answers": state["target_answers"], "competitor_answers": state["competitor_answers"]}
def switch_company_node(state: ConsumerQuantState):
    return {"current_company": "competitor", "q_index": 0}

def synthesis_reasoning_node(state: ConsumerQuantState):
    
    prompt = f"""You are a Lead Portfolio Strategy Director. Generate a market due diligence report comparing {state['target_ticker']} and {state['competitor_ticker']}.
    Utilize the structured target answers: {json.dumps(state['target_answers'])}
    Utilize the competitor answers: {json.dumps(state['competitor_answers'])}
    Deliver a professional summary evaluating market traction, product pipeline capital efficiency, and pricing barriers. Format using clear Markdown."""
    time.sleep(2.5)# to remove the api rate limit reached . time to sleep is in seconds .
    try:
        final_report = execute_groq_call(prompt, temperature=0.1)
    except Exception as e:
        final_report = f"Synthesis step failure: {e}"
    return {"final_report": final_report}

def db_save_node(state: ConsumerQuantState):
    print("[*] PERSISTENCE: Committing structured quantitative pipeline layers and responses to DB tables...")
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS consumer_quant_analysis (
                id SERIAL PRIMARY KEY,
                target_ticker VARCHAR(10),
                competitor_ticker VARCHAR(10),
                target_quant_metrics JSONB,
                competitor_quant_metrics JSONB,
                analysis_results JSONB,
                final_report TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        cur.execute("""
            INSERT INTO consumer_quant_analysis (target_ticker, competitor_ticker, target_quant_metrics, competitor_quant_metrics, analysis_results, final_report)
            VALUES (%s, %s, %s, %s, %s, %s);
        """, (
            state["target_ticker"], 
            state["competitor_ticker"], 
            json.dumps(state["target_quant_pipeline_data"]),
            json.dumps(state["competitor_quant_pipeline_data"]),
            json.dumps({"target": state["target_answers"], "competitor": state["competitor_answers"]}),
            state["final_report"]
        ))
        conn.commit()
        print("[+] PostgreSQL pipeline synchronized and updated safely.")
    except Exception as e:
        print(f"[-] Database Error: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()
    return {}

def route_qa(state: ConsumerQuantState):
    if state["q_index"] < len(DILIGENCE_QUESTIONS):
        return "continue_qa"
    elif state["current_company"] == "target":
        return "switch_company"
    else:
        return "synthesis"
class RIAgent():
    def __init__(self , target :str , competitor :str , ):
        self.target = target
        self.competitor  =competitor
        self.builder = StateGraph(ConsumerQuantState)
        
        self.builder.add_node("switch", switch_company_node)
        self.builder.add_node("synthesis", synthesis_reasoning_node)
        self.builder.add_node("ingest", ingest_and_quant_pipeline_node)
        self.builder.add_node("qa_loop", consumer_qa_node)
        self.builder.add_node("save", db_save_node)

        def set_target(s): return {"current_company": "target"}
        self.builder.add_node("init", set_target)

        self.builder.set_entry_point("init")
        self.builder.add_edge("init", "ingest")
        self.builder.add_edge("ingest", "qa_loop")

        self.builder.add_conditional_edges("qa_loop", route_qa, {
            "continue_qa": "qa_loop",
            "switch_company": "switch",
            "synthesis": "synthesis"
        })
        self.builder.add_edge("switch", "qa_loop")
        self.builder.add_edge("synthesis", "save")
        self.builder.add_edge("save", END)

        self.app = self.builder.compile()
        


obj = RIAgent("NVDA" , "GOOGL")
final_output = obj.app.invoke({
            "target_ticker":obj.target, "competitor_ticker": obj.competitor,
            "current_company": "target", "q_index": 0, "target_answers": {}, "competitor_answers": {},
            "target_quant_pipeline_data": {}, "competitor_quant_pipeline_data": {}, "final_report": ""
        })
print(f"\n extracted Item 8 quant metrics count (Target): {len(final_output['target_quant_pipeline_data'].get('Item 8', []))}")
print(f" extracted Item 7 quant metrics count (Target): {len(final_output['target_quant_pipeline_data'].get('Item 7', []))}")
print(f" extracted  DEF 14A quant  metrics count (Target): {len(final_output['target_quant_pipeline_data'].get('DEF 14A', []))}")
    
print("\n       final report  ")
print(final_output.get("final_report", "Report missing."))
    
