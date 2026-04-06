# Legal KB Scope (Phase 3)

Last updated: 2026-04-06
Owner: Phase 3 (Legal Assistant)

This document defines the legal knowledge base corpus for the assistant retriever.

## Priority Tiers

## Tier 0 (must-have)

- Constitution of India (latest amended text)
- BNS 2023, BNSS 2023, BSA 2023
- IPC 1860, CrPC 1973, Evidence Act 1872 (tagged superseded)
- CPC 1908

## Tier 1 (high-value statutes)

- Indian Contract Act, 1872
- Transfer of Property Act, 1882
- Specific Relief Act, 1963
- Limitation Act, 1963
- Companies Act, 2013
- IT Act, 2000 (+ 2008 amendment context)
- Consumer Protection Act, 2019
- RTI Act, 2005
- Motor Vehicles Act, 1988
- POCSO Act, 2012
- Prevention of Corruption Act, 1988
- Arbitration and Conciliation Act, 1996
- Insolvency and Bankruptcy Code, 2016

## Tier 2 (procedural and court rules)

- Supreme Court Rules, 2013
- selected High Court Rules (based on jurisdiction rollout)
- Civil Rules of Practice
- Criminal Rules of Practice
- CPC/BNSS order-rule procedural mapping notes

## Tier 3 (secondary sources)

- Law Commission reports (curated)
- legal maxims and glossary
- NJDG procedural guides
- Bar Council of India rules

## Source Policy

- Prefer official structured sources (India Code first)
- Store source URL + retrieval timestamp + version hash
- Keep immutable source snapshots for reproducibility

## Chunking Policy

- Primary unit: section/article/rule
- Include full sub-clauses in same chunk when feasible
- Do not chunk by page boundaries

Required metadata per chunk:

- `source_type`
- `act_name`
- `section_or_article`
- `chapter_or_part`
- `year`
- `jurisdiction`
- `is_superseded`
- `superseded_by`
- `source_url`
- `source_version_hash`

## Supersession Policy

- IPC -> BNS
- CrPC -> BNSS
- Evidence Act -> BSA

Retriever behavior requirement:

- On old-law query terms, return both legacy section and mapped new-law section where available
- Explicitly label legacy chunks as superseded in assistant responses
