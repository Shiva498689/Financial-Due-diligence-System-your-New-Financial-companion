import os
import sys
import psycopg2
from psycopg2.extras import DictCursor
from groq import Groq

# ==========================================
# CONFIGURATION & CONNECTIONS
# ==========================================
DB_CONFIG = {
    "dbname": "financial_db",
    "user": "postgres",
    "password": "123shivadubey@gmail.com",  # Update with your password
    "host": "localhost",
    "port": "5432"
}
DB_TABLE_NAME = "financial_due_diligence_chunks"  # Update if your table name is different

GROQ_API_KEY = "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"      # Update with your Groq API Key
GROQ_MODEL = "openai/gpt-oss-120b"         # High-context model ideal for analytical evaluation

# Initialize Groq Client
if GROQ_API_KEY == "YOUR_GROQ_API_KEY" or not GROQ_API_KEY:
    print("[!] Error: Please set a valid GROQ_API_KEY inside the script.")
    sys.exit(1)

groq_client = Groq(api_key=GROQ_API_KEY)

RETRIEVAL_STATEMENTS = [
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

DILIGENCE_QUESTIONS = [
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
    "Item 2 Properties summaries or operational overviews outlining manufacturing plant concentrations, logistics hub singlepoints, or centralized distribution choke points.",
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

# ==========================================
# HYBRID RETRIEVAL MECHANISM
# ==========================================
def hybrid_db_retrieval(cursor, ticker, retrieval_statement, limit=17):
    """
    Performs a full-text search ranking query inside PostgreSQL across 
    BOTH the verbose text 'original_chunk' and 'summary_bullet_points' columns.
    """
    # Target table name matching your exact database list
    table_name = "financial_due_diligence_chunks"
    
    # Text-based query using correct database schema naming maps
    query = f"""
        SELECT 
            filing_date, 
            filing_type as form, 
            sec_item as item, 
            original_chunk as chunk, 
            summary_bullet_points as summary_bullets,
            ts_rank_cd(
                to_tsvector('english', original_chunk || ' ' || summary_bullet_points), 
                plainto_tsquery('english', %s)
            ) as rank
        FROM {table_name}
        WHERE ticker = %s 
          AND (
            to_tsvector('english', original_chunk || ' ' || summary_bullet_points) @@ plainto_tsquery('english', %s)
            OR original_chunk ILIKE %s
          )
        ORDER BY rank DESC, filing_date DESC
        LIMIT %s;
    """
    
    fuzzy_keyword = f"%{retrieval_statement.split()[0]}%"
    cursor.execute(query, (retrieval_statement, ticker, retrieval_statement, fuzzy_keyword, limit))
    return cursor.fetchall()

# ==========================================
# GROQ GENERATION EXECUTION
# ==========================================
def generate_diligence_analysis(question, context_data):
    """
    Pipes the retrieved text chunks and summaries into Groq to execute 
    the analytical due diligence response.
    """
    # Format database context into clean textual hierarchy for the LLM
    formatted_context = ""
    for idx, row in enumerate(context_data):
        formatted_context += f"\n--- Context Document [{idx+1}] (Filed: {row['filing_date']} | Form: {row['form']} | Section: {row['item']}) ---\n"
        formatted_context += f"[Executive Summary View]:\n{row['summary_bullets']}\n"
        formatted_context += f"[Raw Filing Context]:\n{row['chunk']}\n"

    system_prompt = (
        "You are an elite, cynical investment banking due diligence specialist analyzing corporate SEC filings.\n"
        "Your task is to answer the target user question using ONLY the provided text blocks and summaries from the database.\n"
        "Guidelines:\n"
        "1. Be direct, crisp , and objective. Avoid corporate pleasantries. \n"
        "2. Explicitly cite the filing date and item section when referencing facts.\n"
        "3. If the provided context lacks data to completely address the question, state exactly what is missing." "Do not eleborate much give the things that makes the diligence easy " "If you found nothing from database simply say found nothing"
    )
    
    user_content = f"""
Target Due Diligence Question:
{question}

Retrieved SEC Evidence:
{formatted_context if context_data else "No specific text matches found in the database for this dimension."}

Provide your synthesis and final investment analysis:
"""

    response = groq_client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ],
        temperature=0.15,  # Low temperature guarantees analytical grounding
        max_tokens=1500
    )
    return response.choices[0].message.content

# ==========================================
# MAIN EXECUTION ROUTINE
# ==========================================
def main():
    print("=" * 65)
    print("      SEC FILING HYBRID RETRIEVAL & ANALYSIS AGENT (GROQ)      ")
    print("=" * 65)
    
    target_ticker = input("[?] Enter the target company Ticker to analyze (e.g., AAPL): ").strip().upper()
    if not target_ticker:
        print("[!] No ticker entered. Exiting.")
        return

    print(f"\n[*] Connecting to PostgreSQL database '{DB_CONFIG['dbname']}'...")
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor(cursor_factory=DictCursor)
        print("[+] Connection established successfully.")
    except Exception as e:
        print(f"[!] Database Connection Error: {e}")
        return

    print(f"[*] Starting due diligence pipeline execution for {target_ticker}...\n")
    
    # Process all 30 financial dimensions sequentially
    for index, (question, statement) in enumerate(zip(DILIGENCE_QUESTIONS, RETRIEVAL_STATEMENTS), 1):
        print("-" * 80)
        print(f"[Dimension {index}/30] {question.split(':')[0]}")
        print(f"[*] Statement Guide: {statement}")
        print(f"[*] Querying database for semantic matches...")
        
        # 1. Retrieve the evidence chunks from Postgres
        matched_rows = hybrid_db_retrieval(cursor, target_ticker, statement)
        print(f"[+] Found {len(matched_rows)} corresponding filing fragments.")
        
        # 2. Fire the payloads to Groq Cloud
        print(f"[*] Blasting payload context to Groq ({GROQ_MODEL})...")
        try:
            analysis_result = generate_diligence_analysis(question, matched_rows)
            
            # 3. Print analysis to terminal in real-time
            print(f"\n[ANALYSIS REPORT - {target_ticker}]:")
            print(analysis_result)
        except Exception as e:
            print(f"[!] Groq API Generation Error on dimension {index}: {e}")
            
        print("-" * 80 + "\n")

    cursor.close()
    conn.close()
    print("[*] Due Diligence Analysis complete. All dimensions evaluated.")

if __name__ == "__main__":
    main()
