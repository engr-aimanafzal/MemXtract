"""Global search tools: OpenAlex (scientific papers) and Tavily (general web). Both have free tiers."""
from __future__ import annotations

import re

import requests

from . import config

TIMEOUT = 30


class SearchError(Exception):
    pass


def _abstract_from_inverted_index(inv) -> str:
    if not inv:
        return ""
    positions = {}
    for word, idxs in inv.items():
        for i in idxs:
            positions[i] = word
    return " ".join(positions[i] for i in sorted(positions))


def openalex_search(query: str, n: int = 8) -> list:
    key = config.secret("OPENALEX_API_KEY")
    params = {
        "search": query,
        "per_page": n,
        "filter": "has_abstract:true",
        "select": "id,doi,title,publication_year,cited_by_count,abstract_inverted_index,primary_location,open_access",
    }
    if key:
        params["api_key"] = key
    try:
        r = requests.get("https://api.openalex.org/works", params=params, timeout=TIMEOUT)
    except requests.RequestException as e:
        raise SearchError(f"OpenAlex request failed: {e}")
    if r.status_code == 429:
        raise SearchError("OpenAlex daily free budget reached - try again tomorrow (resets at midnight UTC).")
    if r.status_code in (401, 403):
        raise SearchError("OpenAlex rejected the API key - check OPENALEX_API_KEY in Streamlit secrets.")
    if r.status_code != 200:
        raise SearchError(f"OpenAlex error HTTP {r.status_code}")
    out = []
    for w in r.json().get("results", []):
        loc = w.get("primary_location") or {}
        journal = (loc.get("source") or {}).get("display_name")
        oa = w.get("open_access") or {}
        out.append({
            "title": w.get("title") or "(untitled)",
            "year": w.get("publication_year"),
            "cited_by": w.get("cited_by_count"),
            "journal": journal,
            "url": w.get("doi") or w.get("id"),
            "oa_url": oa.get("oa_url"),
            "abstract": _abstract_from_inverted_index(w.get("abstract_inverted_index")),
            "kind": "paper",
        })
    return out


def tavily_search(query: str, n: int = 5) -> list:
    key = config.secret("TAVILY_API_KEY")
    if not key:
        raise SearchError("TAVILY_API_KEY is not set in Streamlit secrets.")
    try:
        r = requests.post(
            "https://api.tavily.com/search",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"query": query, "search_depth": "basic", "max_results": n, "include_answer": False},
            timeout=TIMEOUT,
        )
    except requests.RequestException as e:
        raise SearchError(f"Tavily request failed: {e}")
    if r.status_code in (401, 403):
        raise SearchError("Tavily rejected the API key - check TAVILY_API_KEY in Streamlit secrets.")
    if r.status_code == 429:
        raise SearchError("Tavily monthly free credits or rate limit reached.")
    if r.status_code != 200:
        raise SearchError(f"Tavily error HTTP {r.status_code}")
    return [{
        "title": x.get("title") or x.get("url"),
        "url": x.get("url"),
        "abstract": x.get("content") or "",
        "kind": "web",
    } for x in r.json().get("results", [])]


_STOP = set("a an the of for in on to and or with what which who how is are was were be been do does did "
            "recent latest typical about from by at as into over under between using use used".split())


def keyword_query(question: str) -> str:
    """Cheap fallback: strip filler words from a question to make a search query."""
    words = [w for w in re.findall(r"[A-Za-z0-9\-\+]+", question) if w.lower() not in _STOP]
    return " ".join(words[:10])
