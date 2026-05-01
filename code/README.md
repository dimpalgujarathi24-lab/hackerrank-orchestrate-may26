# Multi-Domain Support Triage Agent

A terminal-based AI support triage agent that handles tickets across three ecosystems:
- **HackerRank** — developer assessment and hiring platform
- **Claude (Anthropic)** — AI assistant platform
- **Visa** — global payment network

---

## Architecture

```
code/
├── run.py                  # Main CLI entry point
├── requirements.txt
├── agent/
│   └── triage_agent.py     # Core agent orchestrator
├── utils/
│   ├── classifier.py       # Domain + ticket classification
│   ├── escalation.py       # Escalation decision logic
│   ├── corpus_loader.py    # Support doc fetching + caching
│   ├── retriever.py        # TF-IDF document retrieval
│   ├── claude_client.py    # Anthropic API response generation
│   └── logger.py           # Logging + chat transcript
├── data/
│   ├── corpus/             # Cached support documentation (JSON)
│   └── support_issues_sample.csv
└── logs/
    ├── agent.log           # Detailed execution log
    └── log.txt             # Chat transcript (required for submission)
```

---

## How It Works

For each support ticket, the agent:

1. **Classifies** the ticket:
   - Detects domain (HackerRank / Claude / Visa) using keyword matching
   - Identifies product area (billing, account, fraud, proctoring, etc.)
   - Determines request type (FAQ, bug, billing inquiry, fraud report, etc.)
   - Assigns sensitivity level (low / medium / high)

2. **Checks for escalation** using 3-tier logic:
   - Global hard rules (fraud, legal threats, data deletion, breach)
   - Domain-specific rules (disputed plagiarism flags, billing disputes, lost cards)
   - Sensitivity threshold + product area risk matrix

3. **Retrieves relevant documentation** using TF-IDF cosine similarity over the support corpus

4. **Generates a response**:
   - If escalating → safe templated escalation message
   - If replying → calls Claude API with retrieved context as grounding, strictly constrained to corpus

5. **Outputs** structured CSV + human-readable transcript

---

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/interviewstreet/hackerrank-orchestrate-may26.git
cd hackerrank-orchestrate-may26
```

### 2. Copy your code into the repo

Place all files from `code/` into the repo's `code/` directory.

### 3. Install dependencies

```bash
cd code
pip install -r requirements.txt
```

### 4. Set your Anthropic API key

```bash
export ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxx
```

### 5. Run in batch mode (process the CSV)

```bash
python run.py --csv ../support_issues/support_issues.csv --out output.csv
```

### 6. Run in interactive mode (test individual tickets)

```bash
python run.py
```

---

## Output Files

| File | Description |
|------|-------------|
| `output.csv` | Predictions for all tickets |
| `logs/log.txt` | Chat transcript (required for submission) |
| `logs/agent.log` | Detailed debug log |

### output.csv columns

| Column | Description |
|--------|-------------|
| `ticket_id` | Original ticket ID |
| `domain` | Detected domain: hackerrank / claude / visa |
| `product_area` | Sub-area: billing, fraud, account, proctoring, etc. |
| `request_type` | faq / bug_report / billing_inquiry / fraud_report / account_access / etc. |
| `sensitivity` | low / medium / high |
| `action` | REPLY or ESCALATE |
| `escalation_reason` | Why escalated (empty if REPLY) |
| `retrieved_sources` | Top matched documentation sources |
| `response` | Generated support response |

---

## Escalation Logic

The agent escalates (instead of auto-replying) when:

- **Fraud or unauthorized transactions** detected
- **Legal threats** or complaints involving lawyers/lawsuits
- **Account compromise** or security breach reported
- **Data deletion / GDPR** requests
- **Lost or stolen cards** (Visa)
- **Billing disputes** (Claude, HackerRank)
- **Plagiarism flag disputes** (HackerRank)
- **Account access issues** requiring identity verification
- **High sensitivity** signals in the ticket text

---

## Corpus Strategy

The agent uses a two-layer corpus strategy:

1. **Web scraping** (first run): scrapes articles from the official support sites and caches them as JSON in `data/corpus/`
2. **Fallback corpus**: hand-crafted FAQ documents covering common scenarios across all three domains — used when scraping fails or sites are unavailable

All responses are strictly grounded in this corpus. The Claude API is instructed never to fabricate policies or procedures not found in the documentation.

---

## Sample Ticket Flow

```
INPUT:  "Unauthorized transaction on my card. Rs. 4500 at an online merchant."
        domain=visa

  → Classify: domain=visa, area=fraud, type=fraud_report, sensitivity=high
  → Escalate:  YES — "potential fraud or unauthorized transaction"
  → Response:  Safe escalation message directing user to bank + Visa assistance

INPUT:  "How do I cancel my Claude Pro subscription?"
        domain=claude

  → Classify: domain=claude, area=billing, type=billing_inquiry, sensitivity=medium
  → Escalate:  YES — "sensitive billing issue requiring account verification"  
  → Response:  Escalation to billing team

INPUT:  "How does proctoring work during HackerRank assessments?"
        domain=hackerrank

  → Classify: domain=hackerrank, area=proctoring, type=faq, sensitivity=low
  → Escalate:  NO
  → Retrieve:  [Proctoring article, Test environment article, …]
  → Response:  Grounded answer from corpus about webcam, tab-monitoring, etc.
```

---

## Design Decisions

- **No hallucination**: Claude API is constrained via system prompt to only use provided documentation
- **Domain-first retrieval**: corpus is scoped to detected domain before similarity search
- **Multi-signal escalation**: three independent escalation layers ensure no sensitive ticket slips through
- **Graceful fallback**: if API fails, the top retrieved chunk is used directly as a response
- **Caching**: corpus is scraped once and cached, making subsequent runs fast and offline-capable
