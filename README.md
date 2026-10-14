# astrbot_plugin_modelflare

在 AstrBot 机器人里，用一个 Modelflare **Smart API Key** 调用你账号可用的全部图像和视频模型。

Generate images and videos from your AstrBot bot with one Modelflare **Smart API Key** for every model available to your account.

## 获取 Smart API Key

1. 注册：https://modelflare.dev/sign-up?utm_source=astrbot&utm_medium=plugin&utm_campaign=integrations
2. 控制台 API Keys →「Create Smart API Key」，选择路由策略（均衡 / 稳定优先 / 低价优先）。

## 安装

在 AstrBot 管理界面：**插件 → 安装插件（+）→ 从链接安装**，填写 `https://github.com/castaly-ai/astrbot_plugin_modelflare`；或在插件市场搜索 Modelflare。

## 配置

在插件配置中填写：

| 配置 | 说明 |
|---|---|
| Modelflare Smart API Key | 你的 Smart API Key |
| Base URL | `china` → https://origin.modelflare.dev/v1（默认）· `global` → https://modelflare.dev/v1 · 或自定义地址 |
| 默认图像模型 / 默认视频模型 | 用 `/mf_models image`、`/mf_models video` 查看可用的模型 ID |
| 图像模型参数（JSON） | 按 https://docs.modelflare.dev/zh/models/image/ 上该模型页面填写 |
| 视频最长等待秒数 | 默认 300 秒 |

## 命令

| 命令 | 作用 |
|---|---|
| `/mf_models image\|video\|text` | 列出这把 Key 可用的模型，图像和视频模型附带文档链接 |
| `/mf_image 提示词` | 用默认图像模型生成图片并发送 |
| `/mf_video 提示词` | 用默认视频模型生成视频，完成后发送；超时则返回任务 ID |

模型列表来自 Key 的 `GET /v1/models`，新模型上线无需改 Key。调用按实际用量从 Modelflare 余额扣费，可在 https://modelflare.dev/usage-logs 查看。

## 常见问题

- **401**：Key 缺失或无效，请在 https://modelflare.dev/keys 创建 Smart API Key。
- **`model_not_found`**：普通 Key 只能调用其分组内的模型；Smart API Key 可调用你账号可用的全部模型。
- **403 `insufficient_user_quota`**：请在 https://modelflare.dev/billing 充值。

MIT © Havenbyte LLC
