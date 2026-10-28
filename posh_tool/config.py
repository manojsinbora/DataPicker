"""
Configuration and constants for POSH & Company Research Tool.
"""

from typing import List
import re
import warnings

# Suppress harmless OpenSSL warnings on macOS LibreSSL
warnings.filterwarnings("ignore")

# Exact 21 columns in mandatory order specified in the prompt
COLUMNS: List[str] = [
    "#",
    "Company name",
    "Legal form (Pvt Ltd / LLP / Listed / Not confirmed)",
    "Full address with PIN",
    "Company website",
    "Company public phone number",
    "Company public email ID",
    "POSH / IC web page link",
    "IC document / report link (POSH policy PDF, IC notice, annual report or BRSR where IC details appear)",
    "Where IC details were found (document name + page/section)",
    "IC presiding officer / member name(s) (as published)",
    "IC email ID",
    "IC phone / mobile number",
    "HR contact name (as published, if any)",
    "HR email ID",
    "HR phone number",
    "Employee count evidence",
    "Source URL(s)",
    "Date of source / date checked",
    "Batch no.",
    "Notes"
]

# Sensitive keywords for IC and POSH discovery
IC_KEYWORDS = [
    "posh",
    "prevention of sexual harassment",
    "internal committee",
    "internal complaints committee",
    "icc",
    "presiding officer",
    "sexual harassment",
    "anti-harassment",
    "anti sexual harassment",
    "brsr",
    "code of conduct",
    "whistleblower",
    "whistle blower",
    "grievance redressal"
]

# HR keywords
HR_KEYWORDS = [
    "careers",
    "work with us",
    "join us",
    "human resources",
    "recruitment",
    "talent acquisition",
    "people officer",
    "hr team",
    "jobs"
]

# Excluded business categories (per strict requirements)
EXCLUSION_KEYWORDS = [
    "coaching",
    "training institute",
    "training consultant",
    "posh training",
    "corporate training",
    "training provider",
    "tuition",
    "test prep",
    "classes",
    "academy for exam",
    "coworking",
    "co-working",
    "shared office",
    "virtual office",
    "staffing solutions",
    "recruitment agency",
    "manpower consultancy",
    "placement consultant",
    "placement agency"
]

# Regular expressions
# STRICT RULE: Record a contact ONLY if it appears verbatim on a public page or document.
# Never guess, construct, or pattern-match (e.g., do not assume posh@company.com or hr@company.com).
EMAIL_REGEX = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b')

# Indian Phone Numbers:
# 1) Mobile numbers: starting with 6, 7, 8, or 9; 10 digits (optionally with +91 or 0)
# 2) Landline numbers: STD code (2-4 digits starting with 0 or +91-city) followed by 6-8 digits
PHONE_REGEX = re.compile(
    r'(?:(?:\+91[\-\s]?)|(?:\b0))?[6-9]\d{4}[\-\s]?\d{5}\b|'  # 10-digit mobile
    r'(?:\+91[\-\s]?)?(?:\b0\d{2,4}[\-\s]?)?\d{6,8}\b'         # Landlines
)

# Indian 6-digit PIN code (ranges 110001 to 899999)
PIN_CODE_REGEX = re.compile(r'\b([1-9][0-9]{5})\b')

# Employee count mentions
EMPLOYEE_COUNT_REGEX = re.compile(
    r'(\b\d{1,3}(?:,\d{3})*|\b\d+)\+?\s*(?:employees|staff|team members|professionals|workforce|people)',
    re.IGNORECASE
)

# HTTP Request settings
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

HTTP_TIMEOUT = 10
REQUEST_DELAY = 1.0
BATCH_SIZE = 25
NOT_AVAILABLE = "Not available"
