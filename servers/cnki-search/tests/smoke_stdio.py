"""End-to-end check: drive the local CNKI MCP server over stdio."""
import asyncio
import json
import sys

sys.stdout.reconfigure(encoding="utf-8")

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SERVER = StdioServerParameters(
    command=sys.executable,
    args=["-m", "cnki_scholar"],
)


async def main() -> None:
    async with stdio_client(SERVER) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            print("TOOLS:", [t.name for t in tools.tools])

            res = await session.call_tool("search", {"query": "深度学习", "kind": "all"})
            payload = res.structuredContent or {}
            print("STATUS:", payload.get("status"), "COUNT:", payload.get("returned_count"))
            print("WARNINGS:", payload.get("warnings"))
            for rec in (payload.get("records") or [])[:4]:
                print("  ---")
                print("  title   :", rec.get("title"))
                print("  url     :", rec.get("url"))
                print("  dbcode  :", rec.get("dbcode"), "| filename:", rec.get("filename"))
                print("  space   :", rec.get("space_url"))
                print("  meta    :", rec.get("authors"), rec.get("year"), rec.get("venue"), rec.get("kind"))

            first = (payload.get("records") or [None])[0]
            if first:
                for label, target in (("kns", first.get("url")), ("space", first.get("space_url"))):
                    det = await session.call_tool("get_record", {"url": target})
                    body = det.structuredContent or {}
                    print(f"\nGET_RECORD[{label}] status={body.get('status')} url={body.get('url')}")
                    print("   title:", (body.get("title") or "")[:70])
                    print("   abstract:", (body.get("abstract") or "")[:90])
                    print("   error:", body.get("error"))


asyncio.run(main())
