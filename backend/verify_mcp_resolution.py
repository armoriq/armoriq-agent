import sys
import os
import uuid
from typing import Optional

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.mcp_manager import MCPManager
from app.models import MCPConfig

class MockConfig:
    def __init__(self, id, name, url):
        self.id = id
        self.name = name
        self.url = url

def test_mcp_resolution():
    manager = MCPManager()

    # Mock data
    mcp_id = uuid.uuid4()
    short_id = str(mcp_id).replace('-', '')[:8]
    mcp_url = "https://loan-server.armoriq.io/mcp"
    mcp_name = "ArmorIQ Loan Server"

    print(f"Testing resolution for:")
    print(f"  ID: {mcp_id}")
    print(f"  Short ID: {short_id}")
    print(f"  URL: {mcp_url}")
    print(f"  Name: {mcp_name}")

    # Create a mock connection/config
    config = MockConfig(id=mcp_id, name=mcp_name, url=mcp_url)
    class MockConnection:
        def __init__(self, cfg):
            self.config = cfg

    manager.connections[str(mcp_id)] = MockConnection(config)

    # Test resolution
    resolved_name = manager.get_mcp_name_by_short_id(short_id)
    resolved_url = manager.get_mcp_url_by_short_id(short_id)

    print(f"\nResults:")
    print(f"  Resolved Name: {resolved_name}")
    print(f"  Resolved URL: {resolved_url}")

    assert resolved_name == mcp_name, f"Expected {mcp_name}, got {resolved_name}"
    assert resolved_url == "loan-server.armoriq.io/mcp", f"Expected loan-server.armoriq.io/mcp, got {resolved_url}"

    print("\n✓ SUCCESS: MCP resolution logic works as expected.")

if __name__ == "__main__":
    test_mcp_resolution()
