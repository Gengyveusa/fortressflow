"""Pydantic schemas for the agents API."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


# ── Request schemas ──────────────────────────────────────────────────────────


class AgentExecuteRequest(BaseModel):
    action: str = Field(..., description="Agent method to invoke (e.g. 'chat', 'embed')")
    params: dict = Field(default_factory=dict, description="Parameters for the action")


class WorkflowStepRequest(BaseModel):
    agent_name: str = Field(..., description="Agent to use: groq, openai, hubspot, zoominfo, twilio")
    action: str = Field(..., description="Method to invoke on the agent")
    params: dict = Field(default_factory=dict, description="Parameters for this step")
    depends_on: int | None = Field(None, description="Index of step whose result feeds into this step")


class WorkflowRequest(BaseModel):
    steps: list[WorkflowStepRequest] = Field(..., min_length=1, description="Ordered list of workflow steps")


class AgentLogsQuery(BaseModel):
    agent_name: str | None = None
    status: str | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)


# ── Response schemas ─────────────────────────────────────────────────────────


class AgentStatusEntry(BaseModel):
    agent_name: str
    configured: bool
    has_db_key: bool
    has_env_key: bool


class AgentStatusResponse(BaseModel):
    agents: list[AgentStatusEntry]


class AgentExecuteResponse(BaseModel):
    agent_name: str
    action: str
    status: str
    result: dict | list | str | None = None
    error: str | None = None
    latency_ms: int | None = None


class WorkflowStepResult(BaseModel):
    step_index: int
    agent_name: str
    action: str
    status: str
    result: dict | list | str | None = None
    error: str | None = None


class WorkflowResponse(BaseModel):
    status: str
    steps: list[WorkflowStepResult]


class AgentActionLogResponse(BaseModel):
    id: UUID
    user_id: UUID
    agent_name: str
    action: str
    params: dict | None = None
    result_summary: dict | None = None
    status: str
    latency_ms: int | None = None
    error_message: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AgentLogsResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[AgentActionLogResponse]


# ── Training config schemas ─────────────────────────────────────────────────


class AgentTrainingConfigResponse(BaseModel):
    id: UUID
    agent_name: str
    config_type: str
    config_key: str
    config_value: dict | list | str
    is_active: bool
    priority: int
    updated_at: datetime

    model_config = {"from_attributes": True}


class AgentTrainingConfigUpdate(BaseModel):
    config_type: str
    config_key: str
    config_value: dict | list | str
    is_active: bool = True
    priority: int = 0


class AgentTrainingBulkUpdate(BaseModel):
    configs: list[AgentTrainingConfigUpdate]


# ── Workflow planner schemas ────────────────────────────────────────────────


class WorkflowPlanRequest(BaseModel):
    message: str = Field(..., description="Natural language request for planning")


class WorkflowPlanResponse(BaseModel):
    understanding: str
    plan_type: str
    steps: list[dict]
    options: list[dict] | None = None
    warnings: list[str] | None = None
    estimated_time: str | None = None
    confirmation_needed: bool = True
    plan_id: str
    outreach_options: dict | None = None


class WorkflowPlanExecuteRequest(BaseModel):
    plan_id: str
    selected_option: int | None = None


class OutreachOptionsResponse(BaseModel):
    target: str
    options: list[dict]
    lead_sourcing: dict
    next_steps: str


# ── Phase 10 Additions ──────────────────────────────────────────────────


class ApolloPersonSearchRequest(BaseModel):
    """Search Apollo's 210M+ contact database."""

    q_person_title: str | None = Field(None, description="Job title filter (e.g. 'DDS', 'Dentist', 'Office Manager')")
    q_organization_name: str | None = Field(None, description="Company name filter")
    person_locations: list[str] | None = Field(None, description="Locations (e.g. ['Denver, CO', 'Austin, TX'])")
    person_seniorities: list[str] | None = Field(
        None, description="Seniority levels: owner, founder, c_suite, vp, director, manager"
    )
    organization_industry_tag_ids: list[str] | None = Field(None, description="Industry tags for filtering")
    organization_num_employees_ranges: list[str] | None = Field(
        None, description="Employee count ranges (e.g. ['1,10', '11,50'])"
    )
    per_page: int = Field(25, ge=1, le=100, description="Results per page")
    page: int = Field(1, ge=1, description="Page number")


class ApolloOrganizationSearchRequest(BaseModel):
    """Search Apollo's 35M+ company database."""

    q_organization_name: str | None = Field(None, description="Company name keyword search")
    organization_locations: list[str] | None = Field(None, description="HQ locations")
    organization_industry_tag_ids: list[str] | None = Field(None, description="Industry filter tags")
    organization_num_employees_ranges: list[str] | None = Field(None, description="Employee count ranges")
    organization_revenue_ranges: list[str] | None = Field(
        None, description="Revenue ranges (e.g. ['1000000,10000000'])"
    )
    per_page: int = Field(25, ge=1, le=100)
    page: int = Field(1, ge=1)


class ApolloEnrichRequest(BaseModel):
    """Enrich a person using Apollo's waterfall enrichment."""

    email: str | None = Field(None, description="Email address to enrich")
    first_name: str | None = None
    last_name: str | None = None
    organization_name: str | None = None
    domain: str | None = None
    linkedin_url: str | None = None
    reveal_phone_number: bool = Field(False, description="Also reveal phone number (costs extra credit)")


class ApolloBulkEnrichRequest(BaseModel):
    """Bulk enrich up to 10 people per call."""

    details: list[ApolloEnrichRequest] = Field(..., min_length=1, max_length=10)


class ApolloContactCreate(BaseModel):
    """Create a contact in Apollo CRM."""

    first_name: str
    last_name: str
    email: str | None = None
    organization_name: str | None = None
    title: str | None = None
    phone: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None


class ApolloSequenceEnrollRequest(BaseModel):
    """Enroll contacts into an Apollo email sequence."""

    sequence_id: str = Field(..., description="Apollo sequence ID")
    contact_ids: list[str] = Field(..., min_length=1, description="Apollo contact IDs to enroll")
    email_account_id: str = Field(..., description="Email account to send from")
    send_email_from_email_account: bool = True


class ApolloDealCreate(BaseModel):
    """Create a deal in Apollo's pipeline."""

    name: str = Field(..., description="Deal name")
    amount: float | None = None
    contact_ids: list[str] | None = None
    account_id: str | None = None
    stage: str | None = None
    close_date: str | None = Field(None, description="ISO date string")


class ApolloTaskCreate(BaseModel):
    """Create a task in Apollo."""

    contact_id: str | None = None
    account_id: str | None = None
    type: str = Field("action_item", description="Task type: action_item, call, email")
    due_date: str | None = Field(None, description="ISO date string")
    note: str | None = None
    priority: str = Field("normal", description="Priority: low, normal, high")


# ── Taplio-specific schemas ──────────────────────────────────────────────────


class TaplioPostRequest(BaseModel):
    """Generate a LinkedIn post via Taplio's AI."""

    topic: str = Field(..., description="Topic or prompt for the post")
    tone: str = Field("professional", description="Tone: professional, casual, thought_leader, educational")
    format: str = Field("text", description="Format: text, carousel, hook_only")
    industry_context: str = Field("dental B2B", description="Industry context for relevant content")
    include_cta: bool = Field(True, description="Include a call-to-action")
    max_length: int = Field(1300, description="Max character length (LinkedIn limit ~3000)")


class TaplioScheduleRequest(BaseModel):
    """Schedule a LinkedIn post for publishing."""

    content: str = Field(..., description="Post content to schedule")
    scheduled_time: str = Field(..., description="ISO datetime for publishing")
    first_comment: str | None = Field(None, description="Optional first comment to add after posting")


class TaplioDMRequest(BaseModel):
    """Compose a personalized LinkedIn DM."""

    recipient_name: str = Field(..., description="Recipient's name")
    recipient_title: str | None = Field(None, description="Recipient's job title")
    recipient_company: str | None = Field(None, description="Recipient's company")
    purpose: str = Field(..., description="Purpose of the DM (e.g. 'introduce dental software')")
    tone: str = Field("professional", description="Tone: professional, casual, friendly")
    max_length: int = Field(300, description="Max character length for DM")


class TaplioBulkDMRequest(BaseModel):
    """Compose personalized DMs for multiple recipients."""

    recipients: list[TaplioDMRequest] = Field(..., min_length=1, max_length=50)
    template_override: str | None = Field(None, description="Optional template to use for all DMs")


class TaplioLeadSearchRequest(BaseModel):
    """Search Taplio's 3M+ enriched LinkedIn profile database."""

    job_title: str | None = Field(None, description="Job title filter")
    company: str | None = Field(None, description="Company name filter")
    location: str | None = Field(None, description="Location filter")
    industry: str | None = Field(None, description="Industry filter")
    seniority: str | None = Field(None, description="Seniority: entry, mid, senior, executive")
    per_page: int = Field(25, ge=1, le=100)


class TaplioConnectionRequest(BaseModel):
    """Send a LinkedIn connection request with a personalized note."""

    linkedin_url: str = Field(..., description="LinkedIn profile URL of the target")
    note: str = Field(..., max_length=300, description="Personalized connection note")


# ── Expanded WhatsApp / MMS schemas ──────────────────────────────────────────


class WhatsAppMessageRequest(BaseModel):
    """Send a WhatsApp Business message via Twilio."""

    to: str = Field(..., description="Recipient phone (E.164 format, e.g. +14155551234)")
    body: str = Field(..., description="Message body text")
    media_url: str | None = Field(None, description="URL to media attachment (image, PDF)")
    content_sid: str | None = Field(None, description="Twilio Content SID for approved templates")
    content_variables: dict | None = Field(None, description="Template variable values")


class MMSRequest(BaseModel):
    """Send an MMS message via Twilio."""

    to: str = Field(..., description="Recipient phone (E.164 format)")
    body: str | None = Field(None, description="Optional text body")
    media_urls: list[str] = Field(..., min_length=1, max_length=10, description="URLs to media files")


class ScheduledMessageRequest(BaseModel):
    """Schedule a message for future delivery via Twilio."""

    to: str = Field(..., description="Recipient phone (E.164 format)")
    body: str = Field(..., description="Message body")
    send_at: str = Field(..., description="ISO datetime for delivery (15 min to 7 days in future)")
    channel: str = Field("sms", description="Channel: sms, whatsapp, mms")


# ── Expanded HubSpot schemas ────────────────────────────────────────────────


class HubSpotPipelineCreate(BaseModel):
    """Create a HubSpot pipeline."""

    label: str = Field(..., description="Pipeline display name")
    display_order: int = Field(0, description="Display order (lower = first)")
    stages: list[dict] | None = Field(None, description="Initial stages to create")


class HubSpotAssociationCreate(BaseModel):
    """Create an association between two HubSpot objects."""

    from_object_type: str = Field(..., description="Source object type (e.g. 'contacts')")
    from_object_id: str = Field(..., description="Source object ID")
    to_object_type: str = Field(..., description="Target object type (e.g. 'deals')")
    to_object_id: str = Field(..., description="Target object ID")
    association_type: str = Field(..., description="Association type ID or label")


class HubSpotCRMSearchRequest(BaseModel):
    """Advanced CRM search with filters."""

    object_type: str = Field(..., description="Object type: contacts, companies, deals, tickets")
    filters: list[dict] = Field(..., description="Filter groups with propertyName, operator, value")
    sorts: list[dict] | None = Field(None, description="Sort criteria")
    properties: list[str] | None = Field(None, description="Properties to return")
    limit: int = Field(10, ge=1, le=100)
    after: str | None = Field(None, description="Pagination cursor")


class HubSpotWebhookSubscription(BaseModel):
    """Subscribe to HubSpot CRM events."""

    event_type: str = Field(..., description="Event type (e.g. 'contact.creation', 'deal.propertyChange')")
    property_name: str | None = Field(None, description="Property to watch (for propertyChange events)")
    active: bool = Field(True, description="Whether subscription is active")
