"""PII redaction: regex for structured identifiers + spaCy NER for names.

Run before any text reaches an LLM or gets written to a log (TRD security
section) — `redact()` is the only thing that should ever touch an LLM
prompt or `audit_log.detail`; `raw_text` stays untouched with tighter
access control (05_Backend_Schema.md notes).
"""

import re
from functools import lru_cache

import spacy

_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
_PHONE_RE = re.compile(r"(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")
# Card-shaped: 13-19 digits, optionally grouped by spaces/dashes.
_CARD_RE = re.compile(r"\b(?:\d[ -]?){12,18}\d\b")
# Any other bare run of 6+ digits — account numbers, transaction IDs, etc.
_ACCOUNT_NUMBER_RE = re.compile(r"\b\d{6,}\b")


@lru_cache(maxsize=1)
def _load_nlp():
    return spacy.load("en_core_web_sm")


def redact(text: str) -> str:
    redacted = _EMAIL_RE.sub("[REDACTED_EMAIL]", text)
    redacted = _PHONE_RE.sub("[REDACTED_PHONE]", redacted)
    redacted = _CARD_RE.sub("[REDACTED_CARD]", redacted)
    redacted = _ACCOUNT_NUMBER_RE.sub("[REDACTED_ACCOUNT]", redacted)

    doc = _load_nlp()(redacted)
    person_spans = [(ent.start_char, ent.end_char) for ent in doc.ents if ent.label_ == "PERSON"]
    for start, end in sorted(person_spans, reverse=True):
        redacted = redacted[:start] + "[REDACTED_NAME]" + redacted[end:]

    return redacted
