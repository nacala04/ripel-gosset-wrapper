from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel
import os, uuid

# ---- TRY to import Gosset modules from YOUR forks ----
# These module names can vary a bit; this tries common options.
# If your deploy logs say "ModuleNotFoundError", tell me and I’ll adjust the import here.
try:
    from web_research_agent import agent as wra_agent   # common
except Exception:
    wra_agent = None

try:
    # Many MCPS repos provide per-source modules or a common entrypoint.
    # We'll call simple helpers below; if import fails, we return friendly samples.
    from mcps import __version__ as _mcps_ok             # just to confirm import
except Exception:
    _mcps_ok = None

API_KEY = os.getenv("PROGRAM_FINDER_API_KEY", "")
ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "")

app = FastAPI(title="RIPEL + Gosset Wrapper", version="0.1")

class QueryBody(BaseModel):
    query: str
    max_searches: int = 2
    max_results: int = 5

def unauthorized(auth: str | None):
    return (not API_KEY) or (auth != f"Bearer {API_KEY}")

@app.get("/health")
def health():
    return {"ok": True}

# ---------- Web Research Agent ----------
@app.post("/gosset/research")
def gosset_research(body: QueryBody, authorization: str | None = Header(None)):
    if unauthorized(authorization):
        raise HTTPException(status_code=401, detail="Unauthorized")

    # If Anthropic is missing or import failed, return a friendly demo payload.
    if not ANTHROPIC_KEY or wra_agent is None:
        return {
            "query_id": str(uuid.uuid4()),
            "results": [{
                "program_id": "demo_web",
                "title": "SHP2 allosteric inhibitors for KRAS-driven tumors",
                "target": "PTPN11 (SHP2)",
                "stage": "research",
                "rationale": "KRAS pathway relevance; tractable chemistry; good literature support.",
                "suggested_next_steps": ["SHP2 enzymatic IC50", "Cell assays in KRAS-mutant lines"],
                "evidence": [{"type": "link", "title": "review", "url": "https://example.org/shp2"}],
                "confidence": 0.7
            }]
        }

    # Real path: call the agent function (names differ between versions).
    # Open your fork’s README for the function name; if it says, e.g., wra_agent.run(query=...)
    # update the line below accordingly and redeploy.
    try:
        # Replace this with the exact call shown in your fork’s README, if needed:
        # e.g. data = wra_agent.run(query=body.query, max_searches=body.max_searches, max_results=body.max_results)
        data = {"results": []}  # placeholder in case your fork exposes a different function
        items = []
        for r in data.get("results", []):
            items.append({
                "program_id": str(uuid.uuid4()),
                "title": r.get("title") or "Result",
                "target": r.get("target") or "",
                "stage": r.get("stage") or "research",
                "rationale": r.get("summary") or "",
                "suggested_next_steps": r.get("next_steps", []),
                "evidence": [{"type":"link","title": (u or "")[:30], "url": u} for u in r.get("sources", [])],
                "confidence": 0.6
            })
        return {"query_id": str(uuid.uuid4()), "results": items}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gosset agent error: {e}")

# ---------- MCPS (PubMed / ClinicalTrials / OpenTargets) ----------
class MCPReq(BaseModel):
    query: str

@app.post("/mcps/pubmed")
def mcps_pubmed(body: MCPReq, authorization: str | None = Header(None)):
    if unauthorized(authorization):
        raise HTTPException(status_code=401, detail="Unauthorized")
    # If not wired yet, return friendly samples
    if _mcps_ok is None:
        return {"source":"pubmed","items":[
            {"id":"pmid_demo_1","title":"SHP2 inhibitors in KRAS tumors","summary":"Review on SHP2.","url":"https://pubmed.ncbi.nlm.nih.gov/00000001/","tags":["paper"]},
            {"id":"pmid_demo_2","title":"Allosteric pockets of PTPN11","summary":"Allosteric binding.","url":"https://pubmed.ncbi.nlm.nih.gov/00000002/","tags":["paper"]}
        ]}
    # TODO: call the real MCPS PubMed function from your fork here (update after checking README)
    return {"source":"pubmed","items":[]}

@app.post("/mcps/clinicaltrials")
def mcps_clinicaltrials(body: MCPReq, authorization: str | None = Header(None)):
    if unauthorized(authorization):
        raise HTTPException(status_code=401, detail="Unauthorized")
    if _mcps_ok is None:
        return {"source":"clinicaltrials","items":[
            {"id":"nct_demo_1","title":"SHP2 inhibitor trial (KRAS)","summary":"Phase I dose escalation.","url":"https://clinicaltrials.gov/study/NCT00000001","tags":["trial"]},
            {"id":"nct_demo_2","title":"KRASi + SHP2i combo","summary":"Phase II signal seeking.","url":"https://clinicaltrials.gov/study/NCT00000002","tags":["trial"]}
        ]}
    return {"source":"clinicaltrials","items":[]}

@app.post("/mcps/opentargets")
def mcps_opentargets(body: MCPReq, authorization: str | None = Header(None)):
    if unauthorized(authorization):
        raise HTTPException(status_code=401, detail="Unauthorized")
    if _mcps_ok is None:
        return {"source":"opentargets","items":[
            {"id":"ot_demo_1","title":"PTPN11 disease associations","summary":"Strong associations.","url":"https://platform.opentargets.org/target/ENSG00000179295","tags":["opentargets"]},
            {"id":"ot_demo_2","title":"PTPN11 pathway links","summary":"RAS/MAPK links.","url":"https://platform.opentargets.org","tags":["opentargets"]}
        ]}
    return {"source":"opentargets","items":[]}
