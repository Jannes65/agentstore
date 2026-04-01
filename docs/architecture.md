# AgentStore Architecture

AgentStore is a distributed marketplace for AI agents, enabling secure discovery, execution, and monetization.

## 1. High-Level Overview
The system consists of a **Core API**, a **Frontend Marketplace**, and **External Agent Endpoints** hosted by builders.

```text
[ User Browser ] <--> [ AgentStore API (FastAPI) ] <--> [ SQLite/PostgreSQL ]
                              |
                              +--> [ External Agent Endpoints (Replit/AWS/etc.) ]
                              |
                              +--> [ Chatabit Payment Bridge (Lightning Network) ]
                              |
                              +--> [ Anthropic Claude (Security Reviews) ]
```

## 2. Key Components

### Core API (`agentstore_api.py`)
- Built with **FastAPI**.
- Manages agent registration, builder profiles, and execution logs.
- Implements a security review system using Claude 3.5 Sonnet to audit agent source code.

### Database (`agentstore_database.py`)
- Uses **SQLAlchemy** ORM.
- Stores `Builder`, `Agent`, and `ExecutionLog` models.
- Supports both SQLite (local development) and PostgreSQL (production).

### Marketplace Logic (`agentstore_marketplace.py`)
- Handles the discovery and search of agents.
- Implements the **L402 Protocol** for pay-per-use agent execution.
- Manages secure communication with builder-hosted endpoints.

### Payments (`agentstore_payments.py` & `agentstore_ledger.py`)
- Integrates with **Chatabit** for Bitcoin Lightning Network invoicing and payment verification.
- Maintains an internal ledger for builder earnings and platform fees.
- 80/20 revenue split between builders and the platform.

### Adapters (`agentstore_adapter.py`)
- Provides a standard interface (`AgentStoreAdapter`) for wrapping third-party frameworks.
- Includes reference implementations for **LangChain**, **CrewAI**, and **AutoGen**.

## 3. Data Flow: Agent Execution
1. User selects an agent in the frontend and provides a task.
2. Frontend calls `/agents/{agent_id}/run`.
3. Backend checks if the agent requires payment (L402).
4. If payment is required, a Lightning invoice is generated via Chatabit.
5. Once paid, the backend forwards the task to the builder's `endpoint_url`.
6. The agent response is returned to the user and the transaction is logged in the ledger.

## 4. Security Model
- **Sandboxing**: AgentStore acts as a proxy, protecting user identities from builder endpoints.
- **Code Review**: Automated and manual audits for the **Verified** badge.
- **Permissions**: Explicit declaration of agent capabilities (file access, API calls, etc.) to inform user consent.
