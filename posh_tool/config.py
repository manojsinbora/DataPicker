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

# Regular expressions
# STRICT RULE: Record a contact ONLY if it appears verbatim on a public page or document.
# Never guess, construct, or pattern-match (e.g., do not assume posh@company.com or hr@company.com).
EMAIL_REGEX = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b')

# Indian Phone Numbers:
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
