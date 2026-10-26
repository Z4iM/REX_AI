# REX AI — Integration Contracts & Interface Specifications

**Project:** REX AI — Smart Academy Multi-Agent System  
**Organization:** Andalusia Academy  
**Version:** 1.0 — Sprint 1  
**Team:** Faris Ahmed, AbdulRahman Adham, Ahmed AlAbiad

**Sprint 2 implementation update (2026-10-26):** This document retains the Sprint 1 baseline and planned full-team contracts. The local AbdulRahman workstream now implements approved-only student course access, SQLite qualification sessions, consent-based leads, upload review/rejection/publication, metadata suggestions, and three reviewed/versioned document-generation types. The implemented API reference is `docs/openapi.sprint2.json`; see `docs/SPRINT2_TA_WALKTHROUGH.md` for current behavior and `docs/abdulrahman_progress.md` for test results. Its scoped FastMCP adapter runs over local stdio; full LangGraph/team orchestration is still Sprint 3. Teammate-agent integration must be verified independently.

---

## 1. Purpose

This document defines the interfaces and communication contracts between REX AI components.

Its purpose is to ensure independently developed components can communicate consistently and support future multi-agent integration.

**Architecture:**

- Frontend: Streamlit
- Backend: FastAPI
- Agent orchestration: LangGraph
- MCP framework: FastMCP
- LLM: Google Gemini API
- Vector database: ChromaDB
- Relational database: SQLite
- Automation: n8n
- Document storage: Local filesystem

**Implementation status:** The Sprint 1 chatbot APIs are implemented. LangGraph orchestration, MCP tools, other agents, and most persistent application services are planned.

---

## 2. Existing FastAPI Contracts — IMPLEMENTED

The current API specification is exported to `docs/openapi.sprint1.json`.

**Base URL (local development):** `http://127.0.0.1:8000`

### 2.1 Health Check

**Endpoint:** `GET /health`

**Purpose:** Verify that the FastAPI application is responding.

**Response fields:**

| Field | Type | Description |
|---|---|---|
| status | string | Backend status |
| service | string | Application name |
| version | string | Backend version |

**Success:** HTTP 200.

This endpoint currently checks application responsiveness. It does not independently verify Gemini, ChromaDB, or external services.

### 2.2 General REX Assistant

**Endpoint:** `POST /api/v1/chat`

**Purpose:** Answer course-related questions using RAG.

**Request fields:**

| Field | Type | Required |
|---|---|---|
| message | string | Yes |

**Response fields:**

| Field | Type | Description |
|---|---|---|
| answer | string | Generated response |
| sources | array | Supporting source references |
| mode | string | Current data mode |
| disclaimer | string | Synthetic-data notice |

Each source reference contains:

- `source_id`
- `course`
- `section`
- `file`
- `excerpt`

**Validation and errors:**

- HTTP 422: Invalid or empty message.
- HTTP 503: RAG or answer-generation failure.
- HTTP 200: Successful response.

**Current limitation:** Each general chat request is independent. Conversation memory is not yet applied to this endpoint.

### 2.3 Learner Qualification

**Endpoint:** `POST /api/v1/qualification`

**Purpose:** Collect learner information through a multi-turn conversation.

**Request fields:**

| Field | Type | Description |
|---|---|---|
| message | string | Student's current message |
| session_id | string or null | Existing session identifier; null starts a new session |

**Response fields:**

| Field | Type | Description |
|---|---|---|
| session_id | string | Unique conversation identifier |
| status | string | `question` or `ready` |
| reply | string | Next question or completion message |
| profile | object | Collected learner information |
| query | string or null | Prepared recommendation query |
| course_matches | array or null | Course constraint results |
| matching_error | string or null | Matching validation error |

**Profile attributes:**

- background
- skill_level
- career_goal
- training_format
- budget
- availability

**Errors:**

- HTTP 422: Invalid message.
- HTTP 404: Unknown session.
- HTTP 409: Qualification already completed.

**Current limitation:** Sessions are stored in process memory and disappear when the backend restarts.

### 2.4 Personalized Course Recommendations

**Endpoint:** `POST /api/v1/qualification/{session_id}/recommendation`

**Purpose:** Generate a personalized recommendation after qualification is completed.

**Path parameter:** `session_id`

**Response fields:**

| Field | Type | Description |
|---|---|---|
| session_id | string | Conversation identifier |
| status | string | Recommendation result status |
| answer | string | Recommendation explanation |
| eligible_courses | array | Courses passing implemented constraint checks |
| needs_verification | array | Courses with missing constraint data |
| excluded_courses | array | Courses violating explicit constraints |
| sources | array | Supporting evidence references |
| mode | string | Current data mode |

**Result statuses:**

- `candidates_found`
- `no_confirmed_match`
- `insufficient_evidence`

**Errors:**

- HTTP 404: Session not found.
- HTTP 409: Qualification incomplete.
- HTTP 503: Recommendation generation failure.

**Current constraint checks:** Budget and training format.

Prerequisites and skill compatibility are considered through retrieved evidence and Gemini, but are not yet fully enforced by deterministic validators.

---

## 3. Agent Integration Contract — PLANNED

All five agents will use a consistent request and response convention.

### 3.1 Standard Agent Request

Proposed fields:

| Field | Type | Purpose |
|---|---|---|
| request_id | string | Traceable request identifier |
| agent_name | string | Target agent |
| actor_id | string or null | Requesting user or service |
| actor_role | string | Student, administrator, or system |
| payload | object | Task-specific inputs |
| context | object | Shared workflow information |
| source_policy | string | Allowed source trust level |

### 3.2 Standard Agent Response

Proposed fields:

| Field | Type | Purpose |
|---|---|---|
| request_id | string | Original request identifier |
| agent_name | string | Responding agent |
| status | string | Execution result |
| result | object | Structured agent output |
| sources | array | Supporting source references |
| errors | array | Validation or execution errors |
| requires_approval | boolean | Whether human review is necessary |

**Proposed execution statuses:**

- pending
- running
- completed
- failed
- awaiting_approval

Each agent may also define task-specific result statuses.

These conventions will be implemented and validated using Python data models during agent development.

---

## 4. FastMCP Tool Contracts — PLANNED

FastMCP will expose controlled application services to authorized agents.

The MCP server will call validated Python services instead of allowing models to execute unrestricted database operations.

### Agent 1 — REX Assistant

| Tool | Purpose |
|---|---|
| `search_courses` | Search course information |
| `get_course_details` | Retrieve structured course data |
| `retrieve_course_documents` | Retrieve approved source evidence |
| `save_lead` | Store consented student lead information |

### Agent 2 — RFP Research

| Tool | Purpose |
|---|---|
| `search_tenders` | Discover opportunities from authorized sources |
| `get_tender_details` | Retrieve tender information |
| `validate_tender` | Apply country and relevance checks |
| `save_opportunity` | Store validated opportunities |

### Agent 3 — Curriculum

| Tool | Purpose |
|---|---|
| `retrieve_standards` | Retrieve applicable competency requirements |
| `search_curriculum_sources` | Retrieve reference information |
| `save_curriculum` | Store generated curriculum drafts |
| `get_approved_curriculum` | Retrieve approved curricula |

### Agent 4 — Document Generation

| Tool | Purpose |
|---|---|
| `get_document_template` | Retrieve document template |
| `get_course_details` | Retrieve course information |
| `get_approved_curriculum` | Retrieve approved curriculum |
| `save_generated_document` | Save generated document metadata and file |

### Agent 5 — Marketing

| Tool | Purpose |
|---|---|
| `get_approved_course` | Retrieve approved course information |
| `get_approved_curriculum` | Retrieve approved curriculum |
| `save_campaign` | Store campaign drafts |
| `get_campaign_details` | Retrieve campaign information |

### MCP Security Rules

1. Validate tool inputs using typed schemas.
2. Apply authorization before sensitive operations.
3. Do not expose unrestricted SQL execution.
4. Protect file paths against unauthorized access.
5. Preserve source references and approval status.
6. Treat external documents and tool results as untrusted data.
7. Require explicit approval for publication or distribution.
8. Record significant tool executions and failures.

Actual MCP parameter schemas and transport configuration will be finalized when the MCP server is implemented.

---

## 5. LangGraph Orchestration Contract — PLANNED

LangGraph will coordinate the agents using shared workflow state.

### Proposed Workflow State

| Field | Purpose |
|---|---|
| workflow_id | Unique workflow identifier |
| task_type | Requested operation |
| actor_id | Initiating user |
| actor_role | Authorization context |
| input | Original request data |
| agent_outputs | Structured results from completed agents |
| source_ids | Evidence references |
| artifact_ids | Saved output references |
| approval_status | Human-review state |
| workflow_status | Current workflow status |
| errors | Recorded workflow errors |

Large documents should be stored through the document storage service. Workflow state should reference stored artifacts rather than unnecessarily duplicate their contents.

### Routing Rules

- Course questions → REX Assistant
- Tender discovery → RFP Agent
- Curriculum generation → Curriculum Agent
- Educational document creation → Document Agent
- Marketing requests → Marketing Agent

Multi-agent workflows will use explicitly defined transitions.

### Example Connected Workflow

Curriculum Agent  
→ Generate curriculum draft  
→ Save draft  
→ Administrator approval  
→ Document Generation Agent  
→ Generate PDF  
→ Save output  
→ Return download reference

The workflow must stop or await further action if approval is rejected or unavailable.

---

## 6. Shared Data Contracts — PLANNED

### Course Records

Proposed core fields:

- course_id
- title
- department
- skill_level
- prerequisites
- learning_outcomes
- duration
- training_format
- price
- currency
- instructor_id
- source_id
- approval_status
- updated_at

Unknown values must remain explicitly unknown rather than being invented.

### Knowledge Sources

Each indexed source should preserve:

- source_id
- document_id
- source_file
- document_type
- dataset_status
- approval_status
- source_version
- update_timestamp
- relevant metadata

### RFP Records

Required business fields include:

- opportunity_id
- title
- issuing_organization
- country
- category
- publication_date
- deadline
- eligibility_requirements
- submission_url
- source_url
- summary
- status

Only Egypt and Saudi Arabia are supported.

### Generated Artifacts

Proposed fields:

- artifact_id
- document_type
- related_course_id
- storage_reference
- version
- approval_status
- source_ids
- created_at

The SQLite database will store structured records and metadata. ChromaDB will store embeddings and retrieval information. The file storage service will hold original and generated documents.

---

## 7. Human Approval Contract — PLANNED

**Content approval states:**

- draft
- pending_review
- approved
- rejected
- revision_requested

Approval records should include:

- artifact or workflow identifier
- content version
- reviewer identifier
- decision
- timestamp
- review comments

Only authorized administrators may approve protected outputs.

LangGraph will pause designated workflows pending approval.

n8n may send notifications but cannot grant approval independently.

---

## 8. Automation Contract — PLANNED

n8n will handle scheduled tasks and external notification delivery.

Example RFP workflow:

1. n8n triggers a scheduled check.
2. An authenticated request starts the RFP workflow.
3. The research agent retrieves opportunity information.
4. Deterministic validation enforces the country restriction.
5. Validated results are saved.
6. New relevant Egyptian opportunities create priority alerts.
7. Notifications are recorded and optionally emailed.

Retries and repeated events must not create duplicate opportunities or unauthorized side effects.

---

## 9. Data Trust and Security Boundaries

### Sprint 1

Current data is synthetic and unapproved.

- Synthetic sources must be labeled as demonstration data.
- The system must not present fictional courses as actual academy offerings.
- Missing information must not be fabricated.

### Future Academy Data

When approved documents become available:

- Source approval must be verified.
- Documents must be processed and indexed.
- Existing synthetic test collections must remain isolated.
- Answers must cite authorized information.
- Unapproved documents must not automatically become trusted references.

### Deployment Limitations

The current Sprint 1 API uses local development endpoints and in-memory qualification sessions.

Production-grade authentication, authorization, persistent sessions, rate limiting, and secure external integrations are not yet complete.

The public chatbot and protected administrator dashboard are architectural targets, not currently completed security controls.

---

## 10. Sprint Responsibility Boundaries

### Sprint 1

**Implemented:**

- Markdown document loading
- Course metadata normalization
- Structure-aware chunking
- Gemini embeddings
- ChromaDB indexing and retrieval
- Grounded answer generation
- Learner qualification
- Course constraint matching
- Personalized recommendation generation
- FastAPI endpoints
- Streamlit interface

**Design documentation:**

- System architecture
- Agent workflows
- API and integration contracts

### Sprint 2

Planned:

- Additional agent implementations
- FastMCP tool server and integrations
- Agent-level testing
- Initial document generation
- RFP and marketing workflows

### Sprint 3

Planned:

- Full LangGraph multi-agent integration
- Connected workflow demonstrations
- Human approval integration
- Final interface refinements
- End-to-end testing
- Final documentation and presentation

---

## 11. Contract Versioning

**Version:** 1.0

Any changes to existing APIs or planned integration schemas should be documented and reflected in the corresponding Python models and tests.

The exported OpenAPI specification is the reference for currently implemented HTTP endpoints.

Planned contracts remain subject to implementation review.

**Maintainers:** Faris Ahmed, AbdulRahman Adham, Ahmed AlAbiad.
