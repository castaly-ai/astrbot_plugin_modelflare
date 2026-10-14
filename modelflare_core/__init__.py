"""Shared Modelflare client logic bundled into each Python plugin (Dify, AstrBot).

Mirrors subPackages/core-ts; the contracts are documented in
docs/platform/plugins-and-integrations.md.
"""

from .client import ModelflareClient, ModelflareError
from .config import (
    BASE_URLS,
    BILLING_URL,
    CATALOG_URL,
    DOCS_URL,
    KEYS_URL,
    SITE_URL,
    resolve_base_url,
    sign_up_url,
)
from .messages import SMART_KEY_HINT, describe_error
from .models import ClassifiedModel, classify_models, model_docs_url

__all__ = [
    "BASE_URLS",
    "BILLING_URL",
    "CATALOG_URL",
    "DOCS_URL",
    "KEYS_URL",
    "SITE_URL",
    "SMART_KEY_HINT",
    "ClassifiedModel",
    "ModelflareClient",
    "ModelflareError",
    "classify_models",
    "describe_error",
    "model_docs_url",
    "resolve_base_url",
    "sign_up_url",
]
