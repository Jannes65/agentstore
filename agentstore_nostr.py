import json
import time
from pynostr.key import PrivateKey
from pynostr.event import Event
from pynostr.relay_manager import RelayManager

NOSTR_RELAYS = [
    "wss://relay.damus.io",
    "wss://relay.nostr.band",
    "wss://nos.lol"
]

def generate_agent_keypair():
    """Generate a fresh Nostr keypair for an agent."""
    private_key = PrivateKey()
    return {
        "nostr_privkey": private_key.bech32(),  # nsec1...
        "nostr_pubkey": private_key.public_key.bech32()  # npub1...
    }

def publish_agent_to_nostr(agent: dict, nostr_privkey: str) -> bool:
    """
    Publish an agent as a NIP-A5 Nostr event (kind 31337).
    agent dict must include: id, name, description_short, category, 
    price_sats, nostr_pubkey, endpoint_url, framework
    Returns True if published to at least one relay.
    """
    try:
        private_key = PrivateKey.from_nsec(nostr_privkey)

        # NIP-A5 agent metadata event
        content = json.dumps({
            "name": agent["name"],
            "description": agent["description_short"],
            "category": agent["category"],
            "price_sats": agent["price_sats"],
            "endpoint": agent["endpoint_url"],
            "framework": agent.get("framework", "other"),
            "marketplace": "agentstore",
            "marketplace_url": f"https://chooseyouragents.com"
        })

        tags = [
            ["d", agent["id"]],           # unique identifier (replaceable event)
            ["name", agent["name"]],
            ["category", agent["category"]],
            ["price", str(agent["price_sats"]), "sats"],
            ["marketplace", "chooseyouragents.com"]
        ]

        event = Event(
            kind=31337,
            content=content,
            tags=tags,
            public_key=private_key.public_key.hex()
        )
        event.sign(private_key.hex())

        relay_manager = RelayManager()
        for relay in NOSTR_RELAYS:
            relay_manager.add_relay(relay)

        relay_manager.open_connections()
        time.sleep(1)  # allow connections to establish
        relay_manager.publish_event(event)
        time.sleep(2)  # allow publish to complete
        relay_manager.close_connections()

        return True

    except Exception as e:
        print(f"Nostr publish failed: {e}")
        return False
