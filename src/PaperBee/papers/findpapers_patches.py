"""
Compatibility patches for findpapers, which is no longer maintained.

The arXiv API now returns ``opensearch:totalResults``, ``arxiv:comment``, ``arxiv:doi`` and
``arxiv:journal_ref`` as plain-text elements without XML attributes. xmltodict then yields a ``str``
where findpapers expects a dict with a ``#text`` key, so ``.get("#text")`` raises, findpapers swallows
the error, and every arXiv search silently returns no papers.

findpapers also pages through every arXiv match and only then drops papers older than ``since``. Results
are sorted newest first, so we cut the result off at the first older paper to stop paging there.
"""

import datetime
from typing import Any, Optional

from findpapers.searchers import arxiv_searcher

_ARXIV_TEXT_FIELDS = ("arxiv:comment", "arxiv:doi", "arxiv:journal_ref")
_original_get_api_result = arxiv_searcher._get_api_result


def _as_text_node(value: Any) -> Any:
    return {"#text": value} if isinstance(value, str) else value


def _get_api_result(search: Any, start_record: Optional[int] = 0) -> Any:
    result = _original_get_api_result(search, start_record)
    feed = (result or {}).get("feed")
    if not feed:
        return result

    feed["opensearch:totalResults"] = _as_text_node(feed.get("opensearch:totalResults"))
    entries = feed.get("entry", [])
    entries = entries if isinstance(entries, list) else [entries]
    for entry in entries:
        for field in _ARXIV_TEXT_FIELDS:
            if field in entry:
                entry[field] = _as_text_node(entry[field])

    if search.since is not None:
        recent = [e for e in entries if _published_date(e) >= search.since]
        if len(recent) < len(entries):
            feed["entry"] = recent
            feed["opensearch:totalResults"] = {"#text": str((start_record or 0) + len(recent))}
    return result


def _published_date(entry: dict) -> datetime.date:
    return datetime.datetime.strptime(entry.get("published", "")[:10], "%Y-%m-%d").date()


arxiv_searcher._get_api_result = _get_api_result
