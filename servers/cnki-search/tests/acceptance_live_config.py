"""Final acceptance, run with the live patch config.

Two environment variables adjust how the server is reached, both for local
verification only:

* ``CNKI_ACCEPTANCE_TARGET`` — shell-style command overriding the launch command
  read from the profile patch. Use it to drive the already-installed venv
  directly while the DSH host holds the project venv open, which makes ``uv run``
  fail when it tries to reinstall the package::

      $env:CNKI_ACCEPTANCE_TARGET = '"C:\\Users\\LiYang\\.dsh\\cnki-kns\\.venv\\Scripts\\python.exe" -m cnki_scholar'

* ``CNKI_ACCEPTANCE_UV_CACHE`` — writable uv cache dir injected into the child,
  for environments where the ambient uv cache is not writable.
"""
import asyncio
import os
import re
import shlex
import sys

import yaml

sys.stdout.reconfigure(encoding="utf-8")

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

PATCH = r"C:\Users\LiYang\.dsh\profiles\desktop\cordis.patch.yml"
KNS_RE = re.compile(
    r"^https://kns\.cnki\.net/kcms/detail/detail\.aspx\?dbcode=[A-Z]{4}&filename=[\w.\-]+$"
)


class Loader(yaml.SafeLoader):
    pass


def _unknown(loader, tag_suffix, node):
    if isinstance(node, yaml.ScalarNode):
        return loader.construct_scalar(node)
    if isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node)
    return loader.construct_mapping(node)


Loader.add_multi_constructor("", _unknown)


def cnki_config():
    doc = yaml.load(open(PATCH, encoding="utf-8"), Loader=Loader)

    def walk(node):
        if isinstance(node, dict):
            if node.get("id") == "mcp-cnki":
                yield node["config"]
            for value in node.values():
                yield from walk(value)
        elif isinstance(node, list):
            for item in node:
                yield from walk(item)

    return next(walk(doc))


def structured(result):
    """Read structured output across MCP SDK naming (new/old attribute)."""
    value = getattr(result, "structured_content", None)
    if value is None:
        value = getattr(result, "structuredContent", None)
    return value or {}


async def main() -> int:
    cfg = cnki_config()
    override = os.environ.get("CNKI_ACCEPTANCE_TARGET")
    if override:
        parts = shlex.split(override, posix=False)
        command, args = parts[0].strip('"'), [p.strip('"') for p in parts[1:]]
        source = "CNKI_ACCEPTANCE_TARGET override"
    else:
        command, args = cfg["command"], list(cfg["args"])
        source = "live profile patch"
    cache = os.environ.get("CNKI_ACCEPTANCE_UV_CACHE")
    env = {"UV_CACHE_DIR": cache} if cache else None
    params = StdioServerParameters(command=command, args=args, env=env)
    print(f"launch source: {source}")
    print("launching:", params.command, params.args)

    failures = []
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = [t.name for t in (await session.list_tools()).tools]
            print("tools:", tools)
            if sorted(tools) != ["get_record", "search"]:
                failures.append(f"unexpected tools: {tools}")

            res = await session.call_tool("search", {"query": "深度学习", "kind": "all"})
            payload = structured(res)
            records = payload.get("records") or []
            print(
                f"status={payload.get('status')} records={len(records)} "
                f"warnings={payload.get('warnings')}"
            )
            if payload.get("status") != "ok" or not records:
                failures.append("search returned no records")
            if payload.get("warnings"):
                failures.append(f"unmapped links: {payload['warnings']}")

            space_leaks = []
            for rec in records:
                url = rec.get("url") or ""
                if not KNS_RE.match(url):
                    failures.append(f"non-conforming url: {url}")
                if "cnki.com.cn" in url or "search.cnki" in url:
                    space_leaks.append(url)
                if not rec.get("dbcode") or not rec.get("filename"):
                    failures.append(f"missing dbcode/filename for {rec.get('title')}")

            print("space links leaked into url field:", space_leaks or "none")
            print("record[0] url:", records[0].get("url"))
            print("record[0] space_url kept separately:", records[0].get("space_url"))

            det = await session.call_tool("get_record", {"url": records[0]["url"]})
            body = structured(det)
            print(
                "get_record on main-site link:",
                body.get("status"),
                "|",
                (body.get("title") or "")[:50],
            )
            if body.get("status") != "ok":
                failures.append(f"get_record failed: {body.get('error')}")
            if not KNS_RE.match(body.get("url") or ""):
                failures.append(f"get_record url not main-site: {body.get('url')}")

    print("\n=== RESULT ===")
    if failures:
        for item in failures:
            print("FAIL:", item)
        return 1
    print("PASS: every CNKI record carries a kns.cnki.net main-site link")
    return 0


sys.exit(asyncio.run(main()))

