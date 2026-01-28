import asyncio
import logging
import sys
import os

# Add parent directory to path so we can import 'app'
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.mcp_manager import DirectMCPClient

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def verify_connection():
    url = "https://loan-server.armoriq.io/mcp"
    logger.info(f"Connecting to {url}...")

    try:
        async with DirectMCPClient(url) as client:
            # Initialize
            logger.info("Initializing...")
            init_result = await client.initialize()
            logger.info(f"Initialized. Server Info: {init_result.get('serverInfo')}")

            # List tools
            logger.info("Listing tools...")
            tools = await client.list_tools()
            logger.info(f"Found {len(tools)} tools:")
            for tool in tools:
                logger.info(f"- {tool.get('name')}: {tool.get('description')}")

            logger.info("Verification SUCCESS")

    except Exception as e:
        logger.error(f"Verification FAILED: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(verify_connection())
