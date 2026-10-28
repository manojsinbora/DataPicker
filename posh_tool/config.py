"""
Configuration and constants for POSH & Company Research Tool.
"""

from typing import List, Dict
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

# Excluded business categories (Strict rule: exclude coaching/training institutes, coworking, staffing agencies)
# NOTE: Must use specific multi-word phrases to avoid false positives on words like "classes" (e.g. world-class, share classes)
EXCLUSION_PHRASES = [
    # Coaching & Tuition
    "coaching classes",
    "coaching institute",
    "coaching center",
    "coaching centre",
    "tuition classes",
    "tuition centre",
    "tuition center",
    "test preparation",
    "competitive exam coaching",
    "iit jee coaching",
    "neet coaching",
    "upsc coaching",
    "ias academy",
    "bank exam coaching",
    "gate coaching",
    "cat coaching",

    # Training institutes & consultancies
    "training institute",
    "training academy",
    "training center",
    "training centre",
    "corporate training provider",
    "posh training consultancy",
    "posh training services",
    "corporate training firm",
    "training consultancy",

    # Coworking spaces
    "coworking space",
    "co-working space",
    "shared office space",
    "shared workspace",
    "virtual office space",
    "flexible workspace provider",
    "managed office space",
    "business center space",

    # Staffing & Recruitment agencies
    "recruitment agency",
    "recruitment consultancy",
    "recruitment consultant",
    "staffing agency",
    "staffing solutions",
    "staffing firm",
    "manpower consultancy",
    "manpower services",
    "placement consultancy",
    "placement agency",
    "job consultancy",
    "headhunting firm",
    "talent staffing firm"
]

# Domain-level exclusion patterns
EXCLUDED_DOMAIN_KEYWORDS = [
    "coaching",
    "coworking",
    "co-working",
    "tuition",
    "staffing",
    "recruitment-agency",
    "jobconsultancy"
]

# Indian City Name Variations & Synonyms
CITY_ALIASES: Dict[str, List[str]] = {
    "bangalore": ["bangalore", "bengaluru", "blr"],
    "bengaluru": ["bengaluru", "bangalore", "blr"],
    "mumbai": ["mumbai", "bombay", "navi mumbai", "thane"],
    "bombay": ["bombay", "mumbai", "navi mumbai", "thane"],
    "delhi": ["delhi", "new delhi", "delhi ncr", "ncr", "noida", "gurgaon", "gurugram", "faridabad", "ghaziabad"],
    "new delhi": ["new delhi", "delhi", "delhi ncr"],
    "delhi ncr": ["delhi ncr", "delhi", "new delhi", "noida", "gurgaon", "gurugram", "faridabad", "ghaziabad"],
    "gurgaon": ["gurgaon", "gurugram"],
    "gurugram": ["gurugram", "gurgaon"],
    "noida": ["noida", "greater noida", "delhi ncr"],
    "pune": ["pune", "poona"],
    "poona": ["poona", "pune"],
    "hyderabad": ["hyderabad", "secunderabad", "cyberabad"],
    "chennai": ["chennai", "madras"],
    "madras": ["madras", "chennai"],
    "kolkata": ["kolkata", "calcutta"],
    "calcutta": ["calcutta", "kolkata"],
    "ahmedabad": ["ahmedabad", "amdavad"],
    "jaipur": ["jaipur", "pink city"],
    "kochi": ["kochi", "cochin", "ernakulam"],
    "cochin": ["cochin", "kochi", "ernakulam"],
    "chandigarh": ["chandigarh", "mohali", "panchkula"],
    "trivandrum": ["trivandrum", "thiruvananthapuram"],
    "thiruvananthapuram": ["thiruvananthapuram", "trivandrum"],
    "vadodara": ["vadodara", "baroda"],
    "baroda": ["baroda", "vadodara"],
    "indore": ["indore"]
}

# Major Indian city PIN code prefixes (first 3 digits)
CITY_PIN_PREFIXES: Dict[str, List[str]] = {
    "bangalore": ["560", "562"],
    "bengaluru": ["560", "562"],
    "mumbai": ["400", "401"],
    "delhi": ["110"],
    "new delhi": ["110"],
    "delhi ncr": ["110", "122", "201", "121"],
    "gurgaon": ["122"],
    "gurugram": ["122"],
    "noida": ["201"],
    "pune": ["411", "412"],
    "hyderabad": ["500", "501"],
    "chennai": ["600"],
    "kolkata": ["700", "711"],
    "ahmedabad": ["380", "382"],
    "jaipur": ["302"],
    "kochi": ["682"],
    "chandigarh": ["160"]
}

# Popular tech parks, clusters and localities by city (used to discover diverse companies)
CITY_LOCALITIES: Dict[str, List[str]] = {
    "bangalore": [
        "Whitefield", "Electronic City", "Koramangala", "Indiranagar", "Manyata Tech Park",
        "Outer Ring Road", "Bellandur", "HSR Layout", "Marathahalli", "Domlur", "Hebbal", "Peenya"
    ],
    "mumbai": [
        "Bandra Kurla Complex", "BKC", "Andheri East", "Powai", "Lower Parel", "Nariman Point",
        "Navi Mumbai", "Thane", "Goregaon East", "Malad Mindspace"
    ],
    "pune": [
        "Hinjewadi", "Magarpatta", "Kharadi", "Viman Nagar", "Baner", "Senapati Bapat Road",
        "Hadapsar", "Bhosari MIDC", "Chakan", "Aundh"
    ],
    "delhi ncr": [
        "Cyber City Gurgaon", "Udyog Vihar", "Golf Course Road", "Noida Sector 62", "Noida Sector 125",
        "Connaught Place", "Okhla Industrial Area", "Nehru Place"
    ],
    "hyderabad": [
        "HITEC City", "Gachibowli", "Madhapur", "Financial District", "Jubilee Hills", "Banjara Hills"
    ],
    "chennai": [
        "OMR", "Tidel Park", "Guindy", "T Nagar", "Sholinganallur", "Ambattur"
    ]
}

# Major Indian city STD codes (without trunk 0 and with trunk 0)
CITY_STD_CODES: Dict[str, List[str]] = {
    "bangalore": ["80", "080"],
    "bengaluru": ["80", "080"],
    "mumbai": ["22", "022"],
    "bombay": ["22", "022"],
    "delhi": ["11", "011"],
    "new delhi": ["11", "011"],
    "delhi ncr": ["11", "011", "120", "0120", "124", "0124", "129", "0129"],
    "gurgaon": ["124", "0124"],
    "gurugram": ["124", "0124"],
    "noida": ["120", "0120"],
    "pune": ["20", "020"],
    "hyderabad": ["40", "040"],
    "chennai": ["44", "044"],
    "kolkata": ["33", "033"],
    "ahmedabad": ["79", "079"],
    "jaipur": ["141", "0141"],
    "kochi": ["484", "0484"],
    "chandigarh": ["172", "0172"],
    "indore": ["731", "0731"],
    "coimbatore": ["422", "0422"],
    "lucknow": ["522", "0522"],
    "nagpur": ["712", "0712"],
    "vadodara": ["265", "0265"],
    "surat": ["261", "0261"],
    "visakhapatnam": ["891", "0891"],
    "patna": ["612", "0612"],
    "bhopal": ["755", "0755"]
}

# Regular expressions
# STRICT RULE: Record a contact ONLY if it appears verbatim on a public page or document.
# Never guess, construct, or pattern-match (e.g., do not assume posh@company.com or hr@company.com).
EMAIL_REGEX = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b')

# Indian Phone Numbers Regex (strictly validated per Department of Telecommunications NNP)
# Matches:
# 1. +91 or 0091 prefixed numbers (mobile, landline, toll-free)
# 2. National Toll-Free / Shared-Cost numbers (1800, 1860)
# 3. Landlines with explicit STD code (e.g. 080-..., 011 ..., (080) ..., 0124-...)
# 4. Standard 10-digit Indian mobiles (starting with 6, 7, 8, or 9, optional leading 0)
PHONE_REGEX = re.compile(
    r'(?:'
    r'(?:\+91[\-\s\.]?(?:\([0-9]+\)[\-\s\.]?)?|\b0091[\-\s\.]?)'
    r'(?:1800|1860|[1-9]\d{1,4})[\-\s\.]?\d{2,4}[\-\s\.]?\d{3,4}\b'
    r'|'
    r'\b(?:1800|1860)[\-\s\.]?\d{3,4}[\-\s\.]?\d{3,4}\b'
    r'|'
    r'(?:\b0\d{1,4}[\-\s\.]|\(\s*0\d{1,4}\s*\)[\-\s\.]?)\d{3,4}[\-\s\.]?\d{3,4}\b'
    r'|'
    r'(?:\b0)?[6-9]\d{4}[\-\s\.]?\d{5}\b'
    r')'
)

def is_valid_indian_phone(phone_str: str) -> bool:
    """
    Validates whether a phone number complies with the Department of Telecommunications
    (DoT) National Numbering Plan (NNP) of India.

    Accepts:
    1. 10-digit Indian Mobile Numbers starting with 6, 7, 8, or 9 (with optional +91, 0091, or leading 0).
    2. Indian Landlines with STD Code (total 10 digits without 0/91, subscriber starting with 2-8).
    3. Indian Toll-Free (1800) and Shared-Cost (1860) numbers (10 or 11 digits).

    Rejects:
    - 6-digit Indian PIN codes (e.g. 560001, 110001).
    - Bare 8-digit numbers without STD code (e.g. 12345678, 41123456).
    - Invalid mobile numbers starting with 0-5.
    - Repetitive dummy numbers (e.g. 9999999999, 0000000000).
    - Foreign numbers with foreign country codes (e.g. +1, +44).
    - Date ranges, years, or alphanumeric sequences.
    """
    if not phone_str or not isinstance(phone_str, str):
        return False

    raw = phone_str.strip()

    # Strip any trailing sentence punctuation
    raw = re.sub(r'[\.,;:\-\s]+$', '', raw)

    # Check for foreign country codes (e.g. +1, +44, +65, etc. where not +91)
    if raw.startswith('+') and not raw.startswith('+91'):
        return False

    # Strip optional extension for core number validation (e.g. "Ext. 102", "x123")
    core = re.sub(r'(?i)\s*(?:ext|x|extension)\.?\s*\d+', '', raw)

    # Extract only digits
    digits = re.sub(r'\D', '', core)

    # Handle country code (+91 or 0091)
    if digits.startswith('0091'):
        digits = digits[4:]
    elif digits.startswith('91') and len(digits) in (12, 13):
        # 91 + 10 digits = 12 digits (mobile or landline)
        # 91 + 11 digits = 13 digits (toll-free like 9118001234567)
        digits = digits[2:]

    # Handle trunk prefix 0
    if digits.startswith('0') and len(digits) in (11, 12):
        digits = digits[1:]

    # Check dummy / placeholder numbers (all identical digits, e.g. 9999999999, 0000000000)
    if len(set(digits)) <= 1:
        return False

    # 1. Toll-Free / Shared-Cost numbers (1800, 1860)
    if digits.startswith(('1800', '1860')):
        if len(digits) in (10, 11):
            return True
        return False

    # Standard Indian mobile and landline numbers must have NSN length of exactly 10 digits
    if len(digits) != 10:
        return False

    # 2. Indian Mobile Numbers:
    # Must start with 6, 7, 8, or 9
    if digits[0] in ('6', '7', '8', '9'):
        return True

    # 3. Indian Landlines with STD Code:
    # Landlines must have an explicit STD code indicator in the raw text:
    # (+91, leading 0, or area code in parentheses or with hyphen/space)
    has_explicit_prefix = bool(
        raw.startswith('+91') or 
        raw.startswith('0') or 
        re.search(r'\b0\d{1,4}[\-\s\.]', raw) or 
        re.search(r'\(\s*0?\d{1,4}\s*\)', raw)
    )

    if has_explicit_prefix:
        # Tier 1: 2-digit STD (11, 20, 22, 33, 40, 44, 79, 80) + 8-digit subscriber (starts 2-8)
        if digits[:2] in ('11', '20', '22', '33', '40', '44', '79', '80'):
            if digits[2] in '2345678':
                return True
        # Tier 2: 3-digit STD (e.g. 120, 124, 141, 172, 484, 522, etc.) + 7-digit subscriber (starts 2-8)
        if digits[0] in '12345678' and digits[3] in '2345678':
            return True
        # Tier 3/4: 4-digit STD + 6-digit subscriber (starts 2-8)
        if digits[0] in '12345678' and digits[4] in '2345678':
            return True

    return False

def classify_indian_phone(phone_str: str, target_city: str = "") -> str:
    """
    Classifies a valid Indian phone number into its functional category:
    - Target city office landline (preferred over toll-free as required by prompt)
    - National toll-free number
    - National shared-cost number
    - Indian mobile number
    - Landline with STD code
    """
    if not is_valid_indian_phone(phone_str):
        return "Invalid or unconfirmed phone number"

    raw = phone_str.strip()
    digits = re.sub(r'\D', '', raw)

    # Toll-free & shared-cost
    if digits.startswith(('1800', '911800', '01800')):
        return "National toll-free number"
    if digits.startswith(('1860', '911860', '01860')):
        return "National shared-cost number"

    # Check target city STD match
    if target_city:
        city_key = target_city.lower().strip()
        matched_stds = CITY_STD_CODES.get(city_key, [])
        for std in matched_stds:
            if std in raw or digits.startswith(('91' + std, '0' + std, std)):
                return f"{target_city.title()} office landline"

    # Normalize digits for mobile check
    if digits.startswith('0091'):
        digits = digits[4:]
    elif digits.startswith('91') and len(digits) == 12:
        digits = digits[2:]
    if digits.startswith('0') and len(digits) == 11:
        digits = digits[1:]

    if len(digits) == 10 and digits[0] in '6789':
        return "Indian mobile number"

    return "Landline with STD code"

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
