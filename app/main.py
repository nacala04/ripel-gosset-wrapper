from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel
import os, uuid, httpx

API_KEY = os.getenv("PROGRAM_FINDER_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

app = FastAPI(title="RIPEL + Gosset Wrapper", version="1.0")

class QueryBody(BaseModel):
    query: str
    max_searches: int = 2
    max_results: int = 5

class MCPReq(BaseModel):
    query: str

@app.get("/health")
def health():
    return {"ok": True}

def unauthorized(auth: str | None):
    return (not API_KEY) or (auth != f"Bearer {API_KEY}")

# ---- LIVE Gosset Web Research Agent (safe import) ----
@app.post("/gosset/research")
def gosset_research(body: QueryBody, authorization: str | None = Header(None)):
    if unauthorized(authorization):
        raise HTTPException(status_code=401, detail="Unauthorized")
    if not ANTHROPIC_API_KEY:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY is not set")

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
                "evidence": [{"type": "link","title": (u or "")[:30], "url": u} for u in r.get("sources", [])],
                "confidence": 0.6
            })
        return {"query_id": str(uuid.uuid4()), "results": items}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gosset agent error: {e}")

# ---- MCPS-style endpoints via public APIs (works from web apps) ----
# PubMed
@app.post("/mcps/pubmed")
def mcps_pubmed(body: MCPReq, authorization: str | None = Header(None)):
    if unauthorized(authorization):
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        q = body.query.strip()
        if not q:
            return {"source":"pubmed","items":[]}
        params = {"db":"pubmed","retmode":"json","retmax":"5","term": q}
        with httpx.Client(timeout=20.0) as client:
            s = client.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi", params=params).json()
            ids = ",".join(s.get("esearchresult",{}).get("idlist",[]))
            if not ids:
                return {"source":"pubmed","items":[]}
            summary = client.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi",
                                 params={"db":"pubmed","retmode":"json","id": ids}).json()
        items=[]
        for pmid,meta in summary.get("result",{}).items():
            if pmid=="uids": continue
            items.append({
                "id": pmid,
                "title": meta.get("title",""),
                "summary": "; ".join([au.get("name","") for au in meta.get("authors",[])[:3]]),
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                "tags":["paper"]
            })
        return {"source":"pubmed","items":items}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"pubmed error: {e}")

# ClinicalTrials.gov
@app.post("/mcps/clinicaltrials")
def mcps_trials(body: MCPReq, authorization: str | None = Header(None)):
    if unauthorized(authorization):
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        q = body.query.strip()
        if not q:
            return {"source":"clinicaltrials","items":[]}
        with httpx.Client(timeout=20.0) as client:
            r = client.get("https://clinicaltrials.gov/api/v2/studies",
                           params={"query.term": q, "pageSize": 5}).json()
        items=[]
        for st in r.get("studies",[]):
            idn = st.get("identificationModule",{})
            prot = st.get("protocolSection",{})
            items.append({
                "id": idn.get("nctId",""),
                "title": idn.get("officialTitle") or idn.get("briefTitle",""),
                "summary": prot.get("statusModule",{}).get("overallStatus",""),
                "url": f"https://clinicaltrials.gov/study/{idn.get('nctId','')}",
                "tags":["trial"]
            })
        return {"source":"clinicaltrials","items":items}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"trials error: {e}")

# OpenTargets (search targets)
@app.post("/mcps/opentargets")
def mcps_opentargets(body: MCPReq, authorization: str | None = Header(None)):
    if unauthorized(authorization):
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        q = body.query.strip()
        if not q:
            return {"source":"opentargets","items":[]}
        query = """
        query Q($q:String!){ search(query:$q){ hits{ id name entity object{ ... on Target { approvedSymbol approvedName } } } } }
        """
        payload = {"query":query,"variables":{"q": q}}
        with httpx.Client(timeout=20.0) as client:
            r = client.post("https://api.platform.opentargets.org/api/v4/graphql", json=payload).json()
        items=[]
        for hit in r.get("data",{}).get("search",{}).get("hits",[])[:5]:
            tgt = hit.get("object",{})
            sym = tgt.get("approvedSymbol") or hit.get("name") or ""
            ensg = hit.get("id") or ""
            items.append({
                "id": ensg,
                "title": f"{sym} ({ensg})",
                "summary": tgt.get("approvedName",""),
                "url": f"https://platform.opentargets.org/target/{ensg}",
                "tags":["opentargets"]
            })
        return {"source":"opentargets","items":items}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"opentargets error: {e}")
