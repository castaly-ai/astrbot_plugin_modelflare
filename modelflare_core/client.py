import re
from collections.abc import Iterator
from typing import Any

import requests

from .config import CATALOG_URL, resolve_base_url

ATTRIBUTION_HEADER = "X-Modelflare-Skill"
# Same shape the gateway accepts in common/skill_attribution.go; anything else
# is dropped there without an error.
_ATTRIBUTION = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}/[0-9]{1,4}(\.[0-9]{1,4}){0,2}$")
# common.MessageWithRequestId appends " (request id: <id>)".
_REQUEST_ID_SUFFIX = re.compile(r"\s*\(request id: ([^)]+)\)\s*$")

_KIND_BY_CODE = {
    "insufficient_user_quota": "insufficient_quota",
    "model_not_found": "model_not_found",
    "unsupported_endpoint": "unsupported_endpoint",
    "rate_limit_exceeded": "rate_limited",
}


def attribution_value(plugin: str, version: str) -> str:
    value = f"{plugin}/{version}"
    if len(value) > 80 or not _ATTRIBUTION.match(value):
        raise ValueError(f"{value!r} is not a valid {ATTRIBUTION_HEADER} value")
    return value


class ModelflareError(Exception):
    """A gateway failure. `kind` is decided by the error code, never the message."""

    def __init__(
        self,
        kind: str,
        message: str,
        status: int | None = None,
        code: str | None = None,
        request_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.kind = kind
        self.message = message
        self.status = status
        self.code = code
        self.request_id = request_id


def error_from_response(response: requests.Response) -> ModelflareError:
    message = response.reason or f"HTTP {response.status_code}"
    code = None
    try:
        body = response.json()
    except ValueError:
        body = None
    if isinstance(body, dict):
        error = body.get("error")
        if isinstance(error, dict):
            message = error.get("message") or message
            code = error.get("code") or None
        elif isinstance(body.get("message"), str):
            message = body["message"]
    request_id = response.headers.get("x-request-id")
    match = _REQUEST_ID_SUFFIX.search(message)
    if match:
        request_id = match.group(1)
        message = message[: match.start()]
    kind = _KIND_BY_CODE.get(code or "")
    if kind is None:
        kind = "unauthorized" if response.status_code == 401 else "rate_limited" if response.status_code == 429 else "upstream"
    return ModelflareError(kind, message, response.status_code, code, request_id)


class ModelflareClient:
    """Bearer-key client that tags every request with the plugin's attribution."""

    def __init__(self, api_key: str, plugin: str, version: str, base_url: str | None = None, timeout: float = 120) -> None:
        api_key = (api_key or "").strip()
        if not api_key:
            raise ModelflareError("unauthorized", "A Modelflare API key is required")
        self._api_key = api_key
        self.base_url = resolve_base_url(base_url)
        self.attribution = attribution_value(plugin, version)
        self.timeout = timeout

    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._api_key}", ATTRIBUTION_HEADER: self.attribution}

    def attribution_headers(self) -> dict[str, str]:
        return {ATTRIBUTION_HEADER: self.attribution}

    def request(self, method: str, path: str, *, json: Any = None, stream: bool = False, timeout: float | None = None) -> requests.Response:
        url = f"{self.base_url}/{path.lstrip('/')}"
        try:
            response = requests.request(
                method, url, headers=self.headers(), json=json, stream=stream, timeout=timeout or self.timeout
            )
        except requests.Timeout as ex:
            raise ModelflareError("timeout", "The request to Modelflare timed out") from ex
        except requests.RequestException as ex:
            raise ModelflareError("network", "Could not reach Modelflare") from ex
        if response.status_code >= 400:
            raise error_from_response(response)
        return response

    def list_models(self) -> list[dict[str, Any]]:
        data = self.request("GET", "models", timeout=30).json().get("data")
        return data if isinstance(data, list) else []

    def iter_content(self, path: str, chunk_size: int = 1 << 20) -> Iterator[bytes]:
        response = self.request("GET", path, stream=True, timeout=600)
        try:
            yield from response.iter_content(chunk_size)
        finally:
            response.close()


def fetch_catalog(timeout: float = 30) -> list[dict[str, Any]] | None:
    """Public catalog without a key; None when it cannot be read."""
    try:
        response = requests.get(CATALOG_URL, timeout=timeout)
        body = response.json() if response.ok else None
    except (requests.RequestException, ValueError):
        return None
    if not isinstance(body, dict) or body.get("success") is False or not isinstance(body.get("data"), list):
        return None
    return body["data"]
