# Risk Data Reconciliation & Limit Monitoring Tool

A Python pipeline that automates daily reconciliation of position data across
two independently-sourced systems (Front Office and Risk System), flags risk
limit breaches, classifies root causes with fully explainable rules, and
produces stakeholder-ready commentary and an auditable issue log.

Built as a portfolio project mirroring the BAU control work described in the
**Risk Reporting & Middle Office** and **Risk Controllers** tracks of a
Global Risk & Compliance role (reconciliation, exception investigation,
limit monitoring, SOP/control documentation, issue-log tracking).

> Full design rationale lives in `docs/` — start with the PRD if you want
> the "why" before the "how."

## Why this exists

Banks record the same trade in multiple systems that are fed independently
and occasionally disagree. Reconciling them before they hit a risk report or
a regulatory filing is normally manual, slow, and inconsistent across
analysts. This tool automates the mechanical matching and triage so analysts
can spend their time on genuinely ambiguous breaks.

## Architecture

```
Raw CSVs (different schemas)
        │
        ▼
  Mapping configs (JSON)  ──►  normalize.py    →  canonical schema
        │
        ▼
  reconcile.py   →  break_category (missing / value / currency / clean)
        │
        ▼
  limits.py      →  limit breach flags per counterparty/asset_class
        │
        ▼
  root_cause.py  →  deterministic, explainable root-cause tags
        │
        ▼
  commentary.py  →  plain-English stakeholder commentary
        │
        ▼
  issue_log.py + report.py  →  issue_log.csv, risk_reconciliation_report.xlsx
        │
        ▼
  tableau_extract.py  →  tableau_extract.csv  (feeds Tableau dashboard)
```

The core design choice: **all source-specific schema knowledge lives in a
declarative JSON mapping config**, never hardcoded inside the pipeline.
`demo_extensibility.py` proves this live by onboarding a third source system
with a brand-new schema, using zero changes to any core module.

## Project structure

```
risk_recon_project/
├── data/
│   ├── front_office_positions.csv   # raw Source A (different schema)
│   ├── risk_system_positions.csv    # raw Source B (different schema)
│   └── limits.csv                   # risk limits reference table
├── config/
│   ├── front_office_mapping.json    # Source A → canonical schema mapping
│   ├── risk_system_mapping.json     # Source B → canonical schema mapping
│   └── control_params.json          # tolerance %, classification cutoffs
├── src/
│   ├── normalize.py                 # schema mapping / normalization
│   ├── reconcile.py                 # cross-source matching & break detection
│   ├── limits.py                    # limit monitoring
│   ├── root_cause.py                # deterministic root-cause classification
│   ├── commentary.py                # templated commentary generation
│   ├── issue_log.py                 # issue log construction
│   ├── report.py                    # formatted Excel report writer
│   ├── tableau_extract.py           # Tableau-ready CSV export
│   ├── run_pipeline.py              # MAIN ENTRY POINT — runs everything
│   ├── demo_extensibility.py        # live proof of config-only extensibility
│   └── test_pipeline.py             # lightweight test suite
├── output/                          # generated on each run (gitignored in spirit)
├── docs/                            # PRD + 3 supporting design documents
└── requirements.txt
```

## Running it

```bash
pip install -r requirements.txt
cd src
python run_pipeline.py
```

This produces, in `output/`:
- `issue_log.csv` — the auditable issue log (every break/breach, root cause, commentary, status)
- `risk_reconciliation_report.xlsx` — a 4-sheet stakeholder report (Summary, Issue Log, Reconciliation Detail, Limit Monitoring) with breach rows highlighted
- `tableau_extract.csv` — flattened export ready to plug into a Tableau dashboard

Run the tests:
```bash
cd src
python test_pipeline.py
```

Prove the extensibility claim live:
```bash
cd src
python demo_extensibility.py
```

## Design principles

- **Explainable over clever.** Root-cause classification is rules-based, not
  ML. Every tag traces to an inspectable condition — auditability matters
  more than predictive sophistication in a risk/compliance context.
- **Config over code.** Source schema knowledge lives in JSON mapping files.
  Onboarding a new source system is a config change, not a refactor.
- **Honest fallbacks.** When no rule confidently classifies a break, the
  system says "Unclassified — Manual Review" rather than forcing a guess.
- **Auditable commentary.** Stakeholder-facing text is templated, not
  free-form generated, so every sentence is traceable to its inputs.

## What's intentionally out of scope (MVP)

- Live system integration / real bank data
- ML-based root-cause prediction (explainability was prioritized instead)
- Workflow/ticketing integration (issue log is a flat file)
- Alteryx ETL layer (tracked as a parallel workstream, not a blocker)

See `docs/01_PRD_Risk_Reconciliation_Tool.docx` for full scope rationale.

## Companion documents (`docs/`)

1. **PRD** — problem statement, goals, scope, success metrics, risks
2. **Data Dictionary & Source Schema Spec** — canonical schema, both raw
   source schemas, mapping configs, planted data-quality issue design
3. **Reconciliation & Control Logic Spec** — matching rules, tolerance
   thresholds, root-cause decision logic, commentary templates
4. **Interview Talking Points** — pitch, resume bullet, anticipated Q&A
# Risk-Data-Reconciliation-Limit-Monitoring-Tool
