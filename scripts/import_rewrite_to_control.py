#!/usr/bin/env python3
"""Import rewrite JSON and local images into xianyu-control."""

from __future__ import annotations

import argparse
import json
import mimetypes
from pathlib import Path
import secrets
import urllib.error
import urllib.request
from urllib.parse import urlsplit, urlunsplit


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def fail(message: str) -> None:
    raise SystemExit(f"Error: {message}")


def runtime_control_url(value: str) -> str:
    """A Docker task reaches the Windows host through its Docker DNS name."""
    parsed = urlsplit(value)
    if Path("/.dockerenv").exists() and parsed.hostname in {"127.0.0.1", "localhost"}:
        host = "host.docker.internal"
        if parsed.port:
            host += f":{parsed.port}"
        return urlunsplit(parsed._replace(netloc=host))
    return value


def make_multipart(payload: dict, files: list[tuple[str, str, str, bytes]]):
    boundary = "----rewrite-" + secrets.token_hex(12)
    parts = []
    parts.append(
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"payload\"\r\n\r\n"
        + json.dumps(payload, ensure_ascii=False)
        + "\r\n"
    )
    for field, filename, media_type, content in files:
        header = (
            f"--{boundary}\r\n"
            f"Content-Disposition: form-data; name=\"{field}\"; filename=\"{filename}\"\r\n"
            f"Content-Type: {media_type}\r\n\r\n"
        ).encode("utf-8")
        parts.append(header + content + b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode("utf-8"))
    body = b"".join(
        item.encode("utf-8") if isinstance(item, str) else item for item in parts
    )
    return body, f"multipart/form-data; boundary={boundary}"


def main() -> int:
    parser = argparse.ArgumentParser(description="导入 rewrite 结果到商品包")
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--control-url")
    parser.add_argument("--token")
    parser.add_argument("--candidate-id", type=int)
    args = parser.parse_args()
    env = load_env(Path(__file__).resolve().parents[1] / ".env")
    control_url = args.control_url or env.get("CONTROL_BASE_URL")
    token = args.token or env.get("CONTROL_TOKEN")
    if not control_url:
        fail("请在 .env 设置 CONTROL_BASE_URL，或通过 --control-url 指定")
    if not token:
        fail("请在 .env 设置 CONTROL_TOKEN，或通过 --token 指定")
    try:
        result = json.loads(args.result.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"无法读取 result JSON：{exc}")
    candidate_id = args.candidate_id or result.get("candidate_id")
    if not isinstance(candidate_id, int):
        fail("请提供 candidate_id")
    for key in ("title", "description"):
        if not isinstance(result.get(key), str) or not result[key].strip():
            fail(f"result JSON 缺少有效的 {key}")

    payload = {
        key: result[key]
        for key in (
            "title",
            "description",
            "source_observation_id",
            "rewrite_run_id",
            "metadata",
        )
        if key in result
    }
    payload["images"] = []
    files = []
    for image in result.get("images") or []:
        if not isinstance(image, dict):
            payload["images"].append(image)
            continue
        local = image.get("path") or image.get("local_path")
        if not local:
            payload["images"].append(image)
            continue
        path = Path(local)
        if not path.is_absolute():
            path = args.result.parent / path
        if not path.is_file():
            fail(f"图片文件不存在：{path}")
        filename = path.name
        payload["images"].append(
            {
                "file_name": filename,
                "selected": image.get("selected", True),
                "kind": image.get("kind", "generated_poster"),
            }
        )
        files.append(
            (
                "files",
                filename,
                mimetypes.guess_type(filename)[0] or "application/octet-stream",
                path.read_bytes(),
            )
        )

    body, content_type = make_multipart(payload, files)
    url = runtime_control_url(control_url).rstrip("/") + (
        f"/api/selection/candidates/{candidate_id}/package/import-rewrite"
    )
    request = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": "Bearer " + token,
            "Content-Type": content_type,
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            print(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        fail(f"control 返回 HTTP {exc.code}：{exc.read().decode(errors='replace')[:1000]}")
    except urllib.error.URLError as exc:
        fail(f"无法连接 control：{exc.reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
