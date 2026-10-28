"""
Web Task Manager for POSH Research Tool.
Manages asynchronous research jobs, real-time logging, batching, and Excel exports.
Zero AI, 100% deterministic backend.
"""

import threading
import time
import os
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from .config import BATCH_SIZE, NOT_AVAILABLE
from .search_engine import SearchEngine
from .scraper import WebScraper
from .company_processor import CompanyProcessor
from .excel_exporter import ExcelExporter

logger = logging.getLogger(__name__)


class WebTaskManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(WebTaskManager, cls).__new__(cls)
                cls._instance._init_manager()
            return cls._instance

    def _init_manager(self):
        # Use RLock (re-entrant lock) to prevent deadlocks across nested calls
        self.state_lock = threading.RLock()
        self.thread: Optional[threading.Thread] = None
        self.stop_requested = False
        self.continue_requested = False

        self.status = "idle"  # idle, running, paused, completed, stopped, error
        self.city = ""
        self.area = "Whole city"
        self.target_count = 25
        self.industry = "Any"
        self.batch_size = BATCH_SIZE
        self.auto_continue = True

        self.logs: List[Dict[str, str]] = []
        self.companies: List[Dict[str, Any]] = []
        self.excluded: List[Dict[str, str]] = []
        self.sources: List[str] = []
        self.batch_no = 1
        self.current_batch: List[Dict[str, Any]] = []
        self.excel_filename: Optional[str] = None
        self.excel_path: Optional[str] = None
        self.error_message: Optional[str] = None

    def log(self, message: str, level: str = "info"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        with self.state_lock:
            self.logs.append({
                "time": timestamp,
                "msg": message,
                "level": level
            })
            # Keep max 500 logs in memory
            if len(self.logs) > 500:
                self.logs.pop(0)

    def start_task(
        self,
        city: str,
        area: str = "Whole city",
        count: int = 25,
        industry: str = "Any",
        batch_size: int = BATCH_SIZE,
        auto_continue: bool = True
    ) -> bool:
        with self.state_lock:
            if self.status == "running" or self.status == "paused":
                return False

            self.status = "running"
            self.stop_requested = False
            self.continue_requested = False
            self.city = city.strip()
            self.area = area.strip() if area.strip() else "Whole city"
            self.target_count = max(1, int(count))
            self.industry = industry.strip() if industry.strip() else "Any"
            self.batch_size = max(1, int(batch_size))
            self.auto_continue = bool(auto_continue)

            self.logs = []
            self.companies = []
            self.excluded = []
            self.sources = []
            self.current_batch = []
            self.batch_no = 1
            self.error_message = None

            exporter = ExcelExporter(city=self.city)
            self.excel_filename = exporter.filename
            self.excel_path = os.path.abspath(exporter.filename)

        self.log(f"Starting research: City='{self.city}', Area='{self.area}', Target={self.target_count}, Industry='{self.industry}'")
        self.thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.thread.start()
        return True

    def continue_batch(self) -> bool:
        with self.state_lock:
            if self.status == "paused":
                self.continue_requested = True
                self.status = "running"
                batch = self.batch_no
            else:
                return False
        self.log(f"Resuming research for Batch {batch}...", level="info")
        return True

    def stop_task(self) -> bool:
        with self.state_lock:
            if self.status in ["running", "paused"]:
                self.stop_requested = True
                self.status = "stopped"
            else:
                return False
        self.log("Task cancellation requested by user.", level="warning")
        return True

    def get_status(self) -> Dict[str, Any]:
        with self.state_lock:
            # Gaps calculations
            total_delivered = len(self.companies)
            ic_emails_count = sum(1 for c in self.companies if c.get("IC email ID") != NOT_AVAILABLE)
            ic_docs_count = sum(1 for c in self.companies if c.get("IC document / report link (POSH policy PDF, IC notice, annual report or BRSR where IC details appear)") != NOT_AVAILABLE)
            ic_members_count = sum(1 for c in self.companies if c.get("IC presiding officer / member name(s) (as published)") != NOT_AVAILABLE)
            hr_emails_count = sum(1 for c in self.companies if c.get("HR email ID") != NOT_AVAILABLE)
            company_phones_count = sum(1 for c in self.companies if c.get("Company public phone number") != NOT_AVAILABLE)
            company_emails_count = sum(1 for c in self.companies if c.get("Company public email ID") != NOT_AVAILABLE)

            return {
                "status": self.status,
                "city": self.city,
                "area": self.area,
                "target_count": self.target_count,
                "industry": self.industry,
                "delivered_count": total_delivered,
                "batch_no": self.batch_no,
                "excel_filename": self.excel_filename,
                "excel_path": self.excel_path,
                "excel_exists": os.path.exists(self.excel_path) if self.excel_path else False,
                "error_message": self.error_message,
                "logs": self.logs[-100:],  # Return latest 100 logs
                "companies": self.companies,
                "excluded_count": len(self.excluded),
                "excluded": self.excluded,
                "sources_count": len(self.sources),
                "gaps": {
                    "ic_email": {"found": ic_emails_count, "total": total_delivered},
                    "ic_doc": {"found": ic_docs_count, "total": total_delivered},
                    "ic_member": {"found": ic_members_count, "total": total_delivered},
                    "hr_email": {"found": hr_emails_count, "total": total_delivered},
                    "company_phone": {"found": company_phones_count, "total": total_delivered},
                    "company_email": {"found": company_emails_count, "total": total_delivered}
                }
            }

    def _worker_loop(self):
        exporter = ExcelExporter(city=self.city)
        try:
            search_engine = SearchEngine(
                on_engine_fallback=lambda msg: self.log(msg, level="info")
            )
            scraper = WebScraper()
            processor = CompanyProcessor(search_engine=search_engine, scraper=scraper)

            # Immediately initialize the Excel workbook on disk so it is downloadable from second 0
            init_path = exporter.export_batch(
                new_companies=[],
                area=self.area,
                industry=self.industry,
                target_rows=self.target_count,
                batch_no=1,
                excluded_companies=[],
                all_source_urls=[]
            )
            with self.state_lock:
                self.excel_path = init_path
                self.excel_filename = exporter.filename

            self.log(f"Initiating continuous public discovery for {self.city} (Area: {self.area}, Industry: {self.industry})...")
            self.log("Multi-engine cascading public search active: DuckDuckGo -> Bing -> Yahoo -> Google -> SearXNG (100% zero-paid compliance).")
            self.log(f"Initialized output file: {exporter.filename} (ready for instant download)")

            candidate_gen = search_engine.iter_candidates(
                city=self.city,
                area=self.area,
                industry=self.industry
            )

            seen_domains = set()
            candidate_idx = 0

            for candidate in candidate_gen:
                if self.stop_requested:
                    self.log("Pipeline stopped by user.", level="warning")
                    break

                domain = candidate["domain"]
                if domain in seen_domains:
                    continue
                seen_domains.add(domain)

                with self.state_lock:
                    current_count = len(self.companies)

                if current_count >= self.target_count:
                    self.log(f"Target count of {self.target_count} companies reached!")
                    break

                candidate_idx += 1
                self.log(f"[{current_count + 1}/{self.target_count}] Checking: {candidate['title']} ({domain})...")

                try:
                    record, exclusion, sources = processor.process_company(
                        candidate=candidate,
                        target_city=self.city,
                        target_area=self.area,
                        batch_no=self.batch_no
                    )
                except Exception as comp_err:
                    logger.warning(f"Error processing candidate {domain}: {comp_err}")
                    exclusion = {"name": candidate.get("title", domain), "reason": f"Processing error: {comp_err}"}
                    record = None
                    sources = [candidate.get("url", "")]

                with self.state_lock:
                    self.sources.extend(sources)
                    self.sources = list(set(self.sources))

                if exclusion:
                    self.log(f"[-] Excluded {candidate['title']}: {exclusion['reason']}", level="info")
                    with self.state_lock:
                        self.excluded.append(exclusion)
                    # Update Sheet 2 Notes & Sources on disk
                    try:
                        exporter.export_batch(
                            new_companies=[],
                            area=self.area,
                            industry=self.industry,
                            target_rows=self.target_count,
                            batch_no=self.batch_no,
                            excluded_companies=self.excluded,
                            all_source_urls=self.sources
                        )
                    except Exception:
                        pass
                    continue

                if record:
                    with self.state_lock:
                        self.companies.append(record)
                        record["#"] = len(self.companies)
                        current_total = len(self.companies)

                    # Incrementally write to Excel so disk is ALWAYS 100% up to date even if a crash occurs
                    saved_path = exporter.export_batch(
                        new_companies=[record],
                        area=self.area,
                        industry=self.industry,
                        target_rows=self.target_count,
                        batch_no=self.batch_no,
                        excluded_companies=self.excluded,
                        all_source_urls=self.sources
                    )
                    with self.state_lock:
                        self.excel_path = saved_path

                    ic_found = record["IC email ID"] != NOT_AVAILABLE or record["IC document / report link (POSH policy PDF, IC notice, annual report or BRSR where IC details appear)"] != NOT_AVAILABLE
                    status_text = "POSH/IC details published" if ic_found else "No online IC published (marked 'Not available')"
                    self.log(f"[+] Verified company #{current_total}: {record['Company name']} ({record['Legal form (Pvt Ltd / LLP / Listed / Not confirmed)']}) - {status_text}", level="success")

                    # Check batch boundaries
                    if current_total % self.batch_size == 0 or current_total >= self.target_count:
                        self.log(f"Batch {self.batch_no} checkpoint: {current_total} of {self.target_count} rows saved to {exporter.filename}.", level="success")

                        with self.state_lock:
                            self.batch_no += 1

                        if current_total >= self.target_count:
                            self.log(f"All {self.target_count} requested companies successfully verified and compiled into {exporter.filename}!", level="success")
                            break

                        if not self.auto_continue:
                            with self.state_lock:
                                self.status = "paused"
                            self.log(f"Batch {self.batch_no - 1} complete. Paused. Click 'Continue Next Batch' or enable Auto-Continue to proceed.", level="warning")

                            while self.status == "paused" and not self.stop_requested:
                                time.sleep(0.5)

            with self.state_lock:
                if not self.stop_requested:
                    self.status = "completed"
                else:
                    self.status = "stopped"
            
            if not self.stop_requested:
                self.log(f"Research workflow complete! Verified {len(self.companies)} qualifying companies. File ready for download.", level="success")
            else:
                self.log(f"POSH research stopped. {len(self.companies)} verified companies safely preserved in {exporter.filename}.", level="warning")

        except Exception as e:
            logger.exception("Error in research task")
            with self.state_lock:
                self.status = "error"
                self.error_message = str(e)
            self.log(f"Unexpected error: {e}. All {len(self.companies)} verified companies have been safely saved to Excel and remain downloadable.", level="error")

        finally:
            # Ensure workbook on disk is finalized with complete audit tables even if failed or aborted
            try:
                final_path = exporter.export_batch(
                    new_companies=[],
                    area=self.area,
                    industry=self.industry,
                    target_rows=self.target_count,
                    batch_no=self.batch_no,
                    excluded_companies=self.excluded,
                    all_source_urls=self.sources
                )
                with self.state_lock:
                    self.excel_path = os.path.abspath(final_path)
                    self.excel_filename = os.path.basename(final_path)
            except Exception as final_err:
                logger.error(f"Error finalizing Excel file: {final_err}")
