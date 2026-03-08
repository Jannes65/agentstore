from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional
from agentstore_adapter import AgentStoreAdapter, LangChainAdapter
from agentstore_schema import AgentSchema

from pydantic import BaseModel, Field

class PermissionScope(BaseModel):
    """Defines the declared permissions for an agent execution."""
    can_read_files: bool = False
    can_write_files: bool = False
    can_make_external_calls: bool = False
    can_access_env_vars: bool = False

class ExecutionLog(BaseModel):
    """Logs the results of an agent execution."""
    agent_id: str
    timestamp: str
    input_str: str
    output: str
    permissions_used: List[str]

class SandboxedRunner:
    """Wraps an adapter and enforces PermissionScope constraints."""

    def __init__(self, adapter: AgentStoreAdapter, scope: PermissionScope):
        self.adapter = adapter
        self.scope = scope
        self._manifest = AgentSchema(**self.adapter.get_manifest())

    def _check_permissions(self):
        """Checks if the adapter's manifest exceeds the declared PermissionScope."""
        violations = []
        if self._manifest.can_read_files and not self.scope.can_read_files:
            violations.append("can_read_files")
        if self._manifest.can_write_files and not self.scope.can_write_files:
            violations.append("can_write_files")
        if self._manifest.can_call_external_apis and not self.scope.can_make_external_calls:
            violations.append("can_make_external_calls")
        # AgentSchema doesn't have can_access_env_vars, but we check if it's in custom_permissions
        if "can_access_env_vars" in (self._manifest.custom_permissions or []) and not self.scope.can_access_env_vars:
            violations.append("can_access_env_vars")

        if violations:
            raise PermissionError(f"Agent exceeds its declared scope. Unauthorized permissions: {', '.join(violations)}")

    def run(self, input_str: str) -> ExecutionLog:
        """Runs the agent after verifying permissions and logs the action."""
        self._check_permissions()

        # Simulate logging the action
        permissions_used = []
        if self.scope.can_read_files: permissions_used.append("read_files")
        if self.scope.can_write_files: permissions_used.append("write_files")
        if self.scope.can_make_external_calls: permissions_used.append("external_calls")
        if self.scope.can_access_env_vars: permissions_used.append("access_env_vars")

        result_str = self.adapter.run(input_str)

        return ExecutionLog(
            agent_id=self._manifest.name,
            timestamp=datetime.now().isoformat(),
            input_str=input_str,
            output=result_str,
            permissions_used=permissions_used
        )

class TrustScore(BaseModel):
    """Represents the trust and verification status of an agent."""
    agent_id: str
    verified: bool
    community_rating: float
    task_completion_rate: float

    def badge(self) -> str:
        """Returns a string representation of the agent's trust level."""
        if self.verified:
            return "AgentStore Verified"
        if self.community_rating >= 4.0:
            return "Community Rated"
        return "Unverified"

if __name__ == "__main__":
    # 1. Setup a LangChain adapter
    adapter = LangChainAdapter()
    
    # 2. Define a read-only PermissionScope
    # Note: LangChainAdapter manifest currently has all 'can_...' as False
    read_only_scope = PermissionScope(can_read_files=True)
    
    # 3. Create a SandboxedRunner
    runner = SandboxedRunner(adapter, read_only_scope)
    
    # 4. Run and print execution log
    try:
        log = runner.run("Hello from the sandbox!")
        print("--- Execution Log ---")
        print(f"Agent ID: {log.agent_id}")
        print(f"Timestamp: {log.timestamp}")
        print(f"Input: {log.input_str}")
        print(f"Output: {log.output}")
        print(f"Permissions Used: {log.permissions_used}")
        
        # 5. Demonstrate TrustScore
        trust = TrustScore(
            agent_id="langchain_001",
            verified=True,
            community_rating=4.8,
            task_completion_rate=0.95
        )
        print(f"\nTrust Badge: {trust.badge()}")
        
    except PermissionError as e:
        print(f"Permission Error: {e}")
