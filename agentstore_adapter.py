from abc import ABC, abstractmethod
from typing import Dict, Optional
from agentstore_schema import AgentSchema, Category, Transport, AuthType, PricingModel, PayoutMethod

class AgentStoreAdapter(ABC):
    """Base class for AgentStore adapters."""

    @abstractmethod
    def run(self, input_str: str) -> str:
        """Run the agent with the given input string and return the response."""
        pass

    @abstractmethod
    def get_manifest(self) -> dict:
        """Return the manifest/schema for this agent as a dictionary."""
        pass

    @abstractmethod
    def health_check(self) -> bool:
        """Check if the underlying agent service is healthy."""
        pass

class LangChainAdapter(AgentStoreAdapter):
    """Adapter for LangChain framework agents."""

    def run(self, input_str: str) -> str:
        # Real framework call: response = langchain_agent.invoke({"input": input_str})
        # return response["output"]
        return f"LangChain received: {input_str}"

    def get_manifest(self) -> dict:
        # Real framework call: Convert LangChain agent properties to AgentSchema
        return {
            "name": "LangChain Agent",
            "version": "1.0.0",
            "description_short": "A dummy LangChain agent for testing.",
            "description_long": "This is a detailed description of a dummy LangChain agent that follows the AgentStore schema.",
            "category": Category.PRODUCTIVITY,
            "author_name": "Junie",
            "mcp_version": "2025-11-25",
            "transport": Transport.STDIO,
            "tools": [{"name": "test_tool", "description": "A tool for testing", "input_schema": {}}],
            "auth_type": AuthType.NONE,
            "can_read_files": False,
            "can_write_files": False,
            "can_send_email": False,
            "can_access_calendar": False,
            "can_make_purchases": False,
            "can_call_external_apis": False,
            "can_spawn_subagents": False,
            "data_retention_days": 0,
            "gdpr_compliant": True,
            "pricing_model": PricingModel.FREE,
            "payout_method": PayoutMethod.FIAT,
            "input_types_accepted": ["text"],
            "output_types_produced": ["text"]
        }

    def health_check(self) -> bool:
        # Real framework call: Check if LangChain components (LLM, tools) are reachable
        return True

class CrewAIAdapter(AgentStoreAdapter):
    """Adapter for CrewAI framework agents."""

    def run(self, input_str: str) -> str:
        # Real framework call: response = crew.kickoff(inputs={"topic": input_str})
        # return str(response)
        return f"CrewAI received: {input_str}"

    def get_manifest(self) -> dict:
        # Real framework call: Convert CrewAI crew/agent properties to AgentSchema
        return {
            "name": "CrewAI Agent",
            "version": "1.0.0",
            "description_short": "A dummy CrewAI agent for testing.",
            "description_long": "This is a detailed description of a dummy CrewAI agent that follows the AgentStore schema.",
            "category": Category.PRODUCTIVITY,
            "author_name": "Junie",
            "mcp_version": "2025-11-25",
            "transport": Transport.STDIO,
            "tools": [{"name": "test_tool", "description": "A tool for testing", "input_schema": {}}],
            "auth_type": AuthType.NONE,
            "can_read_files": False,
            "can_write_files": False,
            "can_send_email": False,
            "can_access_calendar": False,
            "can_make_purchases": False,
            "can_call_external_apis": False,
            "can_spawn_subagents": False,
            "data_retention_days": 0,
            "gdpr_compliant": True,
            "pricing_model": PricingModel.FREE,
            "payout_method": PayoutMethod.FIAT,
            "input_types_accepted": ["text"],
            "output_types_produced": ["text"]
        }

    def health_check(self) -> bool:
        # Real framework call: Check if CrewAI agents and their LLMs are reachable
        return True

class AutoGenAdapter(AgentStoreAdapter):
    """Adapter for AutoGen framework agents."""

    def run(self, input_str: str) -> str:
        # Real framework call: user_proxy.initiate_chat(assistant, message=input_str)
        # return last_message["content"]
        return f"AutoGen received: {input_str}"

    def get_manifest(self) -> dict:
        # Real framework call: Convert AutoGen agent properties to AgentSchema
        return {
            "name": "AutoGen Agent",
            "version": "1.0.0",
            "description_short": "A dummy AutoGen agent for testing.",
            "description_long": "This is a detailed description of a dummy AutoGen agent that follows the AgentStore schema.",
            "category": Category.PRODUCTIVITY,
            "author_name": "Junie",
            "mcp_version": "2025-11-25",
            "transport": Transport.STDIO,
            "tools": [{"name": "test_tool", "description": "A tool for testing", "input_schema": {}}],
            "auth_type": AuthType.NONE,
            "can_read_files": False,
            "can_write_files": False,
            "can_send_email": False,
            "can_access_calendar": False,
            "can_make_purchases": False,
            "can_call_external_apis": False,
            "can_spawn_subagents": False,
            "data_retention_days": 0,
            "gdpr_compliant": True,
            "pricing_model": PricingModel.FREE,
            "payout_method": PayoutMethod.FIAT,
            "input_types_accepted": ["text"],
            "output_types_produced": ["text"]
        }

    def health_check(self) -> bool:
        # Real framework call: Check if AutoGen agents and their LLM configurations are valid
        return True

class AdapterRegistry:
    """Registry for managing and retrieving agent adapters."""

    def __init__(self):
        self._adapters: Dict[str, AgentStoreAdapter] = {}

    def register(self, agent_id: str, adapter: AgentStoreAdapter):
        """Register a new adapter with the given agent_id."""
        self._adapters[agent_id] = adapter

    def get(self, agent_id: str) -> Optional[AgentStoreAdapter]:
        """Retrieve an adapter by its agent_id."""
        return self._adapters.get(agent_id)

if __name__ == "__main__":
    registry = AdapterRegistry()
    
    # Register a dummy LangChain adapter
    langchain_adapter = LangChainAdapter()
    registry.register("langchain_001", langchain_adapter)
    
    # Retrieve and call run
    adapter = registry.get("langchain_001")
    if adapter:
        result = adapter.run("test input")
        print(f"Result: {result}")
        
        # Optionally verify the manifest matches the schema
        manifest_data = adapter.get_manifest()
        # Verify it can be validated by AgentSchema
        validated_manifest = AgentSchema(**manifest_data)
        print(f"Manifest for '{validated_manifest.name}' validated successfully.")
    else:
        print("Adapter not found.")
