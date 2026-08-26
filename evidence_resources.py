"""
Feeds the 'External Medical Knowledge Sources' box: pulls abstracts from
PubMed for a claim's topic and hands them to retrieval.index_documents().

WHY PubMed via Biopython's Entrez client instead of scraping:
It's the actual source WHO/major fact-checkers cite, has a stable free API,
and Biopython handles the XML parsing + rate limiting for you (3 req/s
without a key, 10 req/s with one — set ENTREZ_API_KEY in .env).
"""
from Bio import Entrez
from config import ENTREZ_EMAIL, ENTREZ_API_KEY
from retrieval import index_documents

Entrez.email = ENTREZ_EMAIL
if ENTREZ_API_KEY:
    Entrez.api_key = ENTREZ_API_KEY


def fetch_pubmed_evidence(topic_query: str, max_results: int = 10) -> list[dict]:
    handle = Entrez.esearch(db="pubmed", term=topic_query, retmax=max_results, sort="relevance")
    ids = Entrez.read(handle)["IdList"]
    if not ids:
        return []

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
    return docs


def refresh_corpus_for_topic(topic_query: str):
    """Call this before verifying a claim on a topic you haven't indexed yet."""
    docs = fetch_pubmed_evidence(topic_query)
    if docs:
        index_documents(docs)
    return docs

# For WHO / govt. sources: no clean free API exists, so the practical approach
# for a capstone is a small curated seed corpus (WHO fact-sheet pages you fetch
# once with requests+trafilatura and cache as JSON), loaded the same way via
# index_documents(). Wire that in as `load_seed_corpus("who_factsheets.json")`
# once you've scraped a starter set — don't build a live WHO scraper, it's not
# worth the engineering time relative to the marks it earns.
