import base64
import time
from typing import Any
from urllib.parse import quote

import requests

from .client import ModelflareClient, ModelflareError
from .models import ClassifiedModel


def generate_image(
    client: ModelflareClient,
    model: ClassifiedModel,
    prompt: str,
    parameters: dict[str, Any] | None = None,
    edit: bool = False,
) -> list[tuple[bytes, str]]:
    """Generate or edit an image; returns (bytes, mime type) per image.

    Gemini image models use /v1/models/{model}:generateContent; every other
    image model uses the Images API. Model-specific fields go in `parameters`
    unchanged.
    """
    if model.kind != "image" or not model.image_route:
        raise ValueError(f"{model.id} is not an image model")
    if edit and model.image_route != "images":
        raise ValueError(f"{model.id} does not use the OpenAI-compatible image edits route")
    parameters = dict(parameters or {})
    images: list[tuple[bytes, str]] = []
    if model.image_route == "gemini-generate-content":
        contents = parameters.pop("contents", None) or [{"role": "user", "parts": [{"text": prompt}]}]
        body = client.request("POST", f"models/{quote(model.id, safe='')}:generateContent", json={"contents": contents, **parameters}).json()
        for candidate in body.get("candidates") or []:
            for part in (candidate.get("content") or {}).get("parts") or []:
                inline = part.get("inlineData") or part.get("inline_data") or {}
                if inline.get("data"):
                    mime = inline.get("mimeType") or inline.get("mime_type") or "image/png"
                    images.append((base64.b64decode(inline["data"]), mime))
    else:
        path = "images/edits" if edit else "images/generations"
        body = client.request("POST", path, json={**parameters, "model": model.id, "prompt": prompt}).json()
        for item in body.get("data") or []:
            if item.get("b64_json"):
                images.append((base64.b64decode(item["b64_json"]), "image/png"))
            elif item.get("url"):
                # Result URLs expire, so fetch the bytes right away.
                download = requests.get(item["url"], timeout=120)
                download.raise_for_status()
                images.append((download.content, download.headers.get("content-type", "image/png").split(";")[0]))
    if not images:
        raise ModelflareError("upstream", f"{model.id} returned no image")
    return images


def create_video(client: ModelflareClient, model_id: str, request: dict[str, Any]) -> dict[str, Any]:
    body = client.request("POST", "videos", json={**request, "model": model_id}).json()
    task_id = body.get("id") or body.get("task_id")
    if not task_id:
        raise ModelflareError("upstream", "The video task response has no id")
    return {"id": task_id, "status": body.get("status", "queued")}


def get_video(client: ModelflareClient, task_id: str) -> dict[str, Any]:
    body = client.request("GET", f"videos/{quote(task_id, safe='')}", timeout=30).json()
    body["id"] = body.get("id") or body.get("task_id") or task_id
    return body


def wait_for_video(client: ModelflareClient, task_id: str, timeout: float, interval: float = 5) -> dict[str, Any]:
    """Poll until completed, failed or `timeout` seconds pass; returns the last status."""
    deadline = time.monotonic() + timeout
    while True:
        task = get_video(client, task_id)
        if task.get("status") in ("completed", "failed") or time.monotonic() >= deadline:
            return task
        time.sleep(interval)


def download_video(client: ModelflareClient, task_id: str) -> bytes:
    return b"".join(client.iter_content(f"videos/{quote(task_id, safe='')}/content"))
