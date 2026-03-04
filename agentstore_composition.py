from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime

from agentstore_schema import Category
from agentstore_adapter import LangChainAdapter, CrewAIAdapter, AgentStoreAdapter
from agentstore_trust import PermissionScope, TrustScore, ExecutionLog, SandboxedRunner
from agentstore_marketplace import Marketplace, Listing

# ─────────────────────────────────────────────
# MODELS
# ─────────────────────────────────────────────

class WorkflowStep(BaseModel):
    """Represents a single step in an agent workflow."""
    agent_id: str
    input_template: str = "{previous_output}"  # Can reference {previous_output}
    permissions: PermissionScope = Field(default_factory=PermissionScope)

class AgentWorkflow(BaseModel):
    """Defines a sequence of agent executions as a single workflow."""
    workflow_id: str
    name: str
    steps: List[WorkflowStep]
    price_sats: int  # Total price, split across agents automatically

# ─────────────────────────────────────────────
# RUNNER
# ─────────────────────────────────────────────

class WorkflowRunner:
    """Chains multiple agents together in a structured workflow."""

    def run(self, workflow: AgentWorkflow, initial_input: str, marketplace: Marketplace) -> List[ExecutionLog]:
        """
        Executes the workflow steps in sequence.
        Chains outputs as inputs for subsequent steps.
        """
        logs: List[ExecutionLog] = []
        current_input = initial_input
        previous_output = initial_input

        print(f"[*] Starting workflow: {workflow.name} ({workflow.workflow_id})")

        for i, step in enumerate(workflow.steps):
            print(f"[*] Step {i+1}: Executing agent '{step.agent_id}'")
            
            # Resolve the input template
            # For the first step, {previous_output} is the initial_input
            step_input = step.input_template.format(previous_output=previous_output)
            
            # Execute via marketplace (using SandboxedRunner)
            # Note: We use the permissions defined in the step to override/augment
            # but for this simplified logic, we rely on the Marketplace's run_agent 
            # which uses the listing's declared scope. 
            # If we wanted to enforce the step-specific permissions, we'd manually
            # create a SandboxedRunner here. Let's do that to be precise.
            
            listing = marketplace.listings.get(step.agent_id)
            if not listing:
                raise ValueError(f"Agent '{step.agent_id}' not found in marketplace for workflow step.")

            # Use permissions from the step if they are provided/different
            runner = SandboxedRunner(listing.adapter, step.permissions)
            log = runner.run(step_input)
            
            logs.append(log)
            previous_output = log.output
            print(f"[*] Step {i+1} completed. Output: {log.output[:50]}...")

        print(f"[*] Workflow '{workflow.name}' finished successfully.")
        return logs

# ─────────────────────────────────────────────
# MAIN BLOCK (DEMO)
# ─────────────────────────────────────────────

if __name__ == "__main__":
    # 1. Setup Marketplace with 2 agents: Researcher and Summarizer
    marketplace = Marketplace()

    # Research Agent (LangChain)
    research_agent = Listing(
        agent_id="researcher_01",
        adapter=LangChainAdapter(), # In real life, this would have search tools
        scope=PermissionScope(can_make_external_calls=True),
        trust_score=TrustScore(agent_id="researcher_01", verified=True, community_rating=4.5, task_completion_rate=0.9),
        price_sats=300,
        category=Category.RESEARCH
    )
    
    # Summary Agent (CrewAI)
    summary_agent = Listing(
        agent_id="summarizer_02",
        adapter=CrewAIAdapter(), # Specialized in distillation
        scope=PermissionScope(can_read_files=False),
        trust_score=TrustScore(agent_id="summarizer_02", verified=True, community_rating=4.8, task_completion_rate=0.95),
        price_sats=200,
        category=Category.PRODUCTIVITY
    )

    marketplace.publish(research_agent)
    marketplace.publish(summary_agent)

    # 2. Define the Workflow
    # Research a topic -> Summarize the research results
    workflow = AgentWorkflow(
        workflow_id="wf_market_analysis",
        name="Market Research & Summary",
        steps=[
            WorkflowStep(
                agent_id="researcher_01",
                input_template="Research the latest trends in {previous_output}",
                permissions=PermissionScope(can_make_external_calls=True)
            ),
            WorkflowStep(
                agent_id="summarizer_02",
                input_template="Summarize the following research findings into 3 bullet points: {previous_output}",
                permissions=PermissionScope() # Minimal permissions
            )
        ],
        price_sats=500 # Total price
    )

    # 3. Run the Workflow
    runner = WorkflowRunner()
    try:
        results = runner.run(workflow, "Bitcoin Lightning Network", marketplace)

        print("\n--- Workflow Execution Results ---")
        for i, log in enumerate(results):
            print(f"Step {i+1} ({log.agent_id}):")
            print(f"  Input:  {log.input_str}")
            print(f"  Output: {log.output}")
            print(f"  Perms:  {log.permissions_used}")
            print("-" * 30)

    except Exception as e:
        print(f"Workflow failed: {e}")
