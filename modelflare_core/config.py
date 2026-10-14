import re
from urllib.parse import urlencode, urlsplit, urlunsplit

SITE_URL = "https://modelflare.dev"
DOCS_URL = "https://docs.modelflare.dev"
KEYS_URL = f"{SITE_URL}/keys"
BILLING_URL = f"{SITE_URL}/billing"
# The China entry only admits /v1/* on direct connections, so the public
# catalog is always read from the global host.
CATALOG_URL = f"{SITE_URL}/api/pricing"

BASE_URLS = {
    "global": f"{SITE_URL}/v1",
    "china": "https://origin.modelflare.dev/v1",
}

_UTM_SOURCE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")


def resolve_base_url(value: str | None = None) -> str:
    """Resolve `global`, `china` or a custom URL to the `/v1` base URL."""
    text = (value or "").strip()
    if not text:
        return BASE_URLS["global"]
    if text in BASE_URLS:
        return BASE_URLS[text]
    parts = urlsplit(text)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        raise ValueError(f"Invalid Modelflare base URL: {text}")
    path = parts.path.rstrip("/") or "/v1"
    return urlunsplit((parts.scheme, parts.netloc, path, "", ""))


def sign_up_url(utm_source: str) -> str:
    """Sign-up link carrying the plugin's acquisition source."""
    if not _UTM_SOURCE.match(utm_source):
        raise ValueError(f"Invalid utm_source {utm_source!r}")
    query = urlencode({"utm_source": utm_source, "utm_medium": "plugin", "utm_campaign": "integrations"})
    return f"{SITE_URL}/sign-up?{query}"
