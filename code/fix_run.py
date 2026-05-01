import os
import sys
import csv
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from utils.corpus_loader import CorpusLoader
from utils.retriever import Retriever
from utils.classifier import TicketClassifier
from utils.escalation import EscalationChecker
from utils.claude_client import ClaudeClient

def map_action_to_status(action):
    return "escalated" if action == "ESCALATE" else "replied"

def map_request_type(rt):
    mapping = {
        "bug_report": "bug",
        "feature_request": "feature_request",
        "faq": "product_issue",
        "billing_inquiry": "product_issue",
        "account_access": "product_issue",
        "fraud_report": "product_issue",
        "complaint": "product_issue",
        "data_request": "product_issue",
        "general_inquiry": "product_issue",
    }
    return mapping.get(rt, "product_issue")

def process(input_csv, output_csv):
    corpus_loader = CorpusLoader()
    retriever = Retriever(corpus_loader)
    classifier = TicketClassifier()
    escalation_checker = EscalationChecker()
    claude = ClaudeClient()

    rows = []
    with open(input_csv, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    results = []
    for i, row in enumerate(rows, 1):
        issue = row.get("Issue", row.get("issue", ""))
        subject = row.get("Subject", row.get("subject", ""))
        company = row.get("Company", row.get("company", ""))

        domain_hint = company.lower() if company and company.lower() != "none" else ""

        print(f"[{i}/{len(rows)}] Processing: {subject[:50]}...", end=" ", flush=True)

        try:
            classification = classifier.classify(subject, issue, domain_hint)
            domain = classification["domain"]
            product_area = classification["product_area"]
            request_type = classification["request_type"]
            sensitivity = classification["sensitivity"]

            should_escalate, escalation_reason = escalation_checker.check(
                subject, issue, domain, product_area, request_type, sensitivity
            )

            retrieved_chunks = retriever.retrieve(
                query=f"{subject} {issue}",
                domain=domain,
                top_k=5
            )

            ticket = {"ticket_id": str(i), "subject": subject, "body": issue, "domain": domain_hint}

            if should_escalate:
                response = (
                    f"Thank you for reaching out. Your request has been escalated to our "
                    f"human support team because it involves {escalation_reason}. "
                    f"A specialist will follow up with you shortly."
                )
                justification = (
                    f"Escalated because: {escalation_reason}. "
                    f"This ticket requires human verification and cannot be safely resolved automatically."
                )
                status = "escalated"
            else:
                response = claude.generate_response(
                    ticket=ticket,
                    classification=classification,
                    retrieved_chunks=retrieved_chunks,
                )
                justification = (
                    f"Replied based on corpus documentation. "
                    f"Domain: {domain}, Area: {product_area}. "
                    f"Top source: {retrieved_chunks[0]['title'] if retrieved_chunks else 'N/A'}."
                )
                status = "replied"

            results.append({
                "issue": issue,
                "subject": subject,
                "company": company,
                "response": response,
                "product_area": product_area,
                "status": status,
                "request_type": map_request_type(request_type),
                "justification": justification,
            })
            print(f"✅ {status.upper()}")

        except Exception as e:
            print(f"❌ ERROR: {e}")
            results.append({
                "issue": issue,
                "subject": subject,
                "company": company,
                "response": "We were unable to process your request. A support agent will assist you shortly.",
                "product_area": "general",
                "status": "escalated",
                "request_type": "product_issue",
                "justification": f"Processing error: {str(e)}",
            })

    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        fieldnames = ["issue", "subject", "company", "response", "product_area", "status", "request_type", "justification"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    print(f"\n✅ Done! Output saved to: {output_csv}")

if __name__ == "__main__":
    input_csv = r"C:\Users\dimpa\hackerrank-orchestrate-may26\support_tickets\support_tickets.csv"
    output_csv = r"C:\Users\dimpa\hackerrank-orchestrate-may26\support_tickets\output.csv"
    process(input_csv, output_csv)