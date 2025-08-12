from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel
import os, uuid

API_KEY = os.getenv("PROGRAM_FINDER_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

app = FastAPI(title="RIPEL + Gosset Wrapper (Safe Import)", version="0.3")

# -------- Models --------
class QueryBody(BaseModel):
    query: str
    max_searches: int = 2
    max_results: int = 5

class MCPReq(BaseModel):
    query: str

# -------- Health --------
@app.get("/health")
def health():
    return {"ok": True}

def unauthorized(auth: str | None):
    return (not API_KEY) or (auth != f"Bearer {API_KEY}")

# -------- Web Research Agent (LIVE, safe import) --------
@app.post("/gosset/research")
def gosset_research(body: QueryBody, authorization: str | None = Header(None)):
    if unauthorized(authorization):
        raise HTTPException(status_code=401, detail="Unauthorized")

    if not ANTHROPIC_API_KEY:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY is not set in Railway Variables")

    # Import inside the handler so startup never crashes
    try:
        from web_research_agent.agent import process_task
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gosset import error: {e}")

    try:
        data = process_task(
            body.query,
            max_searches=body.max_searches,
            max_results=body.max_results
        )
        items = []
        for r in data.get("results", []):
            items.append({
                "program_id": str(uuid.uuid4()),
                "title": r.get("title") or r.get("company_name") or "Result",
                "target": r.get("target") or "",
                "stage": r.get("development_stage") or r.get("stage") or "research",
                "rationale": r.get("summary") or r.get("comments") or "",
                "suggested_next_steps": r.get("next_steps", []),
                "evidence": [{"type": "link", "title": (u or "")[:30], "url": u} for u in r.get("sources", [])],
                "confidence": 0.6
            })
        return {"query_id": str(uuid.uuid4()), "results": items}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gosset agent error: {e}")

# -------- MCPS placeholders (can be made live later) --------
@app.post("/mcps/pubmed")
def mcps_pubmed(body: MCPReq, authorization: str | None = Header(None)):
    if unauthorized(authorization):
        raise HTTPException(status_code=401, detail="Unauthorized")
    return {"source":"pubmed","items":[
        {"id":"pmid_demo_1","title":"SHP2 inhibitors in KRAS tumors","summary":"Review on SHP2.","url":"https://pubmed.ncbi.nlm.nih.gov/00000001/","tags":["paper"]},
        {"id":"pmid_demo_2","title":"Allosteric pockets of PTPN11","summary":"Allosteric binding.","url":"https://pubmed.ncbi.nlm.nih.gov/00000002/","tags":["paper"]}
    ]}

@app.post("/mcps/clinicaltrials")
def mcps_clinicaltrials(body: MCPReq, authorization: str | None = Header(None)):
    if unauthorized(authorization):
        raise HTTPException(status_code=401, detail="Unauthorized")
    return {"source":"clinicaltrials","items":[
        {"id":"nct_demo_1","title":"SHP2 inhibitor trial (KRAS)","summary":"Phase I dose escalation.","url":"https://clinicaltrials.gov/study/NCT00000001","tags":["trial"]},
        {"id":"nct_demo_2","title":"KRASi + SHP2i combo","summary":"Phase II signal seeking.","url":"https://clinicaltrials.gov/study/NCT00000002","tags":["trial"]}
    ]}

@app.post("/mcps/opentargets")
def mcps_opentargets(body: MCPReq, authorization: str | None = Header(None)):
    if unauthorized(authorization):
        raise HTTPException(status_code=401, detail="Unauthorized")
    return {"source":"opentargets","items":[
        {"id":"ot_demo_1","title":"PTPN11 disease associations","summary":"Strong associations.","url":"https://platform.opentargets.org/target/ENSG00000179295","tags":["opentargets"]},
        {"id":"ot_demo_2","title":"PTPN11 pathway links","summary":"RAS/MAPK links.","url":"https://platform.opentargets.org","tags":["opentargets"]}
    ]}
