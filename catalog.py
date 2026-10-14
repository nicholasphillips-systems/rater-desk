"""What each platform looks like from the outside, for auto mode. No UI imports here.

Two things are recognised:
  - window words: text that shows up in a browser tab title while you work there
  - email domains: where that platform's own mail comes from
plus payer names, the name a PayPal/Payoneer payment email gives as the sender.

A platform's own match_words / email_domains columns override these when set.
Keep words specific: "Babel" alone would fire on the Babel JS compiler, so it is
"Babel Audio".
"""

import re

# name, window words, email domains, payer names, login_url
CATALOG = [
    ("Outlier", ["Outlier", "outlier.ai"], ["outlier.ai"],
     ["Outlier", "Smart Ecosystem", "Scale AI", "Remotasks"], "https://app.outlier.ai/login"),
    ("TELUS Digital", ["TELUS", "AI Community", "RaterHub", "Rater Hub"],
     ["telusinternational.ai", "telusinternational.com", "telusdigital.com", "telus.com"],
     ["TELUS"], "https://www.telusinternational.ai/snake/"),
    ("Mercor", ["Mercor"], ["mercor.com"], ["Mercor"], "https://work.mercor.com/"),
    ("Babel Audio", ["Babel Audio", "babel.audio"], ["babel.audio"],
     ["Babel Audio", "Babel Inc"], "https://dashboard.babel.audio/sign-in"),
    ("Alignerr", ["Alignerr", "Labelbox"], ["alignerr.com", "labelbox.com"],
     ["Alignerr", "Labelbox"], "https://alignerr.com/"),
    ("Prolific", ["Prolific"], ["prolific.com", "prolific.co"], ["Prolific"],
     "https://app.prolific.com/register"),
    ("Clickworker", ["clickworker", "UHRS"], ["clickworker.com"], ["clickworker"],
     "https://www.clickworker.com/"),
    ("OneForma", ["OneForma"], ["oneforma.com"], ["OneForma", "Pactera"],
     "https://my.oneforma.com/center/signup"),
    ("Mindrift", ["Mindrift", "Toloka"], ["mindrift.ai", "toloka.ai"], ["Mindrift", "Toloka"],
     "https://mindrift.toloka.ai/"),
    ("CrowdGen", ["CrowdGen", "Appen"], ["crowdgen.com", "appen.com"], ["CrowdGen", "Appen"],
     "https://crowdgen.com/"),
    ("LXT", ["LXT"], ["lxt.ai"], ["LXT"], "https://www.lxt.ai/jobs/"),
    ("Sigma", ["Sigma AI", "sigma.ai"], ["sigma.ai"], ["Sigma AI"], "https://sigma.ai/"),
    ("Welo Data", ["Welo Data", "Welocalize"], ["welodata.ai", "welocalize.com"],
     ["Welo", "Welocalize"], "https://welodata.ai/"),
    ("RWS TrainAI", ["TrainAI"], ["rws.com"], ["RWS"], "https://www.rws.com/artificial-intelligence/train-ai-data-services/"),
]

# Where payout emails come from. These name the payer in the body, not the sender.
PAYMENT_DOMAINS = ["paypal.com", "payoneer.com", "airtm.com", "venmo.com"]

# Window classes that count as a browser. Platform work only happens in one, and
# limiting matches to browsers keeps "outlier detection" in an editor from
# starting the Outlier timer.
BROWSER_CLASSES = ["chrom", "firefox", "librewolf", "zen", "brave", "edge", "vivaldi",
                   "opera", "floorp", "waterfox", "falkon", "epiphany", "qutebrowser"]


def catalog_entry(name):
    for entry in CATALOG:
        if entry[0].lower() == (name or "").lower():
            return entry
    return None


def split_list(text):
    """'a, b\nc' -> ['a', 'b', 'c']"""
    return [w.strip() for w in re.split(r"[,\n]", text or "") if w.strip()]


def window_words(platform):
    """The words that identify this platform in a window title."""
    if platform['match_words'] is not None:
        return split_list(platform['match_words'])
    entry = catalog_entry(platform['name'])
    return list(entry[1]) if entry else [platform['name']]


def email_domains(platform):
    if platform['email_domains'] is not None:
        return [d.lower() for d in split_list(platform['email_domains'])]
    entry = catalog_entry(platform['name'])
    return list(entry[2]) if entry else []


def payer_names(name):
    entry = catalog_entry(name)
    return list(entry[3]) if entry else [name]


def _word_re(word):
    return re.compile(r"(?<![\w.])" + re.escape(word) + r"(?![\w])", re.IGNORECASE)


def is_browser(app_class):
    cls = (app_class or "").lower()
    return any(b in cls for b in BROWSER_CLASSES)


def match_window(title, app_class, platforms):
    """Return the platform row whose words appear in this browser window's title."""
    if not title or not is_browser(app_class):
        return None
    for plat in platforms:
        if plat['status'] == 'dead':
            continue
        for word in window_words(plat):
            if _word_re(word).search(title):
                return plat
    return None


def domain_of(address):
    """'Outlier <no-reply@outlier.ai>' -> 'outlier.ai'"""
    m = re.search(r"@([\w.-]+)", address or "")
    return m.group(1).lower().rstrip(".") if m else ""


def _domain_matches(domain, wanted):
    return domain == wanted or domain.endswith("." + wanted)


def platform_for_sender(address, platforms):
    """Platform row (or a catalog name for one not in the list) that sent this email.

    Returns (platform_row_or_None, catalog_name_or_None).
    """
    domain = domain_of(address)
    if not domain:
        return None, None
    for plat in platforms:
        if any(_domain_matches(domain, d) for d in email_domains(plat)):
            return plat, plat['name']
    for entry in CATALOG:
        if any(_domain_matches(domain, d) for d in entry[2]):
            return None, entry[0]
    return None, None


def is_payment_sender(address):
    domain = domain_of(address)
    return any(_domain_matches(domain, d) for d in PAYMENT_DOMAINS)


def platform_for_payer(text, platforms):
    """Find which platform a payment email names as the payer."""
    names = [(p, payer_names(p['name']) + [p['name']]) for p in platforms]
    for plat, words in names:
        for word in words:
            if _word_re(word).search(text or ""):
                return plat, plat['name']
    for entry in CATALOG:
        for word in entry[3]:
            if _word_re(word).search(text or ""):
                return None, entry[0]
    return None, None


def all_watched_domains(platforms):
    """Every sender domain worth fetching mail from."""
    domains = set(PAYMENT_DOMAINS)
    for entry in CATALOG:
        domains.update(entry[2])
    for plat in platforms:
        domains.update(email_domains(plat))
    return sorted(domains)
