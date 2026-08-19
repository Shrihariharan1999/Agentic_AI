from mcp_client.manager import MCPManager

_manager = None
_tools_cache = None


async def get_tools():
    global _manager, _tools_cache

    if _manager is None:
        _manager = MCPManager()
        await _manager.connect()

    if _tools_cache is None:
        _tools_cache = await _manager.load_tools()

    return _tools_cache


async def reset_tools():
    global _manager, _tools_cache

    if _manager is not None:
        await _manager.disconnect()

    _manager = None
    _tools_cache = None