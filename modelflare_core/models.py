from dataclasses import dataclass, field
from typing import Any

from .config import DOCS_URL

_TEXT_ENDPOINTS = {"openai", "openai-response", "anthropic"}
_MODEL_KINDS = {"text", "image", "video", "embedding", "rerank"}


@dataclass(frozen=True)
class ClassifiedModel:
    id: str
    kind: str  # text | image | video | embedding | rerank
    endpoints: tuple[str, ...] = field(default_factory=tuple)
    # "gemini-generate-content" or "images" for image models.
    image_route: str | None = None


def _positive(points: Any) -> bool:
    return any(isinstance(p, dict) and isinstance(p.get("price"), (int, float)) and p["price"] > 0 for p in points or [])


def _declares_image(entry: dict | None, endpoints: set[str]) -> bool:
    if "image-generation" in endpoints:
        return True
    if not entry:
        return False
    if (entry.get("media_options") or {}).get("image") is not None:
        return True
    sized = any(
        isinstance(p, dict) and str(p.get("size") or "").strip() and isinstance(p.get("price"), (int, float)) and p["price"] > 0
        for p in entry.get("image_generation_prices") or []
    )
    return sized or _positive(entry.get("image_feature_prices"))


def _declares_video(entry: dict | None, endpoints: set[str]) -> bool:
    if "openai-video" in endpoints:
        return True
    if not entry:
        return False
    if (entry.get("media_options") or {}).get("video") is not None:
        return True
    by_resolution = any(str(k).strip() and isinstance(v, (int, float)) and v > 0 for k, v in (entry.get("video_resolution_price") or {}).items())
    return by_resolution or _positive(entry.get("video_feature_prices"))


def classify_models(models: list[dict], catalog: list[dict] | None) -> list[ClassifiedModel]:
    """Same rules as core-ts classifyModels: Gemini image models need the
    public catalog, and anything not conclusively classified is hidden."""
    by_name = {e.get("model_name"): e for e in catalog or [] if isinstance(e, dict)}
    result: list[ClassifiedModel] = []
    for model in models:
        model_id = model.get("id")
        if not isinstance(model_id, str):
            continue
        entry = by_name.get(model_id)
        own = [e for e in model.get("supported_endpoint_types") or [] if isinstance(e, str)]
        merged = tuple(dict.fromkeys([*own, *[e for e in (entry or {}).get("supported_endpoint_types") or [] if isinstance(e, str)]]))
        endpoints = set(merged)
        declared_kind = model.get("kind")
        if declared_kind == "image":
            route = model.get("image_route") or ("gemini-generate-content" if "gemini" in endpoints else "images" if "image-generation" in endpoints else None)
            if route in ("gemini-generate-content", "images"):
                result.append(ClassifiedModel(model_id, "image", merged, route))
            continue
        if declared_kind in _MODEL_KINDS:
            result.append(ClassifiedModel(model_id, declared_kind, merged))
            continue
        if _declares_image(entry, endpoints):
            route = "gemini-generate-content" if "gemini" in endpoints else "images" if "image-generation" in endpoints else None
            if route:
                result.append(ClassifiedModel(model_id, "image", merged, route))
            continue
        if _declares_video(entry, endpoints):
            result.append(ClassifiedModel(model_id, "video", merged))
        elif "embeddings" in endpoints:
            result.append(ClassifiedModel(model_id, "embedding", merged))
        elif "jina-rerank" in endpoints:
            result.append(ClassifiedModel(model_id, "rerank", merged))
        elif _TEXT_ENDPOINTS.intersection(own):
            result.append(ClassifiedModel(model_id, "text", merged))
    return result


def needs_catalog(models: list[dict]) -> bool:
    """Whether an older `/v1/models` response still needs `/api/pricing` to classify media."""
    for model in models:
        if not isinstance(model, dict) or model.get("kind") in _MODEL_KINDS:
            continue
        endpoints = {item for item in model.get("supported_endpoint_types") or [] if isinstance(item, str)}
        if endpoints.intersection({"image-generation", "openai-video", "embeddings", "jina-rerank"}):
            continue
        if endpoints.intersection(_TEXT_ENDPOINTS | {"gemini"}):
            return True
    return False


def model_docs_url(model: ClassifiedModel, locale: str = "en") -> str:
    slug = model.id.lower().replace(".", "-")
    kind = "video" if model.kind == "video" else "image"
    return f"{DOCS_URL}{'/zh' if locale == 'zh' else ''}/models/{kind}/{slug}/"
