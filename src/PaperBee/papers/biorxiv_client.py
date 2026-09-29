"""
bioRxiv search through the official API (https://api.biorxiv.org).

findpapers scrapes bioRxiv's HTML search page, which now sits behind a Cloudflare bot check and returns
403 to scripts. The API is not blocked but has no keyword search: it lists every preprint posted in a
date range. We page through that list and apply the findpapers query to titles and abstracts locally.
"""

import logging
import re
import time
from datetime import date
from typing import Any, Callable, Dict, List

import requests

API_URL = "https://api.biorxiv.org/details/biorxiv"
_TOKEN = re.compile(r"\[[^\]]+\]|\(|\)|\bAND NOT\b|\bAND\b|\bOR\b")

logger = logging.getLogger(__name__)


def _normalize(text: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text.lower()).split())


def compile_query(query: str) -> Callable[[str], bool]:
    """
    Compiles a findpapers query (``[term]``, ``AND``, ``OR``, ``AND NOT``, parentheses) into a predicate
    over text. Terms match case-insensitively at a word start, ignoring punctuation, so ``[DNA language model]``
    also matches "DNA-language models".
    """
    tokens = _TOKEN.findall(query)
    if _TOKEN.sub("", query).strip():
        e = f"Unsupported syntax in query: {query}"
        raise ValueError(e)

    terms = [_normalize(t[1:-1]) for t in tokens if t.startswith("[")]
    patterns = [re.compile(r"(?<![a-z0-9])" + re.escape(t)) for t in terms]
    operators = {"(": "(", ")": ")", "AND": " and ", "OR": " or ", "AND NOT": " and not "}
    expression, term_index = "", 0
    for token in tokens:
        if token.startswith("["):
            expression += f"m[{term_index}]"
            term_index += 1
        else:
            expression += operators[token]
    code = compile(expression, "<query>", "eval")  # built only from the fixed tokens above

    def matches(text: str) -> bool:
        normalized = _normalize(text)
        return bool(eval(code, {"__builtins__": {}}, {"m": [bool(p.search(normalized)) for p in patterns]}))  # noqa: S307

    return matches


def _get_page(since: date, until: date, cursor: int, attempts: int = 3) -> Dict[str, Any]:
    for attempt in range(attempts):
        try:
            response = requests.get(f"{API_URL}/{since}/{until}/{cursor}", timeout=60)
            response.raise_for_status()
            return response.json()  # type: ignore[no-any-return]
        except (requests.RequestException, ValueError):
            if attempt == attempts - 1:
                raise
            time.sleep(5)
    return {}


def search_biorxiv(query: str, since: date, until: date) -> List[Dict[str, Any]]:
    """
    Returns new bioRxiv preprints (first versions) posted between ``since`` and ``until`` whose title or
    abstract matches ``query``, as dicts in the findpapers paper format.
    """
    matches = compile_query(query)
    papers: List[Dict[str, Any]] = []
    cursor, total = 0, None
    while total is None or cursor < total:
        page = _get_page(since, until, cursor)
        message = page.get("messages", [{}])[0]
        collection = page.get("collection", [])
        if message.get("status") != "ok" or not collection:
            break
        total = int(message.get("total", 0))
        cursor += len(collection)
        for preprint in collection:
            if str(preprint.get("version")) != "1":
                continue
            if not matches(f"{preprint.get('title', '')} {preprint.get('abstract', '')}"):
                continue
            papers.append({
                "title": " ".join(preprint.get("title", "").split()),
                "abstract": preprint.get("abstract"),
                "authors": [a.strip() for a in preprint.get("authors", "").split(";") if a.strip()],
                "databases": ["bioRxiv"],
                "doi": preprint.get("doi"),
                "keywords": [],
                "publication_date": preprint.get("date"),
                "urls": [f"https://doi.org/{preprint.get('doi')}"],
            })
    logger.info(f"bioRxiv API: {len(papers)} matching preprints out of {cursor} posted since {since}")
    return papers
