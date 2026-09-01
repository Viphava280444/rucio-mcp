"""Tool bodies must run off the event loop.

FastMCP runs a plain ``def`` tool inline on the event loop. One slow
Rucio HTTP call then blocks every other request: other tools, the
liveness probe, and the gateway's health check. On 2026-09-01 a 219 s
``rucio_list_did_rule_history`` call made the gateway mark this server
unhealthy and drop all 34 tools for 2 minutes.
"""

from __future__ import annotations

import asyncio
import time

from rucio_mcp import server


def test_slow_tool_does_not_block_other_tools(monkeypatch) -> None:
    def slow_ping():
        time.sleep(0.5)
        return {"status": "ok", "data": {"version": "slow"}}

    monkeypatch.setattr(server.service, "ping", slow_ping)

    async def two_calls_at_once() -> float:
        t0 = time.monotonic()
        await asyncio.gather(
            server.mcp.call_tool("rucio_ping", {}),
            server.mcp.call_tool("rucio_ping", {}),
        )
        return time.monotonic() - t0

    elapsed = asyncio.run(two_calls_at_once())
    # Serial execution takes 1.0 s; threads take about 0.5 s.
    assert elapsed < 0.9, f"two 0.5 s calls took {elapsed:.2f} s: tools run on the loop"


def test_tool_schema_survives_wrapping() -> None:
    tool = server.mcp._tool_manager.get_tool("rucio_get_did")
    assert tool is not None
    props = tool.parameters["properties"]
    assert set(props) == {"scope", "name", "dynamic_depth"}
    assert tool.description.startswith("Get a single DID")
