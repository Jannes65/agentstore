"""
AgentStore SDK - Schema Validator v0.1
Validates AI agents against the AgentStore Universal Agent Schema
Built on MCP (Model Context Protocol) - vendor neutral open standard

Install dependency: pip install pydantic
"""

from __future__ import annotations
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator, model_validator
import re
import json


# ─────────────────────────────────────────────
# ENUMS
# ─────────────────────────────────────────────

class Category(str, Enum):
    PRODUCTIVITY     = "Productivity"
    DEVELOPER_TOOLS  = "Developer Tools"
    SALES_CRM        = "Sales & CRM"
    FINANCE          = "Finance"
    CUSTOMER_SUPPORT = "Customer Support"
    RESEARCH         = "Research"
    DATA_ANALYSIS    = "Data Analysis"
    CONTENT          = "Content & Writing"
    HR               = "HR & Recruiting"
    OTHER            = "Other"


class Transport(str, Enum):
    STDIO    = "STDIO"
    HTTP_SSE = "HTTP+SSE"


class AuthType(str, Enum):
    NONE             = "None"
    API_KEY          = "API Key"
    OAUTH2           = "OAuth2"
    AGENTSTORE_TOKEN = "AgentStore Token"


class PricingModel(str, Enum):
    FREE         = "free"
    PAY_PER_USE  = "pay_per_use"
    SUBSCRIPTION = "subscription"
    TIERED       = "tiered"


class PayoutMethod(str, Enum):
    FIAT      = "fiat_bank"
    LIGHTNING = "bitcoin_lightning"
    BOTH      = "both"


class Currency(str, Enum):
    USD = "USD"
    BTC = "BTC"


class RelationshipType(str, Enum):
    COMPLEMENTS = "complements"
    REQUIRES    = "requires"
    SERVES      = "serves"


# ─────────────────────────────────────────────
# SUB-MODELS
# ─────────────────────────────────────────────

class MCPTool(BaseModel):
    name: str          = Field(..., description="Tool name (snake_case recommended)")
    description: str   = Field(..., description="What this tool does")
    input_schema: dict = Field(..., description="JSON Schema for tool inputs")
    output_schema: Optional[dict] = Field(None, description="JSON Schema for tool outputs")


class MCPResource(BaseModel):
    name: str
    uri: str
    description: Optional[str] = None


class MCPPrompt(BaseModel):
    name: str
    description: Optional[str] = None
    template: str


class PricingTier(BaseModel):
    name: str            = Field(..., description="Tier name e.g. Starter, Pro, Enterprise")
    price_usd: float     = Field(..., ge=0)
    calls_per_month: int = Field(..., gt=0)


class AgentRef(BaseModel):
    agent_id: str
    relationship_type: RelationshipType


class WorkflowExample(BaseModel):
    name: str
    description: str
    agent_sequence: List[AgentRef]


# ─────────────────────────────────────────────
# MAIN SCHEMA
# ─────────────────────────────────────────────

class AgentSchema(BaseModel):
    """AgentStore Universal Agent Schema v0.1"""

    # Section 1: Identity
    name: str                   = Field(..., min_length=1, max_length=60)
    version: str                = Field(..., description="Semantic version e.g. 1.0.0")
    description_short: str      = Field(..., min_length=10, max_length=120)
    description_long: str       = Field(..., min_length=50)
    category: Category
    tags: Optional[List[str]]   = Field(default_factory=list)
    author_name: str            = Field(..., min_length=1)
    homepage_url: Optional[str] = None
    logo_url: Optional[str]     = None

    # Section 2: MCP Configuration
    mcp_version: str                       = Field(..., description="MCP spec version e.g. 2025-11-25")
    transport: Transport
    endpoint_url: Optional[str]            = None
    tools: List[MCPTool]                   = Field(..., min_length=1)
    resources: Optional[List[MCPResource]] = Field(default_factory=list)
    prompts: Optional[List[MCPPrompt]]     = Field(default_factory=list)
    auth_type: AuthType
    auth_docs_url: Optional[str]           = None

    # Section 3: Permissions
    can_read_files: bool
    can_write_files: bool
    can_send_email: bool
    can_access_calendar: bool
    can_make_purchases: bool
    can_call_external_apis: bool
    can_spawn_subagents: bool
    data_retention_days: int             = Field(..., ge=0)
    gdpr_compliant: bool
    custom_permissions: Optional[List[str]] = Field(default_factory=list)

    # Section 4: Pricing
    pricing_model: PricingModel
    price_per_call: Optional[float]           = Field(None, ge=0)
    subscription_monthly_usd: Optional[float] = Field(None, ge=0)
    free_tier_calls_per_month: Optional[int]  = Field(None, ge=0)
    tiers: Optional[List[PricingTier]]        = Field(default_factory=list)
    payout_method: PayoutMethod
    lightning_address: Optional[str]          = None
    currency: Currency                        = Currency.USD

    # Section 6: Composition
    complementary_agents: Optional[List[AgentRef]]     = Field(default_factory=list)
    depends_on_agents: Optional[List[AgentRef]]        = Field(default_factory=list)
    can_be_subagent_for: Optional[List[AgentRef]]      = Field(default_factory=list)
    workflow_examples: Optional[List[WorkflowExample]] = Field(default_factory=list)
    input_types_accepted: List[str]  = Field(..., min_length=1)
    output_types_produced: List[str] = Field(..., min_length=1)
    max_subagent_depth: Optional[int]= Field(1, ge=1, le=10)

    @field_validator("version")
    @classmethod
    def validate_semver(cls, v):
        if not re.match(r"^\d+\.\d+\.\d+$", v):
            raise ValueError(f"version must be semantic versioning format (e.g. 1.0.0), got: {v!r}")
        return v

    @field_validator("mcp_version")
    @classmethod
    def validate_mcp_version(cls, v):
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", v):
            raise ValueError(f"mcp_version must be date format (e.g. 2025-11-25), got: {v!r}")
        return v

    @field_validator("homepage_url", "endpoint_url", "auth_docs_url", "logo_url")
    @classmethod
    def validate_urls(cls, v):
        if v is not None and not re.match(r"^https?://", v):
            raise ValueError(f"URL must start with http:// or https://, got: {v!r}")
        return v

    @field_validator("lightning_address")
    @classmethod
    def validate_lightning_address(cls, v):
        if v is not None and "@" not in v:
            raise ValueError(f"lightning_address must be a Lightning Address (e.g. you@getalby.com), got: {v!r}")
        return v

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v):
        if v and len(v) > 10:
            raise ValueError("Maximum 10 tags allowed per agent")
        return v

    @model_validator(mode="after")
    def validate_transport_endpoint(self):
        if self.transport == Transport.HTTP_SSE and not self.endpoint_url:
            raise ValueError("endpoint_url is required when transport is HTTP+SSE")
        return self

    @model_validator(mode="after")
    def validate_pricing_model_fields(self):
        if self.pricing_model == PricingModel.PAY_PER_USE and self.price_per_call is None:
            raise ValueError("price_per_call is required when pricing_model is pay_per_use")
        if self.pricing_model == PricingModel.SUBSCRIPTION and self.subscription_monthly_usd is None:
            raise ValueError("subscription_monthly_usd is required when pricing_model is subscription")
        if self.pricing_model == PricingModel.TIERED and not self.tiers:
            raise ValueError("tiers list is required when pricing_model is tiered")
        return self

    @model_validator(mode="after")
    def validate_lightning_payout_fields(self):
        needs_lightning = self.payout_method in (PayoutMethod.LIGHTNING, PayoutMethod.BOTH)
        if needs_lightning and not self.lightning_address:
            raise ValueError("lightning_address is required when payout_method includes bitcoin_lightning")
        return self

    @model_validator(mode="after")
    def validate_gdpr(self):
        if not self.gdpr_compliant:
            raise ValueError("gdpr_compliant must be True. Agents that are not GDPR compliant cannot be listed on AgentStore.")
        return self

    @model_validator(mode="after")
    def validate_purchase_permission(self):
        if self.can_make_purchases and self.pricing_model == PricingModel.FREE:
            raise ValueError("An agent with can_make_purchases=True cannot use pricing_model=free. Financial-action agents must have a billable pricing model.")
        return self


# ─────────────────────────────────────────────
# VALIDATION RESULT
# ─────────────────────────────────────────────

class ValidationResult:
    def __init__(self, valid, errors, schema):
        self.valid = valid
        self.errors = errors
        self.schema = schema

    def print_report(self):
        if self.valid:
            permissions = [l for l, v in {
                "read_files": self.schema.can_read_files,
                "write_files": self.schema.can_write_files,
                "send_email": self.schema.can_send_email,
                "calendar": self.schema.can_access_calendar,
                "purchases": self.schema.can_make_purchases,
                "external_apis": self.schema.can_call_external_apis,
                "spawn_subagents": self.schema.can_spawn_subagents,
            }.items() if v]
            print("\n  AgentStore Schema Validation PASSED")
            print(f"  Agent    : {self.schema.name} v{self.schema.version}")
            print(f"  Author   : {self.schema.author_name}")
            print(f"  Category : {self.schema.category.value}")
            print(f"  Tools    : {len(self.schema.tools)}")
            print(f"  Pricing  : {self.schema.pricing_model.value}")
            print(f"  Payout   : {self.schema.payout_method.value}")
            print(f"  Perms    : {permissions if permissions else 'none'}")
            print()
        else:
            print("\n  AgentStore Schema Validation FAILED")
            print(f"  {len(self.errors)} error(s):\n")
            for i, err in enumerate(self.errors, 1):
                print(f"  {i}. {err}")
            print()


# ─────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────

def validate_schema(data: dict) -> ValidationResult:
    """Validate an agent definition dict against the AgentStore schema."""
    try:
        schema = AgentSchema(**data)
        return ValidationResult(valid=True, errors=[], schema=schema)
    except Exception as e:
        errors = []
        if hasattr(e, "errors"):
            for err in e.errors():
                loc = " -> ".join(str(x) for x in err["loc"]) if err["loc"] else "general"
                errors.append(f"[{loc}] {err[chr(109)+chr(115)+chr(103)]}")
        else:
            errors.append(str(e))
        return ValidationResult(valid=False, errors=errors, schema=None)


def validate_schema_from_file(path: str) -> ValidationResult:
    """Load a JSON file and validate it against the AgentStore schema."""
    with open(path) as f:
        data = json.load(f)
    return validate_schema(data)