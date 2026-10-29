# 输出数据契约（v1.0）

本技能默认输出**单个 UTF-8 JSON 对象**，不加 markdown 代码围栏、注释或开头结尾说明。面向后续图片生成脚本，保持字段稳定。

## 1. 顶层必填字段

| 字段 | 类型 | 说明 |
|---|---|---|
| `schema_version` | string | 固定 `"1.0"` |
| `status` | string | `"ready"` 或 `"needs_review"` |
| `product_analysis` | object | 商品理解与信息来源 |
| `marketing` | object | 主营销策略、钩子、支持信息 |
| `design` | object | 核心画面设计方案 |
| `on_image_text` | object | 要印在首图中的精确短文案 |
| `image_spec` | object | 生图规格 |
| `rendering` | object | 可直接执行的生成指令和叠字建议 |
| `preflight` | object | 生成前文本审查结论 |

## 2. 字段定义（全部必填，可用空字符串或空数组表达不适用）

```json
{
  "schema_version": "1.0",
  "status": "ready",
  "product_analysis": {
    "category": "virtual_course",
    "what_is_sold": "商品具体是什么",
    "target_user": "目标人群或未明确",
    "delivery_form": "实际交付/服务形式或未明确",
    "facts_from_copy": ["可用于视觉表达的文案事实"],
    "unverified_claims": ["若有，填写仍待证实的敏感主张"]
  },
  "marketing": {
    "strategy": "practical_value",
    "primary_hook": "一条核心点击理由",
    "supporting_points": ["最多两条可信支撑点"],
    "why_this_angle": "为什么这个角度符合商品与目标用户"
  },
  "design": {
    "concept": "一句话视觉创意",
    "composition": "明确的构图与商品/文字位置",
    "hero_visual": "商品主体或交付物如何具体展示",
    "visual_evidence": "来源明确的视觉证据或抽象示意",
    "style": "画面审美和质感",
    "palette": ["#16263D", "#F7F5ED", "#FFB64C"],
    "safe_margin_pct": 9,
    "avoid_elements": ["本品类特别不应该出现的元素"]
  },
  "on_image_text": {
    "headline": "清晰的商品身份标题",
    "subline": "一条短卖点或空字符串",
    "small_tag": "次要角标或空字符串"
  },
  "image_spec": {
    "width": 1080,
    "height": 1080,
    "aspect_ratio": "1:1",
    "format": "png"
  },
  "rendering": {
    "recommended_mode": "direct_text",
    "prompt_with_text": "完整、明确、可直接给图片模型的含字版提示词",
    "prompt_without_text": "完整、明确、可直接给图片模型的无字背景版提示词",
    "negative_prompt": "与当前商品相关的具体排除事项",
    "overlay_layers": [
      {
        "role": "headline",
        "text": "与 on_image_text.headline 完全一致",
        "bbox_pct": [9, 11, 54, 21],
        "align": "left",
        "max_lines": 2
      }
    ]
  },
  "preflight": {
    "plan_passed": true,
    "checkpoints": ["已核查的策划层要点"],
    "needs_confirmation": [],
    "rendering_risks": ["生成后需要复核的内容，如中文文字准确性"]
  }
}
```

以上为结构模板，示例文字不是实际商品内容，不要直接套用。两份真实模拟商品样本位于 `examples/`。

## 3. 枚举与字段规则

- `product_analysis.category`：`virtual_resource`、`virtual_course`、`virtual_template`、`virtual_tool`、`service_consulting`、`service_delivery`、`service_technical`、`other`。
- `marketing.strategy`：`content_showcase`、`problem_solution`、`practical_value`、`professional_trust`、`efficiency_convenience`。
- `rendering.recommended_mode`：`direct_text`（默认，能直接接普通生图脚本）或 `background_plus_overlay`（外部脚本已实现文字叠加时可用）。**两套 prompt 始终同时输出**。
- `on_image_text.headline`：非空，必须让用户认识商品类别。建议 6–14 汉字左右；超出时从简，不强制截断导致歧义。
- `on_image_text.subline` 与 `small_tag`：可为空字符串；有内容时应该简短，且每一条能回溯到用户输入。
- `marketing.supporting_points`：最多 2 条。
- `design.palette`：建议 2–3 个合法 HEX 色值字符串。
- `image_spec`：默认 1080×1080、1:1、png；仅在输入明确要求时采用其他合法尺寸，3:4 可设 900×1200。
- `design.safe_margin_pct`：建议 8–10，非闲鱼平台强制规定。
- `overlay_layers`：文本列表可 1–3 项，不包含为空的文案；文字必须分别与 `on_image_text` 完全一致。每个 `bbox_pct` 是 `[x,y,width,height]` 的百分比坐标，整项应落在 0–100 且不要明显重叠。
- `preflight.plan_passed`：只针对提示词方案是否完整、一致与风险可控，不表示图已生成或已审核。
- `status=needs_review`：存在待确认且可能影响真实商品表达的关键事实或重大合规风险时使用。可以给保守设计，但不得带上未确认的营销承诺。
- 高风险绝对效果或社会证明不能从未审核的改写文本直接迁移成首图卖点。若提到，列入 `unverified_claims` 和 `needs_confirmation`。

## 4. 脚本字段消费方式

普通文生图脚本：

```python
prompt = plan["rendering"]["prompt_with_text"]
negative_prompt = plan["rendering"]["negative_prompt"]
width = plan["image_spec"]["width"]
height = plan["image_spec"]["height"]
```

支持后期叠字的脚本：

```python
background_prompt = plan["rendering"]["prompt_without_text"]
text_layers = plan["rendering"]["overlay_layers"]
# 由你的生图和排版程序分别处理，不属于本技能执行范围。
```

随附 `scripts/validate_plan.py` 可验证 JSON 的基本字段结构、尺寸和文本映射；它不是法律审核或真实图片视觉质检器。
