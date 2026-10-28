"""
Main CLI Controller for POSH & Company Research Tool.
Implements Step 1 (interactive Q1-Q4 or CLI flags) and Batching (25 per batch).
Zero AI, 100% deterministic, open-source Python tool.
"""

import sys
import os
import argparse
from typing import List, Dict, Any, Set

from .config import BATCH_SIZE, NOT_AVAILABLE
from .search_engine import SearchEngine
from .scraper import WebScraper
from .company_processor import CompanyProcessor
from .excel_exporter import ExcelExporter


def ask_interactive_inputs() -> Dict[str, Any]:
    """
    Step 1: Ask 4 questions one by one.
    """
    print("\n" + "="*60)
    print("POSH & COMPANY IC RESEARCH TOOL (Zero AI)")
    print("="*60 + "\n")

    # Q1
    q1 = input("Q1. Which city should I research?\n> ").strip()
    while not q1:
        q1 = input("Please specify a city name:\n> ").strip()

    # Q2
    q2 = input("\nQ2. Any specific area/locality within that city? (Reply 'Whole city' if none.)\n> ").strip()
    if not q2:
        q2 = "Whole city"

    # Q3
    q3_input = input("\nQ3. How many companies do you want in total?\n> ").strip()
    try:
        q3 = int(q3_input)
    except ValueError:
        q3 = 25

    # Q4
    q4 = input("\nQ4. Any industry filter? (Reply 'Any' if none.)\n> ").strip()
    if not q4:
        q4 = "Any"

    # Q5
    q5 = input("\nQ5. Should a valid phone number be mandatory before considering a company verified? (Reply 'Mandatory' or 'Optional', default: 'Optional')\n> ").strip()
    if not q5 or q5.lower() not in ["mandatory", "m", "required", "yes"]:
        q5 = "Optional"
    else:
        q5 = "Mandatory"

    # Repeat all five answers back in one line, then start immediately.
    print(f"\nCity: {q1} | Area: {q2} | Total requested: {q3} | Industry: {q4} | Phone Requirement: {q5}")
    print("Starting research immediately...\n")

    return {
        "city": q1,
        "area": q2,
        "count": q3,
        "industry": q4,
        "require_phone": q5.lower()
    }


def run_pipeline(
    city: str,
    area: str = "Whole city",
    count: int = 25,
    industry: str = "Any",
    require_phone: str = "optional",
    batch_size: int = BATCH_SIZE,
    auto_continue: bool = False
):
    search_engine = SearchEngine()
    scraper = WebScraper()
    processor = CompanyProcessor(search_engine=search_engine, scraper=scraper)
    exporter = ExcelExporter(city=city)

    print(f"[*] Initiating continuous public candidate discovery for {city} (Area: {area}, Industry: {industry}, Phone Requirement: {require_phone.title()})...")
    candidate_gen = search_engine.iter_candidates(city=city, area=area, industry=industry)

    delivered_records: List[Dict[str, Any]] = []
    excluded_records: List[Dict[str, str]] = []
    all_source_urls: List[str] = []
    seen_domains: Set[str] = set()

    batch_no = 1
    current_batch: List[Dict[str, Any]] = []
    candidate_idx = 0

    for candidate in candidate_gen:
        domain = candidate["domain"]
        if domain in seen_domains:
            continue
        seen_domains.add(domain)

        if len(delivered_records) >= count:
            break

        candidate_idx += 1
        print(f"[{len(delivered_records) + 1}/{count}] Inspecting: {candidate['title']} ({domain})...")
        record, exclusion, sources = processor.process_company(
            candidate=candidate,
            target_city=city,
            target_area=area,
            batch_no=batch_no,
            require_phone=require_phone
        )

        all_source_urls.extend(sources)

        if exclusion:
            print(f"   [-] Excluded: {exclusion['reason']}")
            excluded_records.append(exclusion)
            continue

        if record:
            current_batch.append(record)
            delivered_records.append(record)
            record["#"] = len(delivered_records)
            ic_status = "Found" if record["IC email ID"] != NOT_AVAILABLE or record["IC document / report link (POSH policy PDF, IC notice, annual report or BRSR where IC details appear)"] != NOT_AVAILABLE else "Not published online"
            print(f"   [+] Verified! IC Details: {ic_status} | Legal: {record['Legal form (Pvt Ltd / LLP / Listed / Not confirmed)']}")

        # Check if batch limit or total target reached
        if len(current_batch) >= batch_size or len(delivered_records) >= count:
            if current_batch:
                file_path = exporter.export_batch(
                    new_companies=current_batch,
                    area=area,
                    industry=industry,
                    target_rows=count,
                    batch_no=batch_no,
                    excluded_companies=excluded_records,
                    all_source_urls=all_source_urls,
                    require_phone=require_phone
                )

                # Batch summary
                ic_emails_found = sum(1 for r in current_batch if r["IC email ID"] != NOT_AVAILABLE)
                ic_docs_found = sum(1 for r in current_batch if r["IC document / report link (POSH policy PDF, IC notice, annual report or BRSR where IC details appear)"] != NOT_AVAILABLE)
                hr_emails_found = sum(1 for r in current_batch if r["HR email ID"] != NOT_AVAILABLE)
                phones_found = sum(1 for r in current_batch if r["Company public phone number"] != NOT_AVAILABLE)

                print("\n" + "-"*60)
                print(f"BATCH {batch_no} COMPLETE: {len(delivered_records)} of {count} rows completed.")
                print(f"Gaps in this batch: IC email found for {ic_emails_found} of {len(current_batch)}, "
                      f"IC document found for {ic_docs_found} of {len(current_batch)}, "
                      f"HR email found for {hr_emails_found} of {len(current_batch)}, "
                      f"Company phone found for {phones_found} of {len(current_batch)}.")
                print(f"Workbook updated at: {file_path}")
                print("-"*60 + "\n")

                current_batch = []
                batch_no += 1

                if len(delivered_records) >= count:
                    print(f"[✓] Goal achieved: {len(delivered_records)} companies verified and exported.")
                    break

                if not auto_continue:
                    resp = input("Type 'continue' to proceed to next batch, or 'stop' to finish:\n> ").strip().lower()
                    if resp == "stop":
                        print("Stopping as requested.")
                        break

    # Flush any remaining unwritten companies if loop ended
    if current_batch:
        file_path = exporter.export_batch(
            new_companies=current_batch,
            area=area,
            industry=industry,
            target_rows=count,
            batch_no=batch_no,
            excluded_companies=excluded_records,
            all_source_urls=all_source_urls
        )
        print(f"[✓] Final batch of {len(current_batch)} records saved to {file_path}")

    if len(delivered_records) < count:
        print(f"\n[i] Finished public search. Found {len(delivered_records)} qualifying companies out of {count} requested.")
        print("Note: In accordance with strict rules, weak or unverified entries were not added to pad the list.")


def main():
    parser = argparse.ArgumentParser(description="POSH & Company IC Research Tool (Zero AI)")
    parser.add_argument("--city", type=str, help="Target city")
    parser.add_argument("--area", type=str, default="Whole city", help="Area or locality within city")
    parser.add_argument("--count", type=int, default=25, help="Number of companies to research")
    parser.add_argument("--industry", type=str, default="Any", help="Industry filter")
    parser.add_argument("--require-phone", type=str, default="optional", choices=["optional", "mandatory"], help="Valid phone requirement (default: optional)")
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE, help="Batch size (default: 25)")
    parser.add_argument("--auto-continue", action="store_true", help="Automatically proceed without pausing between batches")

    args = parser.parse_args()

    if args.city:
        city = args.city
        area = args.area
        count = args.count
        industry = args.industry
        require_phone = args.require_phone
        print(f"City: {city} | Area: {area} | Total requested: {count} | Industry: {industry} | Phone Requirement: {require_phone.title()}")
        print("Starting research immediately...\n")
    else:
        inputs = ask_interactive_inputs()
        city = inputs["city"]
        area = inputs["area"]
        count = inputs["count"]
        industry = inputs["industry"]
        require_phone = inputs.get("require_phone", "optional")

    run_pipeline(
        city=city,
        area=area,
        count=count,
        industry=industry,
        require_phone=require_phone,
        batch_size=args.batch_size,
        auto_continue=args.auto_continue
    )


if __name__ == "__main__":
    main()

