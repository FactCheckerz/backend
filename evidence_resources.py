"""
Feeds the 'External Medical Knowledge Sources' box: pulls abstracts from
PubMed for a claim's topic and hands them to retrieval.index_documents().

WHY PubMed via Biopython's Entrez client instead of scraping:
It's the actual source WHO/major fact-checkers cite, has a stable free API,
and Biopython handles the XML parsing + rate limiting for you (3 req/s
without a key, 10 req/s with one — set ENTREZ_API_KEY in .env).
"""
import re

from Bio import Entrez
from config import ENTREZ_EMAIL, ENTREZ_API_KEY
from retrieval import index_documents
from progress import step, done

Entrez.email = ENTREZ_EMAIL
if ENTREZ_API_KEY:
    Entrez.api_key = ENTREZ_API_KEY


def fetch_pubmed_evidence(topic_query: str, max_results: int = 10) -> list[dict]:
    step(f"Searching PubMed for: \"{topic_query}\"...")
    handle = Entrez.esearch(db="pubmed", term=topic_query, retmax=max_results, sort="relevance")
    ids = Entrez.read(handle)["IdList"]
    if not ids:
        done("PubMed search returned no results.")
        return []

    step(f"Found {len(ids)} PubMed article(s), fetching abstracts...")
    handle = Entrez.efetch(db="pubmed", id=ids, rettype="abstract", retmode="xml")
    records = Entrez.read(handle)["PubmedArticle"]

    docs = []
    for rec in records:
        try:
            article = rec["MedlineCitation"]["Article"]
            title = str(article.get("ArticleTitle", ""))
            abstract_parts = article.get("Abstract", {}).get("AbstractText", [])
            abstract = " ".join(str(p) for p in abstract_parts)
            pmid = str(rec["MedlineCitation"]["PMID"])
            if not abstract:
                continue
            docs.append({
                "id": f"pubmed_{pmid}",
                "text": f"{title}. {abstract}",
                "source": "PubMed",
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            })
        except (KeyError, TypeError):
            continue
    done(f"Parsed {len(docs)} usable PubMed abstract(s).")
    return docs


def _clean_query(query) -> str:
    """LLM-written queries can be lists, half-written boolean expressions, or
    junk like "(" — PubMed rejects those with an error. Reduce to plain
    keywords; PubMed ANDs them itself."""
    if isinstance(query, list):
        query = " ".join(map(str, query))
    words = re.findall(r"[A-Za-z0-9][A-Za-z0-9'-]*", str(query or ""))
    words = [w for w in words if w.upper() not in ("AND", "OR", "NOT")]
    return " ".join(words) if any(len(w) > 2 for w in words) else ""


def refresh_corpus_for_topic(*queries: str):
    """Call this before verifying a claim on a topic you haven't indexed yet.
    Tries each query in order (most specific first) until PubMed returns
    something — PubMed ANDs every term, so a narrow query often comes back
    empty where a broader one doesn't."""
    step("Stage 4a: refreshing evidence corpus from PubMed...")
    docs = []
    for query in dict.fromkeys(q for q in map(_clean_query, queries) if q):
        try:
            docs = fetch_pubmed_evidence(query)
        except Exception as e:  # PubMed errors / outages shouldn't kill the whole request
            step(f"PubMed search failed for \"{query}\" ({e}) — trying next query.")
            continue
        if docs:
            break
    if docs:
        step(f"Indexing {len(docs)} document(s) (embedding + BM25)...")
        index_documents(docs)
        done("Indexing complete.")
    done("Stage 4a complete.")
    return docs

# For WHO / govt. sources: no clean free API exists, so the practical approach
# for a capstone is a small curated seed corpus (WHO fact-sheet pages you fetch
# once with requests+trafilatura and cache as JSON), loaded the same way via
# index_documents(). Wire that in as `load_seed_corpus("who_factsheets.json")`
# once you've scraped a starter set — don't build a live WHO scraper, it's not
# worth the engineering time relative to the marks it earns.
