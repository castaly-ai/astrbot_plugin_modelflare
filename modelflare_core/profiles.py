from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ModelProfile:
    context_window: int
    max_input_tokens: int
    max_output_tokens: int
    input_modalities: tuple[str, ...]
    tool_calling: bool
    reasoning: bool
    temperature_supported: bool


_DEFAULT = ModelProfile(144_384, 128_000, 16_384, ("text",), False, False, True)


def _profile(
    context: int,
    output: int,
    modalities: tuple[str, ...],
    *,
    reasoning: bool = True,
    temperature_supported: bool = True,
) -> ModelProfile:
    return ModelProfile(context, max(1, context - output), output, modalities, True, reasoning, temperature_supported)


def _fallback(model_id: str) -> ModelProfile:
    if model_id == "claude-haiku-4-5":
        return _profile(200_000, 64_000, ("text", "image"), temperature_supported=False)
    if model_id.startswith("claude-"):
        return _profile(1_000_000, 128_000, ("text", "image"), temperature_supported=False)
    if model_id.startswith("gemini-"):
        return _profile(1_048_576, 65_536, ("text", "image"))
    if model_id.startswith("grok-"):
        return _profile(500_000, 128_000, ("text", "image"))
    if model_id == "deepseek-v4.1-flash":
        return _profile(1_000_000, 384_000, ("text", "image"))
    if model_id.startswith("deepseek-"):
        return _profile(1_000_000, 384_000, ("text",))
    if model_id == "glm-5.3-flash":
        return _profile(1_000_000, 131_072, ("text", "image"))
    if model_id.startswith("glm-"):
        return _profile(1_000_000, 131_072, ("text",))
    if model_id.startswith("kimi-"):
        return _profile(1_048_576, 131_072, ("text", "image"))
    if model_id.startswith("qwen"):
        return _profile(1_000_000, 131_072, ("text", "image"))
    if model_id.startswith("muse-"):
        return _profile(1_048_576, 131_072, ("text", "image"))
    if model_id.startswith(("gpt-5", "gpt-6")) or model_id == "codex-auto-review":
        return ModelProfile(1_050_000, 922_000, 128_000, ("text", "image"), True, True, False)
    return _DEFAULT


def _positive_int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and 0 < value <= 10_000_000 else None


def build_model_profile_index(value: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(value, dict):
        raise ValueError("Invalid model metadata")
    index: dict[str, dict[str, Any]] = {}
    ambiguous: set[str] = set()
    for canonical_id, candidate in value.items():
        if not isinstance(canonical_id, str) or not isinstance(candidate, dict):
            continue
        limit = candidate.get("limit") if isinstance(candidate.get("limit"), dict) else {}
        context = _positive_int(candidate.get("context_window")) or _positive_int(limit.get("context"))
        output = _positive_int(candidate.get("max_output_tokens")) or _positive_int(limit.get("output"))
        explicit_input = _positive_int(candidate.get("max_input_tokens")) or _positive_int(limit.get("input"))
        max_input = explicit_input or (context - output if context and output and context > output else context)
        raw_modalities = candidate.get("input_modalities")
        if not isinstance(raw_modalities, list):
            raw_modalities = (candidate.get("modalities") or {}).get("input") if isinstance(candidate.get("modalities"), dict) else None
        modalities = tuple(item for item in raw_modalities if isinstance(item, str)) if isinstance(raw_modalities, list) else None
        tool_calling = candidate.get("tool_calling")
        if not isinstance(tool_calling, bool):
            tool_calling = candidate.get("tool_call")
        temperature = candidate.get("temperature_supported")
        if not isinstance(temperature, bool):
            temperature = candidate.get("temperature")
        profile = {
            **({"context_window": context} if context else {}),
            **({"max_input_tokens": max_input} if max_input else {}),
            **({"max_output_tokens": output} if output else {}),
            **({"input_modalities": modalities} if modalities is not None else {}),
            **({"tool_calling": tool_calling} if isinstance(tool_calling, bool) else {}),
            **({"reasoning": candidate["reasoning"]} if isinstance(candidate.get("reasoning"), bool) else {}),
            **({"temperature_supported": temperature} if isinstance(temperature, bool) else {}),
        }
        if not profile:
            continue
        model_id = canonical_id.rsplit("/", 1)[-1]
        if model_id in ambiguous:
            continue
        if model_id in index:
            del index[model_id]
            ambiguous.add(model_id)
        else:
            index[model_id] = profile
    return index


def resolve_model_profile(model_id: str, profiles: dict[str, dict[str, Any]] | None = None) -> ModelProfile:
    fallback = _fallback(model_id)
    profiles = profiles or {}
    candidates = [model_id]
    for suffix in ("-high", "-medium", "-low"):
        if model_id.endswith(suffix):
            candidates.append(model_id[: -len(suffix)])
            break
    discovered = next((profiles.get(candidate) for candidate in candidates if profiles.get(candidate) is not None), {})
    context_window = _positive_int(discovered.get("context_window")) or fallback.context_window
    max_input_tokens = _positive_int(discovered.get("max_input_tokens")) or fallback.max_input_tokens
    max_output_tokens = _positive_int(discovered.get("max_output_tokens")) or fallback.max_output_tokens
    modalities = discovered.get("input_modalities")
    input_modalities = (
        tuple(item for item in modalities if isinstance(item, str))
        if isinstance(modalities, (list, tuple))
        else fallback.input_modalities
    )
    tool_calling = discovered.get("tool_calling")
    reasoning = discovered.get("reasoning")
    temperature_supported = discovered.get("temperature_supported")
    return ModelProfile(
        context_window=context_window,
        max_input_tokens=max_input_tokens,
        max_output_tokens=max_output_tokens,
        input_modalities=input_modalities,
        tool_calling=tool_calling if isinstance(tool_calling, bool) else fallback.tool_calling,
        reasoning=reasoning if isinstance(reasoning, bool) else fallback.reasoning,
        temperature_supported=(
            temperature_supported if isinstance(temperature_supported, bool) else fallback.temperature_supported
        ),
    )
