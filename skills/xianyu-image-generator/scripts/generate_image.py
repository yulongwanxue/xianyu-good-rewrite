#!/usr/bin/env python3
"""Generate raster images through the OpenAI-compatible API configured for Codex."""

from __future__ import annotations

import argparse
import base64
import json
import os
from pathlib import Path
import sys
from typing import Any
import urllib.error
import urllib.request


DEFAULT_MODEL = "gpt-image-2"
DEFAULT_SIZE = "1024x1024"
DEFAULT_QUALITY = "auto"
DEFAULT_OUTPUT_FORMAT = "png"
DEFAULT_TIMEOUT = 180


def fail(message: str, code: int = 1) -> "NoReturn":
    print(f"Error: {message}", file=sys.stderr)
    raise SystemExit(code)


def default_codex_dir() -> Path:
    configured = os.environ.get("CODEX_HOME")
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".codex"


def read_auth_key(codex_dir: Path) -> str:
    env_key = os.environ.get("OPENAI_API_KEY")
    if env_key:
        return env_key.strip()

    auth_path = codex_dir / "auth.json"
    if not auth_path.exists():
        fail(f"未找到 API 密钥文件：{auth_path}")
    try:
        payload = json.loads(auth_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"无法读取密钥文件 {auth_path}：{exc}")

    key = payload.get("OPENAI_API_KEY")
    if not isinstance(key, str) or not key.strip():
        fail(f"{auth_path} 中没有有效的 OPENAI_API_KEY")
    return key.strip()


def read_base_url(codex_dir: Path) -> str:
    env_url = os.environ.get("OPENAI_BASE_URL")
    if env_url:
        return env_url.strip().rstrip("/")

    config_path = codex_dir / "config.toml"
    if config_path.exists():
        try:
            import tomllib

            config = tomllib.loads(config_path.read_text(encoding="utf-8"))
            provider_name = config.get("model_provider")
            providers = config.get("model_providers", {})
            provider = providers.get(provider_name, {}) if provider_name else {}
            base_url = provider.get("base_url")
            if isinstance(base_url, str) and base_url.strip():
                return base_url.strip().rstrip("/")
        except (OSError, UnicodeError, ValueError) as exc:
            fail(f"无法解析配置文件 {config_path}：{exc}")

    return "https://api.openai.com/v1"


def endpoint_for(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    if normalized.endswith("/images/generations"):
        return normalized
    return f"{normalized}/images/generations"


def read_prompt(args: argparse.Namespace) -> str:
    if bool(args.prompt) == bool(args.prompt_file):
        fail("必须且只能提供 --prompt 或 --prompt-file")
    if args.prompt_file:
        prompt_path = Path(args.prompt_file)
        if not prompt_path.exists():
            fail(f"提示词文件不存在：{prompt_path}")
        try:
            prompt = prompt_path.read_text(encoding="utf-8")
        except OSError as exc:
            fail(f"无法读取提示词文件 {prompt_path}：{exc}")
    else:
        prompt = args.prompt
    prompt = prompt.strip()
    if not prompt:
        fail("提示词不能为空")
    return prompt


def build_payload(args: argparse.Namespace, prompt: str) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": args.model,
        "prompt": prompt,
        "n": args.n,
        "size": args.size,
        "quality": args.quality,
        "output_format": args.output_format,
    }
    if args.background:
        payload["background"] = args.background
    return payload


def request_json(endpoint: str, key: str, payload: dict[str, Any]) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        endpoint,
        data=body,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=DEFAULT_TIMEOUT) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace").strip()
        if len(detail) > 1200:
            detail = detail[:1200] + "..."
        fail(f"图片 API 返回 HTTP {exc.code}：{detail}")
    except urllib.error.URLError as exc:
        fail(f"无法连接图片 API：{exc.reason}")
    except TimeoutError:
        fail("图片 API 请求超时")

    try:
        result = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        fail(f"图片 API 返回的不是有效 JSON：{exc}")

    if not isinstance(result, dict):
        fail("图片 API 返回格式不是 JSON 对象")
    return result


def output_paths(out: Path, count: int, fmt: str) -> list[Path]:
    suffix = "." + ("jpg" if fmt == "jpeg" else fmt)
    if out.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
        out = out.with_suffix(suffix)
    if count == 1:
        return [out]
    return [
        out.with_name(f"{out.stem}-{index}{out.suffix}")
        for index in range(1, count + 1)
    ]


def decode_item(item: Any) -> bytes | None:
    if not isinstance(item, dict):
        return None
    encoded = item.get("b64_json") or item.get("base64") or item.get("image")
    if isinstance(encoded, str) and encoded:
        try:
            return base64.b64decode(encoded)
        except (ValueError, base64.binascii.Error):
            fail("图片 API 返回了无法解码的 base64 图片")
    url = item.get("url")
    if isinstance(url, str) and url.startswith(("http://", "https://")):
        try:
            with urllib.request.urlopen(url, timeout=DEFAULT_TIMEOUT) as response:
                return response.read()
        except (urllib.error.URLError, TimeoutError) as exc:
            fail(f"无法下载图片结果：{exc}")
    return None


def save_images(result: dict[str, Any], paths: list[Path], force: bool) -> int:
    data = result.get("data") or result.get("images")
    if not isinstance(data, list) or not data:
        fail("图片 API 返回中没有 data/images 图片结果")

    saved = 0
    for index, item in enumerate(data):
        if index >= len(paths):
            break
        image_bytes = decode_item(item)
        if image_bytes is None:
            continue
        path = paths[index]
        if path.exists() and not force:
            fail(f"输出文件已存在：{path}（如需覆盖请加 --force）")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(image_bytes)
        print(f"Wrote {path}")
        saved += 1

    if saved == 0:
        fail("图片 API 返回了结果，但没有可保存的图片数据")
    return saved


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="使用 Codex 配置的 API 生成图片")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--prompt", help="直接传入提示词")
    source.add_argument("--prompt-file", help="从 UTF-8 文本文件读取提示词")
    parser.add_argument("--codex-dir", type=Path, default=default_codex_dir())
    parser.add_argument("--base-url", help="临时覆盖配置中的 API base URL")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--size", default=DEFAULT_SIZE)
    parser.add_argument("--quality", default=DEFAULT_QUALITY)
    parser.add_argument("--background", choices=("transparent", "opaque", "auto"))
    parser.add_argument("--output-format", choices=("png", "jpeg", "webp"), default=DEFAULT_OUTPUT_FORMAT)
    parser.add_argument("--n", type=int, default=1)
    parser.add_argument("--out", type=Path, default=Path("outputs/imagegen/generated.png"))
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.n < 1 or args.n > 10:
        fail("--n 必须在 1 到 10 之间")
    if args.background == "transparent" and args.output_format not in {"png", "webp"}:
        fail("透明背景只能使用 PNG 或 WebP")
    return args


def main() -> int:
    args = parse_args()
    prompt = read_prompt(args)
    payload = build_payload(args, prompt)
    base_url = args.base_url.rstrip("/") if args.base_url else read_base_url(args.codex_dir)
    endpoint = endpoint_for(base_url)
    paths = output_paths(args.out, args.n, args.output_format)

    if args.dry_run:
        print(json.dumps({"endpoint": endpoint, "outputs": [str(p) for p in paths], **payload}, ensure_ascii=False, indent=2))
        return 0

    key = read_auth_key(args.codex_dir)
    result = request_json(endpoint, key, payload)
    save_images(result, paths, args.force)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

