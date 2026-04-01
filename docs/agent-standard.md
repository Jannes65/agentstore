# AgentStore Universal Agent Standard v0.1

AgentStore is built on the **Model Context Protocol (MCP)**, a vendor-neutral open standard for AI agents. To list an agent on AgentStore, it must adhere to our Universal Agent Standard.

## 1. Core Principles
- **Interoperability**: Agents must be framework-agnostic (LangChain, CrewAI, AutoGen, etc.).
- **Security**: All agents undergo mandatory automated checks and optional manual reviews for the **Verified** badge.
- **Transparency**: Permissions and pricing must be explicitly declared in the agent manifest.
- **Monetization**: Native support for Bitcoin Lightning Network payments.

## 2. Agent Manifest (Schema)
Every agent must provide a manifest that follows our [Pydantic schema](agentstore_schema.py). Key sections include:

### Identity
- `name`: 1-60 characters.
- `version`: Semantic versioning (e.g., `1.0.0`).
- `category`: Productivity, Developer Tools, Sales & CRM, Finance, etc.
- `author_name`: The individual or company behind the agent.

### MCP Configuration
- `mcp_version`: The MCP spec version (e.g., `2025-11-25`).
- `transport`: `STDIO` or `HTTP+SSE`.
- `tools`: A list of capabilities (name, description, input/output JSON schema).
- `auth_type`: `None`, `API Key`, `OAuth2`, or `AgentStore Token`.

### Permissions
Builders must explicitly declare if an agent can:
- Read/Write files
- Send emails
- Access calendars
- Make purchases (requires billable pricing model)
- Call external APIs
- Spawn sub-agents

### Pricing & Payouts
- **Models**: `free`, `pay_per_use`, `subscription`, or `tiered`.
- **Payouts**: Supports `bitcoin_lightning` (via Lightning Address) and `fiat_bank`.
- **Currency**: Default is `USD` (converted to Sats at runtime) or `BTC`.

## 3. Implementation (Adapters)
To wrap your existing agent, implement the `AgentStoreAdapter` interface:

```python
class AgentStoreAdapter(ABC):
    @abstractmethod
    def run(self, input_str: str) -> str:
        """Execute agent logic and return string response"""
        pass

    @abstractmethod
    def get_manifest(self) -> dict:
        """Return the manifest matching AgentSchema"""
        pass

    @abstractmethod
    def health_check(self) -> bool:
        """Return True if agent service is operational"""
        pass
```

## 4. Compliance
- **GDPR**: All agents must be GDPR compliant.
- **Data Retention**: Builders must specify how many days data is retained.
- **Verified Badge**: Requires manual code review and security audit. Verified agents receive priority placement and higher trust scores.
