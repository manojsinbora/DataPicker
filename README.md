# POSH & Company Research Tool (Zero AI)

A deterministic, open-source Python tool to build a verified list of companies in any Indian city with their publicly published POSH Internal Committee (IC) details, HR contact details, and general company contacts using **ONLY public web sources** (no AI models, no LLMs, zero paid APIs).

Delivers everything in **ONE downloadable Excel file** adhering strictly to all 21 mandatory columns and the accompanying "Notes & Sources" sheet.

---

## Key Highlights & Strict Rule Compliance

- **Zero AI / Zero Paid APIs**: Driven purely by deterministic Python algorithms, regex pattern extraction, and public web search (DuckDuckGo).
- **Public Sources Only**: Searches company domains, published POSH policy PDFs, annual reports, Board reports, Corporate Governance reports, and BRSR filings.
- **Strict Verbatim Extraction**:
  - Never guesses or pattern-matches email addresses or phone numbers.
  - Contacts are captured **only** if they appear verbatim on a public page or document; otherwise marked `"Not available"`.
- **Full PDF Inspection**:
  - Automatically downloads and parses all pages using `pdfplumber` / `pypdf`.
  - Searches annexures, schedules, appendices, and tables for Presiding Officers, members, and grievance emails.
- **Cloudflare Email De-obfuscation**:
  - Automatically decodes Cloudflare-protected emails (`data-cfemail` tags) without third-party services.
- **Enterprise CDN Compatibility**:
  - Employs browser TLS fingerprint impersonation (`primp`) to reliably access enterprise sites protected by Cloudflare/Akamai without being blocked.
- **Rigorous Company Qualification**:
  - Validates physical presence in the target city and locality.
  - Confirms evidence of 10 or more employees.
  - Automatically filters out coaching institutes, coworking spaces, and staffing/recruitment agencies.
- **Single Excel Workbook Architecture**:
  - **Sheet 1 ("Companies")**: All 21 mandatory columns, frozen bold header, auto-filters, clickable hyperlinks, no blank cells.
  - **Sheet 2 ("Notes & Sources")**: Metadata, running gaps summary, excluded companies log, and full list of source URLs.
  - Appends subsequent batches to the **same** file without creating duplicate files or losing previous records.

---

## Installation & Setup

1. **Clone or navigate to the workspace**:
   ```bash
   cd "/Users/amitabora/CODING PROJECTS/DataPicker"
   ```

2. **Verify Python packages** (already installed in your environment):
   ```bash
   python3 -m pip install openpyxl beautifulsoup4 requests ddgs primp pdfplumber pypdf
   ```

---

## How to Run

### Mode 1: Interactive Web Dashboard (Recommended)
Launch the browser UI:
```bash
python3 run_web.py
```
Open **[http://127.0.0.1:5050](http://127.0.0.1:5050)** in your browser.
- **Interactive Form**: Inputs for City, Area, Company Count, Industry filter.
- **Real-Time Live Console**: View candidate discovery, domain scraping, PDF analysis, and Cloudflare email decoding as it happens.
- **Live Gaps Summary Cards**: Real-time completion rates for IC emails, IC documents, HR contacts, and excluded entities.
- **Responsive Data Explorer Table**: Full 21-column data table with sticky headers, search filtering, and pill badges.
- **Direct Excel Download**: One-click download of the complete `POSH_IC_Contacts_<City>_<YYYY-MM-DD>.xlsx` file.

---

### Mode 2: Interactive Terminal CLI
Run from terminal in the project directory:
```bash
python3 run.py
```
Prompts the 4 questions one by one (Q1–Q4), repeats the summary line, and starts research in batches of 25.

---

### Mode 3: Headless CLI Flags
```bash
python3 run.py --city "Bangalore" --area "Whole city" --count 25 --industry "IT" --auto-continue
```

---

## Output File Format

Generated in the working directory:
```
POSH_IC_Contacts_<City>_<YYYY-MM-DD>.xlsx
```

### Sheet 1: `Companies` (21 Columns)
1. `#`
2. `Company name`
3. `Legal form (Pvt Ltd / LLP / Listed / Not confirmed)`
4. `Full address with PIN`
5. `Company website`
6. `Company public phone number`
7. `Company public email ID`
8. `POSH / IC web page link`
9. `IC document / report link (POSH policy PDF, IC notice, annual report or BRSR where IC details appear)`
10. `Where IC details were found (document name + page/section)`
11. `IC presiding officer / member name(s) (as published)`
12. `IC email ID`
13. `IC phone / mobile number`
14. `HR contact name (as published, if any)`
15. `HR email ID`
16. `HR phone number`
17. `Employee count evidence`
18. `Source URL(s)`
19. `Date of source / date checked`
20. `Batch no.`
21. `Notes`

### Sheet 2: `Notes & Sources`
- **Project Metadata**: City, area, row target, rows delivered so far, industry filter, start date.
- **Running Gaps Summary**: Completion rates for IC email, IC phone, HR email, HR phone, company phone, company email, and IC document link.
- **Companies Checked and Excluded**: Log of excluded entities with explicit one-line reasons.
- **Full List of Source URLs**: Active clickable URLs for full transparency.

