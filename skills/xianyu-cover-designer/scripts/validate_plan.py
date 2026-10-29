#!/usr/bin/env python3
"""对 xianyu-cover-designer v1.0 的生成方案 JSON 做基础结构检验。

用法：python scripts/validate_plan.py examples/virtual-course-plan.json
     cat plan.json | python scripts/validate_plan.py -

只验证格式、字段映射和常见遗漏，不判断商业事实真伪，也不审核实际生图效果。
"""

import argparse
import json
import re
import sys
from pathlib import Path

TOP_KEYS = {
    "schema_version", "status", "product_analysis", "marketing", "design",
    "on_image_text", "image_spec", "rendering", "preflight",
}
CATEGORIES = {
    "virtual_resource", "virtual_course", "virtual_template", "virtual_tool",
    "service_consulting", "service_delivery", "service_technical", "other",
}
STRATEGIES = {
    "content_showcase", "problem_solution", "practical_value",
    "professional_trust", "efficiency_convenience",
}
ROLES = {"headline", "subline", "small_tag"}


def validate(plan):
    errors = []
    warnings = []

    def err(message):
        errors.append(message)

    def warn(message):
        warnings.append(message)

    def obj(parent, key, path=""):
        value = parent.get(key) if isinstance(parent, dict) else None
        if not isinstance(value, dict):
            err(f"{path}{key}: 必须为对象")
            return {}
        return value

    def string(parent, key, path, allow_empty=False):
        value = parent.get(key)
        if not isinstance(value, str) or (not value.strip() and not allow_empty):
            err(f"{path}{key}: 必须为{'可空' if allow_empty else '非空'}字符串")
            return ""
        return value

    def array(parent, key, path):
        value = parent.get(key)
        if not isinstance(value, list):
            err(f"{path}{key}: 必须为数组")
            return []
        return value

    def number(value):
        return isinstance(value, (int, float)) and not isinstance(value, bool)

    if not isinstance(plan, dict):
        return ["根节点必须是 JSON 对象"], []
    for key in sorted(TOP_KEYS - set(plan)):
        err(f"缺少顶层字段: {key}")
    if plan.get("schema_version") != "1.0":
        err("schema_version: 当前仅支持字符串 1.0")
    if plan.get("status") not in {"ready", "needs_review"}:
        err("status: 只能是 ready 或 needs_review")
    if set(plan) - TOP_KEYS:
        warn("发现额外顶层字段，可能影响严格解析器的兼容性")

    p = obj(plan, "product_analysis")
    if p.get("category") not in CATEGORIES:
        err("product_analysis.category: 不支持的类别")
    for key in ("what_is_sold", "target_user", "delivery_form"):
        string(p, key, "product_analysis.")
    for key in ("facts_from_copy", "unverified_claims"):
        values = array(p, key, "product_analysis.")
        if any(not isinstance(v, str) or not v.strip() for v in values):
            err(f"product_analysis.{key}: 元素必须为非空字符串")

    m = obj(plan, "marketing")
    if m.get("strategy") not in STRATEGIES:
        err("marketing.strategy: 不支持的营销策略")
    for key in ("primary_hook", "why_this_angle"):
        string(m, key, "marketing.")
    points = array(m, "supporting_points", "marketing.")
    if len(points) > 2:
        err("marketing.supporting_points: 至多两项")
    if any(not isinstance(v, str) or not v.strip() for v in points):
        err("marketing.supporting_points: 元素必须为非空字符串")

    d = obj(plan, "design")
    for key in ("concept", "composition", "hero_visual", "visual_evidence", "style"):
        string(d, key, "design.")
    palette = array(d, "palette", "design.")
    if not 2 <= len(palette) <= 3 or any(
        not isinstance(color, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", color)
        for color in palette
    ):
        err("design.palette: 需要 2-3 个合法的 HEX RGB 颜色")
    margin = d.get("safe_margin_pct")
    if not number(margin) or not 0 <= margin <= 20:
        err("design.safe_margin_pct: 需要 0-20 的数值")
    elif not 8 <= margin <= 10:
        warn("design.safe_margin_pct: 与推荐的 8%-10% 范围不同")
    avoid = array(d, "avoid_elements", "design.")
    if any(not isinstance(v, str) for v in avoid):
        err("design.avoid_elements: 元素必须为字符串")

    text = obj(plan, "on_image_text")
    headline = string(text, "headline", "on_image_text.")
    subline = string(text, "subline", "on_image_text.", allow_empty=True)
    small_tag = string(text, "small_tag", "on_image_text.", allow_empty=True)
    if len(headline) > 20:
        warn("on_image_text.headline: 文案较长，请确认手机缩略图可读性")
    if len(subline) > 24:
        warn("on_image_text.subline: 辅助文案较长")

    spec = obj(plan, "image_spec")
    width, height, ratio = spec.get("width"), spec.get("height"), spec.get("aspect_ratio")
    if (not isinstance(width, int) or isinstance(width, bool) or width < 512 or width > 4096
        or not isinstance(height, int) or isinstance(height, bool) or height < 512 or height > 4096):
        err("image_spec: 宽高必须是 512-4096 的整数")
    elif not ((ratio == "1:1" and width == height) or (ratio == "3:4" and width * 4 == height * 3)):
        err("image_spec: 宽高与比例不一致；当前支持 1:1、3:4")
    if spec.get("format") not in {"png", "jpg", "jpeg"}:
        err("image_spec.format: 目前支持 png、jpg、jpeg")

    r = obj(plan, "rendering")
    if r.get("recommended_mode") not in {"direct_text", "background_plus_overlay"}:
        err("rendering.recommended_mode: 取值不合法")
    pt = string(r, "prompt_with_text", "rendering.")
    pn = string(r, "prompt_without_text", "rendering.")
    string(r, "negative_prompt", "rendering.")
    if pt and len(pt) < 100:
        warn("rendering.prompt_with_text: 提示词过短，可能缺少商品主体与构图说明")
    if pn and len(pn) < 100:
        warn("rendering.prompt_without_text: 提示词过短，可能缺少设计约束")
    for phrase in (headline, subline, small_tag):
        if phrase and phrase not in pt:
            err(f"rendering.prompt_with_text: 缺少准确上图文字: {phrase}")
    if pn and not any(phrase in pn for phrase in ("不出现", "不要出现", "绝不出现", "完全不出现")):
        warn("rendering.prompt_without_text: 未明确禁止生成文字")

    layers = array(r, "overlay_layers", "rendering.")
    required_text = {"headline": headline, "subline": subline, "small_tag": small_tag}
    seen = set()
    if len(layers) > 3:
        err("rendering.overlay_layers: 最多三项文字")
    for index, layer in enumerate(layers):
        path = f"rendering.overlay_layers[{index}]"
        if not isinstance(layer, dict):
            err(f"{path}: 必须为对象")
            continue
        role = layer.get("role")
        if role not in ROLES:
            err(f"{path}.role: 非法文本角色")
            continue
        if role in seen:
            err(f"{path}.role: 重复的文本角色 {role}")
        seen.add(role)
        if not required_text.get(role):
            err(f"{path}: 不应给空文本创建叠字图层")
        elif layer.get("text") != required_text[role]:
            err(f"{path}.text: 必须与 on_image_text.{role} 完全一致")
        bbox = layer.get("bbox_pct")
        if not isinstance(bbox, list) or len(bbox) != 4 or not all(number(v) for v in bbox):
            err(f"{path}.bbox_pct: 必须有四个数值 [x,y,w,h]")
        else:
            x, y, w, h = bbox
            if min(x, y) < 0 or min(w, h) <= 0 or x + w > 100 or y + h > 100:
                err(f"{path}.bbox_pct: 坐标超出画布或大小非正数")
        if layer.get("align") not in {"left", "center", "right"}:
            err(f"{path}.align: 只能是 left、center、right")
        ml = layer.get("max_lines")
        if not isinstance(ml, int) or isinstance(ml, bool) or not 1 <= ml <= 3:
            err(f"{path}.max_lines: 需要 1-3 的整数")
    for role, val in required_text.items():
        if val and role not in seen:
            err(f"rendering.overlay_layers: 缺少 {role} 图层")

    pf = obj(plan, "preflight")
    if not isinstance(pf.get("plan_passed"), bool):
        err("preflight.plan_passed: 必须为布尔值")
    for key in ("checkpoints", "needs_confirmation", "rendering_risks"):
        arr = array(pf, key, "preflight.")
        if any(not isinstance(v, str) or not v.strip() for v in arr):
            err(f"preflight.{key}: 元素必须为非空字符串")
    if plan.get("status") == "ready" and pf.get("plan_passed") is False:
        err("status=ready 但 preflight.plan_passed=false")
    return errors, warnings


def main():
    parser = argparse.ArgumentParser(description="校验闲鱼营销首图策划 JSON 的基础结构")
    parser.add_argument("file", help="JSON 文件路径，或 -（标准输入）")
    args = parser.parse_args()
    try:
        data = sys.stdin.read() if args.file == "-" else Path(args.file).read_text(encoding="utf-8")
        plan = json.loads(data)
    except (OSError, ValueError) as exc:
        print(f"JSON 读取失败: {exc}", file=sys.stderr)
        return 2
    errors, warnings = validate(plan)
    for warning in warnings:
        print(f"提示: {warning}")
    for error in errors:
        print(f"错误: {error}", file=sys.stderr)
    if errors:
        print(f"校验失败，{len(errors)} 个错误，{len(warnings)} 个提示", file=sys.stderr)
        return 1
    print(f"校验通过，0 个错误，{len(warnings)} 个提示")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
