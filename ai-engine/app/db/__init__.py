"""Tenant-scoped DB layer (D-07): pool, schema gate, ai_vectors access.

Consumed by the document pipeline (/v1/documents) and the RAG search layer
(03-06). Every DB access validates schema_name against ``^school_[0-9]+$``
and checks existence — no global fallback (D-07/D-09, ROADMAP criterion 4).
"""
