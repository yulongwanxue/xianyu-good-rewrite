


# 闲鱼商品重写-技能包

## 文案重写

`skills/xianyu-copy-rewriter` 从原商品标题和描述中提取商品内容、功能、交付物、服务范围及使用条件，结合 [本店经营规则](business/rules/xianyu-shop-operations.md) 生成新标题与完整商品描述。

经营规则维护自动网盘交付、网络资料采集整理收费说明和侵权反馈方式，并明确各项适用范围。卖家审核备注与买家文案分开。输入与成品示例见 [改写示例](skills/xianyu-copy-rewriter/references/examples.md)。

## 图片生成

skills/xianyu-image-generator 负责实际调用图片生成 API。它会自动读取当前用户
.codex/auth.json 中的 OPENAI_API_KEY，以及 .codex/config.toml 中当前模型提供商
的 base_url，不会把密钥写入项目。

先检查请求：

    python skills/xianyu-image-generator/scripts/generate_image.py --prompt "太空猫" --dry-run

生成图片：

    python skills/xianyu-image-generator/scripts/generate_image.py --prompt "一只穿着宇航服的太空猫，漂浮在星云与地球之间，无文字无水印" --out outputs/imagegen/space-cat.png

营销型闲鱼首图先使用 skills/xianyu-cover-designer 生成设计方案，再把其中的完整提示词交给图片生成技能。

control 的候选页面也可以通过 codex-task-managers 调用本项目，执行文案改写、首图生成和商品包导入。联调字段、模板契约和配置见 workflows/xianyu-goods-rewrite/WORKFLOW.md。
