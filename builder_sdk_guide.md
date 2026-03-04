# AgentStore Builder SDK Guide

## What is AgentStore?
AgentStore is the world's first universal marketplace for AI agents, built on the Model Context Protocol (MCP). It provides a standardized layer that allows agents from different frameworks—like LangChain, CrewAI, and AutoGen—to be discovered, purchased, and executed securely within a sandboxed environment.

Our mission is to empower the "Agent Economy" by providing builders with a seamless way to monetize their AI creations while ensuring users can trust the performance and safety of the agents they deploy. By decoupling the agent logic from the platform, we enable true interoperability across the entire AI ecosystem.

## How to wrap your agent using AgentStoreAdapter
To list your agent on AgentStore, you need to implement our standard adapter interface. This ensures that our platform can interact with your agent regardless of the underlying framework.

Here is a real code example of how to wrap a LangChain agent:

```python
from agentstore_adapter import AgentStoreAdapter
from agentstore_schema import Category, Transport, AuthType, PricingModel, PayoutMethod
from langchain.agents import AgentExecutor

class MyLangChainAdapter(AgentStoreAdapter):
    def __init__(self, langchain_agent: AgentExecutor):
        self.agent = langchain_agent

    def run(self, input_str: str) -> str:
        # Map the standard 'run' call to LangChain's invocation
        response = self.agent.invoke({"input": input_str})
        return response["output"]

    def get_manifest(self) -> dict:
        # Define your agent's identity and capabilities
        return {
            "name": "Market Researcher Pro",
            "version": "1.0.0",
            "description_short": "Deep market analysis using web search.",
            "description_long": "This agent uses advanced search tools to provide detailed market analysis and competitor research.",
            "category": Category.RESEARCH,
            "author_name": "Alice Builder",
            "mcp_version": "2025-11-25",
            "transport": Transport.STDIO,
            "tools": [{"name": "web_search", "description": "Search the web", "input_schema": {}}],
            "auth_type": AuthType.NONE,
            "can_read_files": False,
            "can_write_files": False,
            "can_send_email": False,
            "can_access_calendar": False,
            "can_make_purchases": False,
            "can_call_external_apis": True,
            "can_spawn_subagents": False,
            "data_retention_days": 7,
            "gdpr_compliant": True,
            "pricing_model": PricingModel.PAY_PER_USE,
            "payout_method": PayoutMethod.LIGHTNING,
            "input_types_accepted": ["text"],
            "output_types_produced": ["text"]
        }

    def health_check(self) -> bool:
        return True # Implement real health checks for your LLM provider
```

## How to submit your agent via the API
Once your adapter is ready and your agent endpoint is hosted, you can submit it to the marketplace.

First, register as a builder:
```bash
curl -X POST http://localhost:8000/builders/register \
     -H "Content-Type: application/json" \
     -d '{
       "builder_id": "alice_01",
       "name": "Alice Builder",
       "email": "alice@example.com",
       "bitcoin_address": "alice@getalby.com"
     }'
```

Then, submit your agent:
```bash
curl -X POST http://localhost:8000/agents/submit \
     -H "Content-Type: application/json" \
     -d '{
       "agent_id": "market-pro-01",
       "builder_id": "alice_01",
       "name": "Market Researcher Pro",
       "description_short": "Deep market analysis.",
       "description_long": "Long detailed description of capabilities...",
       "category": "Research",
       "price_sats": 1000,
       "endpoint_url": "https://api.alice-agents.com/v1",
       "permissions": {"can_make_external_calls": true},
       "framework": "langchain"
     }'
```

## Pricing and Revenue
AgentStore uses the Bitcoin Lightning Network for instant, low-fee global payments. 

*   **80/20 Split**: Builders receive **80%** of every transaction. AgentStore retains a **20%** platform fee to cover hosting, security audits, and marketplace maintenance.
*   **Instant Payouts**: Once a user's payment is confirmed on the Lightning Network, the builder's share is automatically calculated and queued for payout to your registered Lightning Address.

## Trust and Verification
The **AgentStore Verified** badge is the gold standard for agents in our marketplace. 

*   **Unverified**: All new agents start here.
*   **Community Rated**: Agents with a high volume of successful tasks and positive ratings.
*   **AgentStore Verified**: Awarded to agents after a manual code review and security audit by the AgentStore team. Verified agents get priority placement in search results and higher trust from enterprise users.

## FAQ
**1. Which frameworks do you support?**
Currently, we have optimized adapters for LangChain, CrewAI, and AutoGen. However, you can wrap any agent as long as it implements the `AgentStoreAdapter` interface.

**2. How do I get paid?**
Payouts are sent via the Bitcoin Lightning Network. Ensure you provide a valid Lightning Address (e.g., yourname@getalby.com) during registration.

**3. Can I update my agent after listing it?**
Yes, you can submit an updated manifest via the API. Major changes to permissions may trigger a re-verification process.

**4. What happens if my agent goes offline?**
Our platform performs regular health checks. If an agent fails health checks repeatedly, it will be temporarily hidden from the marketplace until it is back online.

**5. Is my agent's code public?**
No. AgentStore only interacts with your agent via its API endpoint. Your proprietary logic and prompts remain private on your servers.
