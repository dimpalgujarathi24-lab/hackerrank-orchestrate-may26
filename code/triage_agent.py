"""
Multi-Domain Support Triage Agent
Handles tickets for HackerRank, Claude Help Center, and Visa Support
"""

import os
import sys
import json
import csv
import re
import logging
from datetime import datetime
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.corpus_loader import CorpusLoader
from utils.retriever import Retriever
from utils.classifier import TicketClassifier
from utils.escalation import EscalationChecker
from utils.claude_client import ClaudeClient
from utils.logger import setup_logger, ChatTranscriptLogger

# ─────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────
SUPPORTED_DOMAINS = {
    "hackerrank": "HackerRank Support",
    "claude": "Claude Help Center",
    "visa": "Visa Support",
}

LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

logger = setup_logger("triage_agent", LOG_DIR / "agent.log")
chat_logger = ChatTranscriptLogger(LOG_DIR / "log.txt")


class TriageAgent:
    """
    Core support triage agent.
    
    For each ticket:
    1. Classifies domain + product area
    2. Checks if escalation is needed
    3. Retrieves relevant corpus chunks
    4. Generates a grounded response via Claude API
    5. Returns structured output
    """

    def __init__(self):
        logger.info("Initializing TriageAgent …")
        self.corpus_loader = CorpusLoader()
        self.retriever = Retriever(self.corpus_loader)
        self.classifier = TicketClassifier()
        self.escalation_checker = EscalationChecker()
        self.claude = ClaudeClient()
        logger.info("TriageAgent ready.")

    # ── Public API ────────────────────────────

    def process_ticket(self, ticket: dict) -> dict:
        """Process a single ticket dict and return structured output."""
        ticket_id = ticket.get("ticket_id", "UNKNOWN")
        subject = ticket.get("subject", "")
        body = ticket.get("body", "")
        domain_hint = ticket.get("domain", "").lower()

        logger.info(f"Processing ticket {ticket_id}: {subject[:60]}")
        chat_logger.log_user(ticket_id, subject, body)

        # 1. Classify
        classification = self.classifier.classify(subject, body, domain_hint)
        domain = classification["domain"]
        product_area = classification["product_area"]
        request_type = classification["request_type"]
        sensitivity = classification["sensitivity"]

        logger.info(
            f"[{ticket_id}] domain={domain}, area={product_area}, "
            f"type={request_type}, sensitivity={sensitivity}"
        )

        # 2. Escalation check
        should_escalate, escalation_reason = self.escalation_checker.check(
            subject, body, domain, product_area, request_type, sensitivity
        )

        # 3. Retrieve relevant docs
        retrieved_chunks = self.retriever.retrieve(
            query=f"{subject} {body}",
            domain=domain,
            top_k=5
        )

        # 4. Generate response
        if should_escalate:
            response_text = self._build_escalation_response(
                escalation_reason, domain, product_area
            )
            action = "ESCALATE"
        else:
            response_text = self.claude.generate_response(
                ticket=ticket,
                classification=classification,
                retrieved_chunks=retrieved_chunks,
            )
            action = "REPLY"

        # 5. Build output
        output = {
            "ticket_id": ticket_id,
            "domain": domain,
            "product_area": product_area,
            "request_type": request_type,
            "sensitivity": sensitivity,
            "action": action,
            "escalation_reason": escalation_reason if should_escalate else "",
            "retrieved_sources": [c["source"] for c in retrieved_chunks[:3]],
            "response": response_text,
        }

        chat_logger.log_agent(ticket_id, action, response_text)
        logger.info(f"[{ticket_id}] → {action}")
        return output

    def process_csv(self, input_path: str, output_path: str):
        """Process all tickets from a CSV and write results to output CSV."""
        input_path = Path(input_path)
        output_path = Path(output_path)

        if not input_path.exists():
            raise FileNotFoundError(f"Input CSV not found: {input_path}")

        tickets = []
        with open(input_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                tickets.append(row)

        logger.info(f"Loaded {len(tickets)} tickets from {input_path}")
        print(f"\n📂  Loaded {len(tickets)} tickets from {input_path.name}")
        print("─" * 60)

        results = []
        for i, ticket in enumerate(tickets, 1):
            tid = ticket.get("ticket_id", f"T{i:04d}")
            print(f"[{i}/{len(tickets)}] Processing {tid} …", end=" ", flush=True)
            try:
                result = self.process_ticket(ticket)
                results.append(result)
                print(f"✅  {result['action']}")
            except Exception as e:
                logger.error(f"Error processing {tid}: {e}", exc_info=True)
                print(f"❌  ERROR: {e}")
                results.append({
                    "ticket_id": tid,
                    "domain": "unknown",
                    "product_area": "unknown",
                    "request_type": "unknown",
                    "sensitivity": "unknown",
                    "action": "ESCALATE",
                    "escalation_reason": f"Processing error: {e}",
                    "retrieved_sources": [],
                    "response": "We were unable to process your request automatically. A support agent will assist you shortly.",
                })

        # Write CSV
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fieldnames = [
            "ticket_id", "domain", "product_area", "request_type",
            "sensitivity", "action", "escalation_reason",
            "retrieved_sources", "response"
        ]
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in results:
                r["retrieved_sources"] = "; ".join(r.get("retrieved_sources", []))
                writer.writerow(r)

        print(f"\n✅  Results written → {output_path}")
        print(f"📝  Chat transcript  → {LOG_DIR / 'log.txt'}")
        return results

    # ── Private helpers ───────────────────────

    def _build_escalation_response(
        self, reason: str, domain: str, product_area: str
    ) -> str:
        domain_label = SUPPORTED_DOMAINS.get(domain, domain.title())
        return (
            f"Thank you for reaching out to {domain_label} Support.\n\n"
            f"Your request has been flagged for review by our human support team "
            f"because it involves {reason.lower()}. "
            f"We want to make sure you receive the most accurate and secure assistance possible.\n\n"
            f"A support specialist from our {product_area} team will follow up with you "
            f"as soon as possible. Please do not share any sensitive account credentials "
            f"or payment information via this channel.\n\n"
            f"We appreciate your patience."
        )
