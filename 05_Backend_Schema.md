# Backend Schema — ResolveIQ

## users
| column | type | notes |
|---|---|---|
| id | uuid PK | |
| email | text unique | |
| password_hash | text | bcrypt/argon2 |
| role | enum(agent, admin) | enforced at API layer |
| created_at | timestamp | |

## customers (Feature 2)
| column | type | notes |
|---|---|---|
| id | uuid PK | |
| masked_identifier | text | display-safe identifier, no raw PII |
| created_at | timestamp | |

## tickets
| column | type | notes |
|---|---|---|
| id | uuid PK | |
| customer_id | uuid FK -> customers.id | links tickets across channels (Feature 2) |
| channel | text | email, chat, form, etc. |
| raw_text | text | original message |
| redacted_text | text | PII-masked, used for LLM calls/logging |
| category | text | payment_failure, refund_delay, account_lock, dispute, general_query, etc. |
| urgency_score | float | 0-1, from trained classifier |
| breach_risk_score | float | 0-1, from SLA model (Feature 3) |
| status | enum(new, classified, drafted, resolved, escalated) | |
| assigned_agent_id | uuid FK -> users.id | nullable until picked up |
| created_at | timestamp | |
| updated_at | timestamp | |

## ticket_drafts
| column | type | notes |
|---|---|---|
| id | uuid PK | |
| ticket_id | uuid FK -> tickets.id | |
| draft_text | text | AI-generated reply |
| confidence | float | |
| source_chunk_ids | uuid[] | which kb_chunks were used |
| created_at | timestamp | |

## ticket_resolutions
| column | type | notes |
|---|---|---|
| id | uuid PK | |
| ticket_id | uuid FK -> tickets.id | |
| final_text | text | what was actually sent |
| action | enum(approved, edited, escalated) | |
| agent_id | uuid FK -> users.id | |
| edit_distance | float | nullable, populated when action = edited (feeds Feature 4) |
| escalation_note | text | nullable |
| created_at | timestamp | |

## kb_documents
| column | type | notes |
|---|---|---|
| id | uuid PK | |
| title | text | |
| source_type | enum(help_doc, resolved_ticket) | |
| uploaded_by | uuid FK -> users.id | |
| created_at | timestamp | |

## kb_chunks
| column | type | notes |
|---|---|---|
| id | uuid PK | |
| document_id | uuid FK -> kb_documents.id | |
| content | text | chunk text |
| embedding | vector | pgvector column |
| retrieval_boost | float | default 1.0, adjusted by feedback loop |
| times_retrieved | int | default 0 |
| times_corrected_against | int | default 0 |

## correction_signals
| column | type | notes |
|---|---|---|
| id | uuid PK | |
| ticket_id | uuid FK -> tickets.id | |
| draft_id | uuid FK -> ticket_drafts.id | |
| diff_summary | text | what changed between draft and final |
| affected_chunk_ids | uuid[] | which kb_chunks this correction should influence |
| created_at | timestamp | |

## audit_log
| column | type | notes |
|---|---|---|
| id | uuid PK | |
| ticket_id | uuid FK -> tickets.id | |
| event_type | text | classified / drafted / reviewed / escalated / resolved |
| detail | jsonb | full reasoning snapshot (scores, sources, model version) |
| actor | text | "system" or agent_id |
| created_at | timestamp | |

## Notes
- `correction_signals` + `retrieval_boost` on `kb_chunks` implement the
  feedback loop (Feature 1): after each correction, a background job adjusts
  `retrieval_boost` on affected chunks.
- `customer_id` on `tickets` is the entire mechanism for Feature 2 — no
  separate service needed, just a join + a summarization step at draft time.
- `breach_risk_score` on `tickets` is written by the Feature 3 model at
  classification time and used to sort the queue view.
- `edit_distance` on `ticket_resolutions` is the core input for the Feature 4
  coaching view — aggregate it per agent, no new backend logic required.
- `redacted_text` is what ever gets sent to an LLM or written into
  `audit_log.detail` — `raw_text` is kept separately with tighter access control.
