import asyncio
import logging
import sys
import os
from unittest.mock import MagicMock

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from armoriq_sdk import ArmorIQClient
from armoriq_sdk.models import IntentToken

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_intent_token_behavior():
    # Create a dummy token
    token = IntentToken(
        token_id="test_token",
        token="test_jwt_string",
        expires_at=1234567890,
        policy={}
    )

    logger.info(f"Token type: {type(token)}")
    logger.info(f"Token attributes: {token.token_id}")

    try:
        logger.info("Attempting subscript access token['token_id']...")
        print(token['token_id'])
    except TypeError as e:
        logger.error(f"Caught expected error: {e}")
    except Exception as e:
        logger.error(f"Caught unexpected error: {e}")

    # Now let's try to simulate invoke if possible, or check SDK code if we could (we can't easily)
    # But we can check if ArmorIQClient.invoke expects dict or object
    try:
        # Mock client to test invoke parameters
        client = ArmorIQClient(api_key="test", user_id="u1", agent_id="a1")
        # We can't really call invoke without real backend easily, but we can check usage if we had the code.
        # Since we can't see SDK code, we rely on this test confirming that IntentToken IS NOT subscriptable.
        pass
    except Exception as e:
        logger.error(f"Client init error: {e}")

if __name__ == "__main__":
    test_intent_token_behavior()
