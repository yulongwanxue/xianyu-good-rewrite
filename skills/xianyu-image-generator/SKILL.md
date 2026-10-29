---
name: xianyu-image-generator
description: 使用当前机器的 Codex 配置和 API 连接，根据提示词生成 PNG/JPEG/WebP 图片并保存到项目目录。适用于商品首图、营销视觉和其他需要真实位图输出的场景；不负责商品文案改写或营销方案策划。
---

# 闲鱼图片生成器

此技能负责实际调用图片生成 API 并保存图片。营销文案与首图策略由 xianyu-cover-designer 负责；需要从商品文案策划首图时先调用该技能，再把 rendering.prompt_with_text 或 rendering.prompt_without_text 交给本技能。

## 配置读取

执行脚本时按以下优先级读取配置：

1. OPENAI_API_KEY 和 OPENAI_BASE_URL 环境变量（如果已设置）。
2. CODEX_HOME 指向目录中的 auth.json 与 config.toml。
3. Windows 默认使用 C:\Users\<当前用户>\.codex。

脚本从 auth.json 的 OPENAI_API_KEY 读取密钥，从 config.toml 的 [model_providers.<model_provider>] 读取 base_url。密钥只用于请求，不打印到终端、提示词、日志或输出文件。可以用 --codex-dir 指定其他配置目录，用 --base-url 临时覆盖 API 地址。

## 直接生成

在项目根目录执行：

    python skills/xianyu-image-generator/scripts/generate_image.py --prompt "一只穿着白色宇航服的太空猫，漂浮在星云与地球之间，电影感数字插画，无文字无水印" --out outputs/imagegen/space-cat.png

默认模型为 gpt-image-2，默认尺寸为 1024x1024，默认质量为 auto。可以通过 --model、--size、--quality、--background、--output-format 和 --n 调整。已有输出文件不会被覆盖，确认替换时才使用 --force。

生成多个结果时，--n 3 会将结果保存为带 -1、-2、-3 后缀的文件。脚本支持 API 返回的 b64_json 和 url 两种图片结果。

## 运行前检查

先用 --dry-run 检查实际请求，不会发送 API 请求，也不会读取或显示密钥：

    python skills/xianyu-image-generator/scripts/generate_image.py --prompt "太空猫" --dry-run

真实生成后检查主体、构图、文字准确性、是否出现水印或伪造商品截图。需要透明背景时传 --background transparent，并使用 PNG 或 WebP。

## 与封面设计技能衔接

- xianyu-cover-designer 只输出策划 JSON 与两套提示词，不执行 API 调用。
- 本技能接收完整提示词，负责调用图片 API、解码/下载结果并保存到 outputs/imagegen/。
- 如果需要中文文字准确，优先使用无字背景提示词生成，再用程序叠字；除非用户明确接受模型直接绘制中文。

## 限制

- 只从配置目录读取 API 密钥，不把密钥写入项目。
- 不默认覆盖任何现有图片。
- API 不支持或返回错误时，保留脱敏错误信息并停止，不伪造成功文件。

