from .client import ModelflareError
from .config import BILLING_URL, KEYS_URL, sign_up_url

SMART_KEY_HINT = {
    "en": "Recommended: one Smart API Key calls every model available to your account, and new models work without editing the key. Create one under API Keys → Create Smart API Key.",
    "zh": "推荐使用 Smart API Key：一个 Key 调用你账号可用的全部模型，新模型上线无需改 Key。在控制台 API Keys →“Create Smart API Key”创建。",
}


def describe_error(error: ModelflareError, locale: str, utm_source: str, model_listed: bool | None = None) -> str:
    """User-facing explanation of a gateway error; never contains the key.

    For model_not_found, pass whether the model is in the key's /v1/models
    list; unknown is treated as not listed.
    """
    zh = locale == "zh"
    sign_up = sign_up_url(utm_source)
    kind = error.kind
    if kind == "unauthorized":
        text = (
            f"API Key 缺失或无效。请在 {KEYS_URL} 创建 Smart API Key；还没有账号可在 {sign_up} 注册。"
            if zh
            else f"The API key is missing or invalid. Create a Smart API Key at {KEYS_URL}, or sign up at {sign_up}."
        )
    elif kind == "insufficient_quota":
        text = f"Modelflare 余额不足，请在 {BILLING_URL} 充值。" if zh else f"Your Modelflare balance is empty. Top up at {BILLING_URL}."
    elif kind == "model_not_found" and model_listed:
        text = "该模型暂时不可用，请稍后重试。" if zh else "This model is temporarily unavailable. Please try again later."
    elif kind == "model_not_found":
        text = (
            f"当前 Key 不能调用此模型。如果你用的是普通 Key，换用 Smart API Key 即可调用你账号可用的全部模型；如果已经是 Smart API Key，说明此模型在你的账号下暂不可用。获取 Smart API Key：{sign_up}"
            if zh
            else f"This key can't call this model. If it is a regular key, switch to a Smart API Key to call every model available to your account. If it is already a Smart API Key, this model isn't available to your account right now. Get a Smart API Key: {sign_up}"
        )
    elif kind == "unsupported_endpoint":
        text = "该模型不支持这种请求类型，请换用对应的接口或模型。" if zh else "This model does not support this kind of request. Use the matching endpoint or another model."
    elif kind == "rate_limited":
        text = "请求过于频繁，请稍后重试。" if zh else "Too many requests. Please retry shortly."
    elif kind == "timeout":
        text = "请求超时，请稍后重试。" if zh else "The request timed out. Please try again."
    elif kind == "network":
        text = "无法连接 Modelflare。请检查网络，或切换全球 / 国内 Base URL。" if zh else "Could not reach Modelflare. Check your network or switch between the global and China base URLs."
    else:
        text = f"Modelflare 返回错误：{error.message}" if zh else f"Modelflare returned an error: {error.message}"
    if error.request_id:
        text += f"（请求 ID：{error.request_id}）" if zh else f" (request ID: {error.request_id})"
    return text
