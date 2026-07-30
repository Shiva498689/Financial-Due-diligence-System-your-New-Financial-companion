import os
from qdrant_client import AsyncQdrantClient, models
from google import genai
import json
import asyncio
DB_TABLE_NAME = "financial_due_diligence_chunks"
GEMINI_API_KEY = os.environ.get(
    "GEMINI_API_KEY",
    "AQ.Ab8RN6KVewqbkCQ_dyxNcUGGllh9J4XkmRk3R5AMN1TEuLQgeg",
)
GEMINI_MODEL = "gemini-3.5-flash-lite"
if not GEMINI_API_KEY or GEMINI_API_KEY == "YOUR_GEMINI_API_KEY":
    print("[!] Warning: Please set a valid GEMINI_API_KEY in your environment.")
DILIGENCE_QUESTIONS = ["Strategic Moat & Disruption: How does management identify its core competitive barriers and market entry protection?",
    "Strategic Moat & Disruption: What specific low-cost or technological disruptors does management note as direct competitive threats?",
    "Consumer Shift Rationale: What explanations does management offer for structural changes in consumer purchasing habits?",
    "Consumer Shift Rationale: How is a changing product mix or volume compression changing overall segment revenue?",
    "Pricing Power Execution: What is the specific execution mechanism for passing input cost inflation onto consumers via price hikes?",
    "Pricing Power Execution: How does management describe consumer volume elasticity or pushback to recent price adjustments?",
    "Underpenetrated Growth Vectors: What is the company's expansion roadmap for new geographic or vertical market segments?",
    "Underpenetrated Growth Vectors: What targeted value proposition is being marketed to unlock these new addressable demographics?",
    "M&A Integration Friction: What operational friction points, timeline delays, or system infrastructure issues occurred during recent integrations?",
    "M&A Integration Friction: What explicit corporate restructuring charges or workforce alignment friction points were recorded?",
    "FX Operational Adaptation: What structural supply chain movements or local sourcing initiatives are being executed to combat currency issues?",
    "FX Operational Adaptation: How is localized pricing or contract renegotiation being deployed to mitigate foreign currency volatility?",
    "Incentive Compensation Alignment: What specific performance metrics (like EPS, ROIC, or total shareholder return) govern executive annual cash bonuses?",
    "Incentive Compensation Alignment: How are long-term equity awards insulated by clawback policies or equity holding requirements?",
    "Human Capital & Labor Vitality: What material turnover trends, attrition rates, or specialized engineering/software talent recruitment risks are disclosed?",
    "Human Capital & Labor Vitality: What is the current operational health of baseline labor relations and domestic/international workforce stability?",
    "Key-Person & Succession Risk: To what extent is the company structurally dependent on the continuous service of its founder or Chief Executive Officer?",
    "Key-Person & Succession Risk: What structural gaps or strategic execution risks exist regarding formal executive succession planning?",
    "Board Oversight of Emerging Technology: How are the board committees explicitly organized to oversee data privacy policies and cybersecurity governance?",
    "Board Oversight of Emerging Technology: What operational oversight frameworks govern corporate artificial intelligence implementation and risk tracking?",
    "Related-Party Transaction Risks: What related-party transactions involve real estate leases, asset purchases, or vendor relationships owned by executives?",
    "Related-Party Transaction Risks: What tracking controls and internal evaluation policies govern the review of major shareholder transactions?",
    "ESG & Decarbonization Mandates: What fundamental capital allocation shifts are required to achieve targeted net-zero or carbon emission metrics?",
    "ESG & Decarbonization Mandates: What explicit material risks do physical climate disruptions or transitional carbon regulations pose to manufacturing operations?",
    "Single-Source Sourcing Chokepoints: Where does the business rely on a single or sole-source vendor for critical production components?",
    "Single-Source Sourcing Chokepoints: What internal raw material dependency risks lack alternative qualification paths or backup supply buffers?",
    "Logistics & Manufacturing Concentration: What geographical or physical concentration risks exist regarding the company's internal manufacturing facilities?",
    "Logistics & Manufacturing Concentration: What single-point distribution vulnerabilities exist across the outsourced third-party logistics network?",
    "Raw Material Scarcity Strategies: What are the operational parameters and minimum volume requirements of the company's long-term procurement obligations?",
    "Raw Material Scarcity Strategies: How has supplier concentration shifted structural input cost pricing power away from the company?",
    # "Intellectual Property & Patent Horizons: What core proprietary patents face impending expiration timelines over the near-term forecast horizon?",
    # "Intellectual Property & Patent Horizons: What material royalty structures or third-party technology licensing agreements are critical to product manufacturing?",
    # "Vendor Switching Frictions: What operational disruptions or data migration complexities act as structural barriers to switching primary cloud providers?",
    # "Vendor Switching Frictions: What financial exit penalties or contractual multi-year commitments prevent the migration of primary SaaS solutions?",
    # "Geopolitical & Trade Tariff Exposure: How are active regulatory international tariffs or cross-border trade restrictions altering regional unit economics?",
    # "Geopolitical & Trade Tariff Exposure: What manufacturing footprint re-shoring or localized manufacturing re-organizations are underway to mitigate sovereign risk?",
    # "Brand-Damaging Litigation: What active class-action lawsuits or consumer safety claims present material financial or reputational risks?",
    # "Brand-Damaging Litigation: What active intellectual property or patent infringement lawsuits threaten core production viability?",
    # "Data Privacy Regulatory Shocks: What operational compliance vulnerabilities exist regarding cross-border data movements under GDPR or CCPA frameworks?",
    # "Data Privacy Regulatory Shocks: What structural investments are required to remedy localized data processing or security architecture mandates?",
    # "Legacy Environmental Liabilities: What financial accruals are established for outstanding Superfund site remediation or hazardous cleanup mandates?",
    # "Legacy Environmental Liabilities: What active EPA or regional environmental enforcement actions carry material penalty exposures?",
    # "Uncertain Tax Positions & Audits: What narrative rationale or open positions govern current reserves for unrecognized tax benefits?",
    # "Uncertain Tax Positions & Audits: What international cross-border transfer pricing audits are currently active with foreign tax jurisdictions?",
    # "Internal Controls Weakness Root Causes: What structural accounting tool deficiencies or access control issues caused current material weaknesses?",
    # "Internal Controls Weakness Root Causes: What specific personnel shortages or internal review failures are driving financial reporting accounting restatements?",
    # "Anti-Bribery & FCPA Exposures: What compliance oversight systems govern active operations within high-risk emerging markets under the Foreign Corrupt Practices Act?",
    # "Anti-Bribery & FCPA Exposures: What active internal investigations or Department of Justice / SEC compliance inquiries are currently unresolved?",
    # "Post-Closing Strategic Shifts: What material asset sales, structural closures, or corporate divestitures occurred subsequent to the balance sheet date?",
    # "Post-Closing Strategic Shifts: What major corporate lines of credit or new debt facilities were executed after the current reporting period?",
    # "Risk Factor Narrative Evolution: What newly introduced operational or macroeconomic risks were integrated into the primary risk factor disclosures this period?",
    # "Risk Factor Narrative Evolution: How has management altered the ordering or structural grouping of systemic industry disruptions in Item 1A?",
    # "Product Recalls & Safety Inquiries: What voluntary or government-mandated product recalls or active inventory holds were executed?",
    # "Product Recalls & Safety Inquiries: What ongoing federal or international consumer safety testing probes are actively processing?",
    # "Capital Allocation Philosophy Nuances: What explicit qualitative limits or leverage hurdles govern the authorization of share buyback and dividend distribution programs?",
    # "Capital Allocation Philosophy Nuances: How does management balance operational maintenance capital expenditures against strategic expansion funding?",
    # "Restrictive Covenant Bottlenecks: What explicit net leverage or fixed charge coverage ratios constrain ongoing operational financing adjustments?",
    # "Restrictive Covenant Bottlenecks: What explicit negative pledges or physical asset lien limits restrict the issuance of alternative corporate debt instruments?",
    # "Labor Disruption & Unionization Threats: What explicit percentages of the current global or domestic workforce operate under active union configurations?",
    # "Labor Disruption & Unionization Threats: What upcoming collective bargaining contract expirations present immediate work stoppage or strike exposures?",
    ]
RETRIEVAL_STATEMENTS = [
    "Competitive advantages include proprietary technology market barriers scale economies brand equity distribution networks.",
    "Disruptive competitors low-cost alternatives emerging technological threats market share erosion.",
    "Consumer preferences shifting purchasing patterns changing demand trends shifting habits.",
    "Product mix alterations volume declines demand normalization deceleration segment revenue.",
    "Inflationary price adjustments cost increases passing through price hikes raw material inflation.",
    "Volume elasticity price sensitivity customer pushback resistance to pricing actions.",
    "Expansion roadmap underpenetrated markets geographical expansion new vertical penetration.",
    "Value proposition target demographics addressable market expansion customer acquisition strategies.",
    "Integration delays operational disruption systems consolidation post-merger integration friction.",
    "Restructuring charges severance costs workforce reductions facility consolidations execution challenges.",
    "Local sourcing supply chain relocation localized manufacturing structural FX mitigation.",
    "Localized pricing billing currencies contract renegotiation international price adjustments.",
    "Incentive compensation metrics annual cash bonus performance targets EPS ROIC criteria.",
    "Clawback policy equity retention requirements performance share units long-term incentive alignment.",
    "Employee turnover attrition rates recruiting specialized talent retention risks human capital.",
    "Labor relations employee grievances workforce stability employee engagement metrics disclosures.",
    "Founder dependency chief executive key-person reliance loss of key personnel disruption.",
    "Succession planning executive talent gaps management transition governance vacancy risk.",
    "Cybersecurity governance board oversight audit committee data privacy protections network security.",
    "Artificial intelligence governance AI adoption frameworks technology committee emerging technology risks.",
    "Related-party transactions executive transactions entities owned by officers material conflicts.",
    "Conflict of interest policy related-party review controls disinterested board approval tracking.",
    "Carbon emission targets decarbonization capital expenditure adjustments net-zero compliance costs.",
    "Climate transition risks carbon regulations compliance penalties physical asset vulnerabilities.",
    "Sole-source supplier single vendor dependency component allocation single-points-of-failure.",
    "Alternative sourcing qualifications backup supply constraints material shortages single-source dependencies.",
    "Manufacturing plant concentration localized operations production footprint geographic hubs.",
    "Logistics hubs distribution network central warehouse choke points outsourced fulfillment.",
    "Procurement contract purchase commitments long-term supply obligations purchase agreements.",
    "Supplier leverage input pricing power material scarcity seller concentration dynamics.",
    # "Patent expirations loss of exclusivity generic competition proprietary technology cliff.",
    # "Licensing agreements third-party technology royalties cross-license dependencies software licensing.",
    # "Cloud migration vendor lock-in switching complexities infrastructure architecture transition.",
    # "SaaS contract commitments cancellation termination penalties platform switching costs software dependencies.",
    # "Tariff exposure trade restrictions cross-border duties protectionism impact import penalties.",
    # "Re-shoring footprint optimization production relocation near-shoring cross-border geopolitical adjustments.",
    # "Class-action lawsuit consumer litigation product liability multi-district litigation lawsuits.",
    # "Patent infringement litigation trade secret misappropriation injunction risk IP disputes.",
    # # 20. Data Privacy Regulatory Shocks
    # "GDPR compliance CCPA enforcement data protection frameworks cross-border transfer restrictions.",
    # "Data localization regional storage regulatory compliance remediations platform architectures.",
    # # 21. Legacy Environmental Liabilities
    # "Superfund cleanup liabilities remediation costs hazardous waste site legacy environmental.",
    # "EPA violations clean air compliance enforcement decrees environmental regulatory fines.",
    # # 22. Uncertain Tax Positions & Audits
    # "Unrecognized tax benefits tax reserves internal revenue service valuation allowance.",
    # "Transfer pricing dispute international tax audits foreign revenue authorities audit.",
    # # 23. Internal Controls Weakness Root Causes
    # "Material weakness information technology controls segregation of duties financial reporting failures.",
    # "Accounting personnel deficiencies review control tracking errors material weaknesses remediation.",
    # # 24. Anti-Bribery & FCPA Exposures
    # "FCPA monitoring anti-corruption compliance program foreign corrupt practices act testing.",
    # "DOJ investigation SEC enforcement inquiry subpoena regulatory compliance review.",
    # # 25. Post-Closing Strategic Shifts
    # "Subsequent events asset divestitures transaction post-period closing asset sales.",
    # "Credit facility execution subsequent financing debt issuance post-closing term loan.",
    # # 26. Risk Factor Narrative Evolution
    # "Risk factors structural industry updates macroeconomic operational risk additions.",
    # "Risk groupings prioritization operational risks business continuity framework adaptations.",
    # # 27. Product Recalls & Safety Inquiries
    # "Product recall inventory pullbacks consumer product safety commission voluntary safety holds.",
    # "Safety probes regulatory testing investigations consumer injury claims engineering review.",
    # # 28. Capital Allocation Philosophy Nuances
    # "Share repurchases dividend prioritization capital return execution equity buyback hurdles.",
    # "Capital expenditures maintenance capex growth investments resource deployment strategic reinvestment.",
    # # 29. Restrictive Covenant Bottlenecks
    # "Financial covenants leverage ratio maintenance limits fixed charge coverage metrics.",
    # "Negative pledge restrictive covenants asset liens encumbrances limitation on debt.",
    # # 30. Labor Disruption & Unionization Threats
    # "Unionized employees collective bargaining agreements union representation percentage workforce.",
    # "Contract expiration strike risk work stoppages union negotiations organized labor.",
]
async def qdrant_vector_retrieval(client, ticker, retrieval_statement, limit=2):
    try:
        results = await client.query_points(
            collection_name=DB_TABLE_NAME,
            query=models.Document(
                text=retrieval_statement,
                model="sentence-transformers/all-MiniLM-L6-v2"
            ),
            limit=limit,
            query_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="ticker",
                        match=models.MatchValue(value=ticker)
                    )
                ]
            )
        )
        return results.points
    except Exception as e:
        print(f"[!] Qdrant Retrieval Error: {str(e)}")
        return []
async def analysis_genrator(ticker):
    target_ticker = ticker
    if not target_ticker:
        print("[!] No ticker entered. Exiting.")
        return []

    print("\n[*] Connecting to Qdrant Cloud...")
    try:
        qdrant_client = AsyncQdrantClient(
            url="https://3e3b954a-76d4-425b-992b-51d1b942e2dd.eu-west-1-0.aws.cloud.qdrant.io:6333", 
            api_key=os.getenv("QDRANT_API_KEY"),
            cloud_inference=True
        )
        print("[+] Qdrant connection established successfully.")
    except Exception as e:
        print(f"[!] Qdrant Connection Error: {e}")
        return []

    # Combine the pairs so we can chunk them cleanly
    paired_tasks = list(zip(DILIGENCE_QUESTIONS, RETRIEVAL_STATEMENTS))
    
    # Configuration for Free Tier stability
    BATCH_SIZE = 15  # 60 questions / 20 = 3 clean API calls
    final_answers = []
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

    # Process questions in chunks of 20
    for batch_idx in range(0, len(paired_tasks), BATCH_SIZE):
        batch = paired_tasks[batch_idx:batch_idx + BATCH_SIZE]
        current_batch_num = (batch_idx // BATCH_SIZE) + 1
        total_batches = (len(paired_tasks) + BATCH_SIZE - 1) // BATCH_SIZE
        
        print(f"\n[*] Processing Batch {current_batch_num}/{total_batches} ({len(batch)} questions)...")

        # Concurrently fetch DB context only for the current batch
        async def fetch_dimension_context(index, question, statement):
            matched_points = await qdrant_vector_retrieval(qdrant_client, target_ticker, statement, limit=3)
            formatted_context = ""
            for idx, point in enumerate(matched_points):
                # Safely extract text document and metadata from the payload
                payload = point.payload or getattr(point, "metadata", {})
                doc_text = payload.get("chunk", "")
                
                filing_date = payload.get("filing_date", "Unknown")
                form = payload.get("filing_type", "Unknown")
                item = payload.get("sec_item", "Unknown")
                
                formatted_context += f"\n--- Context Document [{idx+1}] (Filed: {filing_date} | Form: {form} | Section: {item}) ---\n"
                formatted_context += f"[Raw Filing Context]:\n{doc_text}\n"
            return question, (formatted_context if matched_points else "No specific text matches found.")

        tasks = [
            fetch_dimension_context(batch_idx + i, q, s) 
            for i, (q, s) in enumerate(batch, 1)
        ]
        results = await asyncio.gather(*tasks)
        batch_context = {q: ctx for q, ctx in results}

        # Build the structured prompt for this specific batch
        system_prompt = (
            "You are an elite, cynical investment banking due diligence specialist analyzing corporate SEC filings.\n"
            "Below is a subset of due diligence questions with their corresponding retrieved SEC Evidence.\n"
            "Your task is to answer EACH question using ONLY the provided text blocks for that question.\n"
            "Guidelines:\n"
            "1. Be direct, crisp, and objective. Avoid corporate pleasantries.\n"
            "2. Explicitly cite the filing date and item section when referencing facts.\n"
            "3. If the provided context lacks data, state exactly what is missing. If you found nothing, simply say found nothing.\n\n"
            "You MUST return the output as a valid JSON object, where the keys are exactly the questions provided, and the values are your answers."
        )

        user_content = ""
        for q, ctx in batch_context.items():
            user_content += f"Question: {q}\n"
            user_content += f"Retrieved SEC Evidence:\n{ctx}\n\n"

        full_prompt = system_prompt + "\n\n" + user_content

        print(f"[*] Dispatching Batch {current_batch_num} to Gemini ({GEMINI_MODEL})...")
        try:
            response = await client.aio.models.generate_content(
                model=GEMINI_MODEL,
                contents=full_prompt,
                config=genai.types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.0,
                    # 1. Disable safety filters for financial/legal analysis
                    safety_settings=[
                        genai.types.SafetySetting(
                            category=genai.types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                            threshold=genai.types.HarmBlockThreshold.BLOCK_NONE,
                        ),
                        genai.types.SafetySetting(
                            category=genai.types.HarmCategory.HARM_CATEGORY_HARASSMENT,
                            threshold=genai.types.HarmBlockThreshold.BLOCK_NONE,
                        ),
                        genai.types.SafetySetting(
                            category=genai.types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                            threshold=genai.types.HarmBlockThreshold.BLOCK_NONE,
                        ),
                        genai.types.SafetySetting(
                            category=genai.types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                            threshold=genai.types.HarmBlockThreshold.BLOCK_NONE,
                        )
                    ]
                ),
            )

            # 2. Safely check if text exists before parsing
            if not response.text:
                # If text is None, print the reason so you know exactly why it failed
                finish_reason = response.candidates[0].finish_reason if response.candidates else "UNKNOWN"
                print(f"[!] API returned empty text. Finish Reason: {finish_reason}")
                
                for q, _ in batch:
                    final_answers.append({q: f"Failed: API blocked response (Reason: {finish_reason})"})
                continue # Skip parsing and move to the next batch

            response_json = json.loads(response.text)
            
            # Map answers back to order
            for q, _ in batch:
                if q in response_json:
                    final_answers.append({q: response_json[q]})
                else:
                    final_answers.append({q: "Error: Model failed to generate an answer for this key."})

        except Exception as e:
            print(f"[!] Gemini API Error on Batch {current_batch_num}: {e}")
            for q, _ in batch:
                final_answers.append({q: "Failed due to API execution error."})
        except Exception as e:
            print(f"[!] Gemini API Error on Batch {current_batch_num}: {e}")
            # Append empty states so the final indexing doesn't break
            for q, _ in batch:
                final_answers.append({q: "Failed due to API execution error."})

        # Quota Safeguard: Wait for the per-minute token clock to reset before firing the next batch
        if batch_idx + BATCH_SIZE < len(paired_tasks):
            print("[*] Sleeping for 65 seconds to clear Free Tier Rate Limits (250k TPM)...")
            await asyncio.sleep(65)

    await qdrant_client.close()
    print("\n[+] Analysis execution complete successfully.")
    return final_answers

