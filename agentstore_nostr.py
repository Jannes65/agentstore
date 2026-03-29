from pynostr.key import PrivateKey

def generate_agent_keypair():
    """Generate a fresh Nostr keypair for an agent."""
    private_key = PrivateKey()
    return {
        "nostr_privkey": private_key.bech32(),  # nsec1...
        "nostr_pubkey": private_key.public_key.bech32()  # npub1...
    }
