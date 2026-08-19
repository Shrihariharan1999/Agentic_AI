import asyncio
from services.mcp_service import shutdown_manager

async def main():
    await shutdown_manager()
    print("shutdown-ok")

asyncio.run(main())
