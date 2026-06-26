import asyncio
import re
from edgar import Company , set_identity
import torch 
from transformers import AutoModelForCausalLM , AutoTokenizer , BitsAndBytesConfig
import os
from dotenv import load_dotenv
from groq import AsyncGroq

load_dotenv()

client = AsyncGroq(api_key=os.environ.get("GROQ_API_KEY"))

GROQ_MODEL = "openai/gpt-oss-20b"

async def llm_async(prompt: str) -> str:
    resp = await client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,        # deterministic: critical for extractive faithfulness
        max_tokens=2000,      # your output budget (the bullets)
    )
    return resp.choices[0].message.content

if not os.getenv("EDGAR_IDENTITY"):
    raise ValueError("EDGAR IDENTITY NOT FOUND !")

def get_one_company(ticker : str) -> dict:
    # creating an object used to create all the 4 sections for one particular ticker
    tenk = Company(ticker).get_filings(form = "10-K").latest().obj() 

    def get_subsidiary_count(tenk) -> int | None:
        try:
            exhibit_21 = tenk.exhibits.get("EX-21") or tenk.exhibits.get("EX-21.1")
            if not exhibit_21:
                return None
            
            text = str(exhibit_21.text)
            
            # Count non-empty lines that aren't headers
            lines = [
                line.strip() for line in text.split("\n")
                if line.strip() and len(line.strip()) > 5
            ]
            return len(lines)
        except:
            return None

    return{
        "target_ticker" : ticker , 
        "company_name" : (str(tenk.company)) ,
        "filing_date" : (str(tenk.filing_date)) , 
        "fiscal_year_end" : (str(tenk.period_of_report)) , 
        "filing_type" : "10-K",
        "risk_factors" : (str(tenk.risk_factors)) , 
        "management_discussion" : str(tenk.management_discussion) , 
        "legal_proceedings" : str(tenk["Item 3"]) , 
        "business_description" : str(tenk["Item 1"]) ,
        "auditor" : (str(tenk.auditor)) , 
        "subsidiary_count"  : get_subsidiary_count(tenk)
    }

# function to ensure that if you are getting for one company , then that has to be put in the event loop ans await as the request is fired
async def get_one_company_async(ticker : str) -> dict:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None , get_one_company , ticker)

# function to collect info for all companies in an asynchronous manner 
async def get_all_company_async(tickers : list[str]) -> list[dict] :
    tasks = [get_one_company_async(t) for t in tickers]
    results = await asyncio.gather(*tasks)
    return list(results)

# DEFINING AND LOADING THE MODEL
"""model_name = "Qwen/Qwen2.5-7B-Instruct"

quant_config = BitsAndBytesConfig(
    load_in_4bit=True,                  # 4-bit loading on
    bnb_4bit_quant_type="nf4",          
    bnb_4bit_compute_dtype=torch.float16
)

# Loading the tokeniser
tokeniser = AutoTokenizer.from_pretrained(model_name)

# Loading the model
model = AutoModelForCausalLM.from_pretrained(
    model_name , 
    quantization_config = quant_config
)

# to make llm calls async (for the condensation of peers , sections simulatenously)
async def llm_async(prompt : str) -> str:
    return await model.agenerate(prompt)"""

## GROQ LLM PART



# DEFINING THE SECTIONS TO FOCUS ON THE TARGET COMPANY 
SECTION_FOCUS = {
    "risk_factors": (
        "Extract ONLY company-specific, material risks. Prioritize: "
        "(1) customer concentration (% of revenue from one/top customers, named customers); "
        "(2) supplier/raw-material dependence, single-source or single-country sourcing, "
        "and whether supply is diversified or concentrated; "
        "(3) GEOPOLITICAL exposure: name the countries involved and the specific risk "
        "(tariffs, sanctions, export controls, conflict, currency controls), for BOTH "
        "sales markets and supplier/manufacturing locations; "
        "(4) named litigation or regulatory actions with financial exposure; "
        "(5) internal-control material weakness or going-concern language; "
        "(6) concentration in a single product, segment, or geography; "
        "(7) pricing pressure, input-cost inflation, or inability to pass costs to customers; "
        "(8) debt covenants or liquidity constraints. "
        "EXCLUDE generic boilerplate UNLESS tied to a company-specific figure, named "
        "country, or named entity. Lead each bullet with the risk type."
    ),

    "business_description": (
        "Extract what the company does and how it competes: "
        "(1) primary products/services and revenue split if stated; "
        "(2) reportable segments (product/business/GEOGRAPHIC) with revenue or % figures, "
        "including which countries/regions are the largest markets; "
        "(3) customer concentration (major/named customers, % from top customers, "
        "government vs commercial mix); "
        "(4) RAW MATERIALS and supply chain: key inputs, named suppliers, single vs "
        "diversified sourcing, and the countries those inputs/manufacturing come from; "
        "(5) COMPETITIVE ADVANTAGE: stated moat, brand, scale, switching costs, network "
        "effects, proprietary IP/licenses, and named principal competitors; "
        "(6) PRICING STRATEGY: how the company prices (premium, subscription, volume, "
        "cost-plus), and any stated pricing power; "
        "(7) any disclosed per-customer economics (ARPU, subscriber counts, average "
        "revenue per user/account) ONLY if the filing states them. "
        "Capture all figures, segment names, countries, and named entities verbatim. "
        "Do NOT infer customer demographics, age groups, or per-customer pricing if the "
        "filing does not state them."
    ),

    "management_discussion": (
        "Extract management's account of performance and outlook: "
        "(1) revenue and margin direction with figures and YoY changes, and the SEGMENT or "
        "GEOGRAPHY driving them; "
        "(2) drivers management attributes results to (which product/market/region moved numbers); "
        "(3) impact of GEOPOLITICAL events, tariffs, FX, or specific-country conditions on "
        "results, with named countries; "
        "(4) input/raw-material COST trends and whether the company raised prices in response "
        "(pricing power evidence); "
        "(5) forward guidance and quantified targets; "
        "(6) direct CEO/CFO quotes about strategy, pricing, or competitive position; "
        "(7) liquidity, cash, and capital allocation (buybacks, dividends, capex). "
        "Favor statements checkable against the financial ratios. Convey tone only by "
        "quoting management's own words."
    ),

    "legal_proceedings": (
        "Extract each distinct active legal/regulatory matter separately: parties; nature "
        "of claim; current status (filed, pending, settled, appealed); and any stated or "
        "estimated exposure, reserve, or damages. Include antitrust/competition cases and "
        "regulatory or trade actions (relevant to pricing power and geopolitical exposure). "
        "List a matter even if stated not material (note that it said so). EXCLUDE routine "
        "ordinary-course boilerplate unless a specific case is named."
    ),
}

# DEFINING THE FOCUS SECTION FOR PEERS
PEER_SECTION_FOCUS = {
    "business_description": (
        "Extract ONLY what is needed to benchmark this peer against the target. "
        "Keep it tight (aim for 4-7 bullets total): "
        "(1) reportable segments and revenue split, especially GEOGRAPHIC segments and "
        "which countries/regions are the largest markets; "
        "(2) RAW MATERIALS / supply chain: key inputs, named suppliers, and whether "
        "sourcing is single-source or diversified, and from which countries; "
        "(3) COMPETITIVE ADVANTAGE vs others: stated moat, brand, scale, switching costs, "
        "proprietary IP, and how this peer positions against competitors; "
        "(4) PRICING STRATEGY: premium vs value vs subscription vs cost-plus, and any "
        "stated pricing power; "
        "(5) per-customer economics (ARPU, subscriber/user counts) ONLY if the filing "
        "explicitly states them. "
        "Capture figures, segment names, countries, and named entities verbatim. "
        "Do NOT infer customer demographics, age groups, or per-customer pricing if absent."
    ),

    "risk_factors": (
        "Extract ONLY the 2-3 most company-specific risks relevant to competitive "
        "comparison: "
        "(1) supplier/raw-material concentration or single-country sourcing; "
        "(2) GEOPOLITICAL exposure with NAMED countries (tariffs, sanctions, export "
        "controls, conflict) for either sales or supply; "
        "(3) pricing pressure, input-cost inflation, or inability to pass costs to customers; "
        "(4) customer concentration if a major/named customer dependence is stated. "
        "One bullet each. EXCLUDE all generic boilerplate."
    ),
    "management_discussion": "revenue/margin trends, forward guidance, and "
                             "direct CEO/CFO statements about performance.",
    "legal_proceedings": "each active case: parties, claim, status, exposure."
}

FOCUS_MAPS = {"target": SECTION_FOCUS, "peer": PEER_SECTION_FOCUS}

# VERIFICATION (TO MAKE SURE THAT THE LLM OUTPUT IS NOT HALLUCINATED)
def verify(bullets : str , source : str , window : int = 10) -> str:
    src = re.sub(r"\s+", " ", source).lower()
    kept = []
    for line in bullets.splitlines():
        cand = line.lstrip("-*• \t").strip()
        if len(cand) < 20:
            continue
        words = re.sub(r"\s+", " ", cand).lower().split()
        grounded = any(
            " ".join(words[i:i + window]) in src
            for i in range(max(1, len(words) - window + 1))
        )
        if grounded:
            kept.append(f"- {cand.rstrip('.')}." )
    return "\n".join(kept)

# define the max number of tokens allowed to put in an LLM
SECTION_INPUT_CHARS = {
    "risk_factors" : 80000 , 
    "management_discussion" : 60000 ,
    "business_description" : 60000 ,
    "legal_proceedings" : 40000
}

# DEFNING THE PROMPT TO BE GIVEN TO THE LLM TO EXTRACT THE IMPORTANT THINGS OUT OF THE GIVEN TEXT AND CONDENSE IT 
PROMPT = """You are extracting key facts from the {section} section of an SEC 10-K
for {company}.

WHAT TO EXTRACT:
{focus}

UNIVERSAL RULES (always apply):
- Copy facts, figures, names, and percentages VERBATIM from the source.
- Do NOT invent or infer any number, name, date, or claim not in the source.
- Do NOT paraphrase a figure; quote it exactly as written.
- Omit anything you cannot ground in the source text.
- Output concise bullet points. One distinct fact or item per bullet.
- If the section contains nothing matching the focus, output nothing.

SOURCE:
{text}
"""

# A function to verify + condense the ouptut of a given text , company , section from the LLM (to make sure llm calls are in an asynchronous manner)
async def condense_one(text:str , section_type : str , llm_async ,  company : str , role : str = "target") -> str:
    focus = FOCUS_MAPS[role] # to get the section dict (section -> what to look for)
    if not text or section_type not in focus:
        return ""
    num_tokens_cap = SECTION_INPUT_CHARS[section_type]
    # defining the prompt to be given to the LLM to generate the output
    prompt = PROMPT.format(
        section = section_type.replace("_" , " ") , 
        company = company , 
        focus = focus ,
        text = text[: num_tokens_cap]
    )

    output = await llm_async(prompt) # returns the condensed output (removing any unnecessary stuff) -> await ensures single llm worflow 
    return verify(output , text) # return the verified ouput (removes any hallucinations by the LLM) 

async def condense_all(ticker : str, peers_list : list ,llm_async , max_concurrency = 4) -> dict:
    async def get_peers_and_ticker_dict(ticker : str) -> dict[str , dict]:

        all_tickers = [ticker , *peers_list]
        results = await get_all_company_async(all_tickers)

        target = results[0]

        peers : dict[str , dict] = {}
        for peers_data in results[1:]:
            peers[peers_data.get("target_ticker")] = peers_data

        return {"target" : target , "peers" : peers}
    
    target , peers = get_peers_and_ticker_dict(ticker)

    sem = asyncio.Semaphore(max_concurrency)

    async def one(ticker , data , section , role):
        async with sem : 
            condensed_output = await condense_one(data.get(section) , section ,llm_async , ticker , role)
        return ticker , section , condensed_output
    
    tasks = [] # to queue up all the tasks (how they are going to get in the asyncio.gather() function later , one task -> bundle of 4)

    #iterating through the target dict (contains : section -> section data) -> since calculating with one function involves async with sem , the task automatically gets buncdled up in 4
    for section in SECTION_FOCUS:
        if (target.get(section)) :
            tasks.append(one(target.get("target_ticker" , "target") , target , section , "target"))

    # iterating thorugh the peers dictionary , getting the peer stock and its corresponding dict 
    for peer_ticker , peer_data in peers.items():
        for section in PEER_SECTION_FOCUS:
            if (peer_data.get(section)):
                tasks.append(one(peer_ticker , peer_data , section , "peer"))

    results = await asyncio.gather(*tasks) # tasks = list of tasks bundled as a group of 4

    output_dict : dict[str , dict] = {}
    for ticker , section, condensed_output in results :
        if condensed_output:
            output_dict.setdefault(ticker , {})[section] = condensed_output
    return output_dict

## *CODE TO BE IMPLEMENTED ONCE THE SHARED STATE TICKER IS RECEIVED*
#ticker = state.get("ticker")
ticker = "AAPL"

output_dict = asyncio.run(condense_all(ticker ,  llm_async))
print (output_dict)

    # ***CODE FOR THE OUPUT DICT TO GET APPENDED IN THE SHARED STATE***