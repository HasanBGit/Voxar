"""Talk to `voxar mcp` the way an AI agent's host would: launch it over stdio and call a tool.

    uv run python examples/06_mcp_client.py sample.wav

Needs the mcp extra. The server may only touch files inside --allow-dir, so this passes the
audio file's own folder. (A real MCP host does the same with a config entry; see the README.)
"""

import asyncio
import os
import sys
from pathlib import Path

from mcp import Client
from mcp.client.stdio import StdioServerParameters


async def main(audio: Path) -> None:
    server = StdioServerParameters(
        command=sys.executable,
        args=["-m", "voxar", "mcp", "--allow-dir", str(audio.parent.resolve())],
        env=dict(os.environ),
    )
    async with Client(server) as client:
        tools = await client.list_tools()
        print("tools:", ", ".join(sorted(tool.name for tool in tools.tools)))
        result = await client.call_tool("transcribe_file", {"path": str(audio.resolve())})
        print("error" if result.is_error else "text:", result.structured_content or result.content)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    asyncio.run(main(Path(sys.argv[1])))
