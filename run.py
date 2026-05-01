#!/usr/bin/env python3
"""
Support Triage Agent — Main Entry Point
Usage:
  python run.py                        # interactive mode
  python run.py --csv input.csv        # batch mode (reads CSV, writes output.csv)
  python run.py --csv input.csv --out results.csv
"""

import os
import sys
import argparse
from pathlib import Path

# Ensure code/ is on the path
sys.path.insert(0, str(Path(__file__).parent))

from agent.triage_agent import TriageAgent


BANNER = r"""
╔══════════════════════════════════════════════════════════════╗
║        Multi-Domain Support Triage Agent  v1.0              ║
║   Domains: HackerRank │ Claude (Anthropic) │ Visa            ║
╚══════════════════════════════════════════════════════════════╝
"""


def interactive_mode(agent: TriageAgent):
    """Simple REPL for manual ticket testing."""
    print(BANNER)
    print("Interactive mode — type a support ticket and press Enter twice.\n")
    print("Commands: 'quit' to exit, 'domain:hackerrank/claude/visa' to set domain.\n")

    domain_hint = ""

    while True:
        try:
            print("─" * 60)
            subject = input("Subject: ").strip()
            if subject.lower() in ("quit", "exit", "q"):
                print("Goodbye!")
                break

            if subject.startswith("domain:"):
                domain_hint = subject.split(":", 1)[1].strip()
                print(f"  Domain set to: {domain_hint}")
                continue

            body = input("Body    : ").strip()

            ticket = {
                "ticket_id": f"MANUAL_{id(subject) % 9999:04d}",
                "subject": subject,
                "body": body,
                "domain": domain_hint,
            }

            print("\nProcessing …\n")
            result = agent.process_ticket(ticket)

            print(f"  Domain       : {result['domain']}")
            print(f"  Product Area : {result['product_area']}")
            print(f"  Request Type : {result['request_type']}")
            print(f"  Sensitivity  : {result['sensitivity']}")
            print(f"  Action       : {result['action']}")
            if result["escalation_reason"]:
                print(f"  Esc. Reason  : {result['escalation_reason']}")
            print(f"\n{'─'*60}\nRESPONSE:\n{result['response']}\n")

        except KeyboardInterrupt:
            print("\n\nInterrupted. Goodbye!")
            break


def main():
    parser = argparse.ArgumentParser(description="Support Triage Agent")
    parser.add_argument(
        "--csv",
        metavar="INPUT_CSV",
        help="Path to support_issues.csv (batch mode)",
    )
    parser.add_argument(
        "--out",
        metavar="OUTPUT_CSV",
        default="output.csv",
        help="Output CSV path (default: output.csv)",
    )
    args = parser.parse_args()

    # Check API key
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("\n❌  ERROR: ANTHROPIC_API_KEY environment variable is not set.")
        print("   Set it with: export ANTHROPIC_API_KEY=your_key_here\n")
        sys.exit(1)

    agent = TriageAgent()

    if args.csv:
        # Batch mode
        agent.process_csv(args.csv, args.out)
    else:
        # Interactive mode
        interactive_mode(agent)


if __name__ == "__main__":
    main()
