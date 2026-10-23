import asyncio
import json
import os
import re
import tempfile
from pathlib import Path

import yaml
from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.message_components import Video
from astrbot.api.star import Context, Star

from .modelflare_core import ModelflareClient, ModelflareError, classify_models, describe_error, model_docs_url, needs_catalog
from .modelflare_core.client import fetch_catalog
from .modelflare_core.media import create_video, download_video, generate_image, get_video, wait_for_video

ATTRIBUTION_PLUGIN = "modelflare-astrbot"
UTM_SOURCE = "astrbot"
VERSION = str(yaml.safe_load((Path(__file__).parent / "metadata.yaml").read_text(encoding="utf-8"))["version"]).lstrip("v")
EXTENSIONS = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}


class ModelflarePlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self.output_dir = Path(tempfile.gettempdir()) / "astrbot_modelflare"

    def _client(self) -> ModelflareClient:
        return ModelflareClient(self.config.get("api_key", ""), ATTRIBUTION_PLUGIN, VERSION, self.config.get("base_url") or "china")

    def _classified(self, client: ModelflareClient):
        listed = client.list_models()
        catalog = fetch_catalog() if needs_catalog(listed) else None
        return classify_models(listed, catalog), {entry.get("id") for entry in listed}

    def _video_path(self, task_id: str) -> Path:
        safe_id = re.sub(r"[^a-zA-Z0-9._-]+", "-", task_id).strip("-") or "video"
        return self.output_dir / f"{safe_id}.mp4"

    async def _send_video(self, event: AstrMessageEvent, client: ModelflareClient, task_id: str):
        data = await asyncio.to_thread(download_video, client, task_id)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        path = self._video_path(task_id)
        path.write_bytes(data)
        yield event.chain_result([Video.fromFileSystem(str(path))])

    def _explain(self, error: Exception, client: ModelflareClient | None, model_id: str | None) -> str:
        if not isinstance(error, ModelflareError):
            return str(error)
        listed = None
        if error.kind == "model_not_found" and client and model_id:
            try:
                listed = model_id in self._classified(client)[1]
            except ModelflareError:
                listed = None
        return describe_error(error, "zh", UTM_SOURCE, model_listed=listed)

    def _find(self, client: ModelflareClient, model_id: str, kind: str):
        models, listed = self._classified(client)
        for model in models:
            if model.id == model_id and model.kind == kind:
                return model
        if model_id in listed:
            raise ValueError(f"{model_id} 不是可用的{'图像' if kind == 'image' else '视频'}模型，请用 /mf_models {kind} 查看。")
        raise ModelflareError("model_not_found", model_id)

    @filter.command("mf_models")
    async def mf_models(self, event: AstrMessageEvent, kind: str = "image"):
        """列出这把 Modelflare Key 可用的媒体模型：/mf_models image|video"""
        if kind not in ("image", "video"):
            yield event.plain_result("用法：/mf_models image|video")
            return
        client = None
        try:
            client = self._client()
            models, _ = await asyncio.to_thread(self._classified, client)
            rows = [model for model in models if model.kind == kind]
            if not rows:
                yield event.plain_result(f"没有可用的 {kind} 模型。")
                return
            lines = [f"- {m.id}" + (f"  {model_docs_url(m, 'zh')}" if kind in ("image", "video") else "") for m in rows]
            yield event.plain_result("\n".join(lines))
        except Exception as ex:
            yield event.plain_result(self._explain(ex, client, None))

    @filter.command("mf_image")
    async def mf_image(self, event: AstrMessageEvent):
        """用 Modelflare 生成图像：/mf_image 提示词"""
        prompt = event.message_str.partition(" ")[2].strip()
        model_id = self.config.get("image_model", "")
        if not prompt or not model_id:
            yield event.plain_result("用法：/mf_image 提示词。请先在插件配置里设置默认图像模型。")
            return
        client = None
        try:
            client = self._client()
            model = await asyncio.to_thread(self._find, client, model_id, "image")
            parameters = json.loads(self.config.get("image_parameters") or "{}")
            images = await asyncio.to_thread(generate_image, client, model, prompt, parameters)
            self.output_dir.mkdir(parents=True, exist_ok=True)
            for data, mime_type in images:
                fd, path = tempfile.mkstemp(suffix=EXTENSIONS.get(mime_type, ".png"), dir=self.output_dir)
                with os.fdopen(fd, "wb") as file:
                    file.write(data)
                yield event.image_result(path)
        except Exception as ex:
            logger.warning(f"Modelflare image generation failed: {ex}")
            yield event.plain_result(self._explain(ex, client, model_id))

    @filter.command("mf_video")
    async def mf_video(self, event: AstrMessageEvent):
        """用 Modelflare 生成视频：/mf_video 提示词"""
        prompt = event.message_str.partition(" ")[2].strip()
        model_id = self.config.get("video_model", "")
        if not prompt or not model_id:
            yield event.plain_result("用法：/mf_video 提示词。请先在插件配置里设置默认视频模型。")
            return
        client = None
        try:
            client = self._client()
            model = await asyncio.to_thread(self._find, client, model_id, "video")
            request = json.loads(self.config.get("video_parameters") or "{}")
            request.setdefault("prompt", prompt)
            task = await asyncio.to_thread(create_video, client, model.id, request)
            yield event.plain_result(f"视频任务已创建：{task['id']}，生成中……")
            wait = max(0, min(int(self.config.get("video_wait_seconds") or 300), 1800))
            status = await asyncio.to_thread(wait_for_video, client, task["id"], wait)
            if status.get("status") != "completed":
                reason = (status.get("error") or {}).get("message") if status.get("status") == "failed" else None
                yield event.plain_result(f"视频任务 {task['id']} 当前状态：{status.get('status')}" + (f"，原因：{reason}" if reason else ""))
                return
            # Result URLs expire, so the file is downloaded as soon as it is ready.
            async for result in self._send_video(event, client, task["id"]):
                yield result
        except Exception as ex:
            logger.warning(f"Modelflare video generation failed: {ex}")
            yield event.plain_result(self._explain(ex, client, model_id))

    @filter.command("mf_video_status")
    async def mf_video_status(self, event: AstrMessageEvent, task_id: str = ""):
        """查询已有视频任务：/mf_video_status <task_id>"""
        if not task_id:
            yield event.plain_result("用法：/mf_video_status <task_id>")
            return
        client = None
        try:
            client = self._client()
            status = await asyncio.to_thread(get_video, client, task_id)
            yield event.plain_result(json.dumps(status, ensure_ascii=False))
        except Exception as ex:
            yield event.plain_result(self._explain(ex, client, None))

    @filter.command("mf_video_download")
    async def mf_video_download(self, event: AstrMessageEvent, task_id: str = ""):
        """下载已完成视频：/mf_video_download <task_id>"""
        if not task_id:
            yield event.plain_result("用法：/mf_video_download <task_id>")
            return
        client = None
        try:
            client = self._client()
            status = await asyncio.to_thread(get_video, client, task_id)
            if status.get("status") != "completed":
                yield event.plain_result(f"视频任务 {task_id} 当前状态：{status.get('status')}")
                return
            async for result in self._send_video(event, client, task_id):
                yield result
        except Exception as ex:
            yield event.plain_result(self._explain(ex, client, None))
