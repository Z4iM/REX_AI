
# REX AI — Agent Responsibilities & Workflows

**Sprint 2 update (2026-10-26):** Current ownership is AbdulRahman for the Assistant/catalog/RAG and Document Generation, Faris for RFP and later Curriculum, and Ahmed for AI Marketing only. The Assistant and three course-based document types are implemented locally, including persistent qualification, consent-based lead capture, staff review/versioning and DOCX/PDF outputs. The sections below retain the original target workflows; consult `docs/SPRINT2_TA_WALKTHROUGH.md` for implemented capabilities and verification. Curriculum-based generation remains blocked on Faris's approved interface. Full team orchestration is not claimed by this branch.

## 1. Project Overview

REX AI is a multi-agent system developed for Andalusia Academy.

The system consists of five specialized AI agents coordinated through LangGraph.

### Technology Stack

- Frontend: Streamlit
- Backend: FastAPI
- LLM: Google Gemini API
- Agent Orchestration: LangGraph
- MCP Integration: FastMCP
- Vector Database: ChromaDB
- Embeddings: Gemini Embedding 2 (768 dimensions)
- Relational Database: SQLite + SQLAlchemy + Alembic
- Workflow Automation: n8n
- Document Storage: Local filesystem

### System Principles

1. Every agent performs a clearly defined business task.
2. Agents communicate through structured interfaces.
3. Approved source information takes priority over generated content.
4. Deterministic validation enforces business constraints.
5. Human approval is required for specified operations.
6. Agent outputs retain source references where applicable.
7. Errors must be recorded and handled appropriately.

---

## 2. Agent 1 — REX Course Assistant

### Objective

Help potential students choose suitable training courses.

### Inputs

- Student questions
- Educational background
- Existing experience
- Skill level
- Career goals
- Preferred training format
- Budget
- Available learning time
- Approved course catalog

### Workflow

1. Receive a student question through Streamlit.
2. Route the request through FastAPI.
3. Determine whether the student wants general course information or a guided recommendation.
4. For general questions:
   - Generate a question embedding.
   - Retrieve relevant approved course information from ChromaDB.
   - Generate a grounded answer using Gemini.
   - Return source references.
5. For guided recommendations:
   - Collect learner information through follow-up questions.
   - Maintain session state.
   - Validate explicit budget and training-format constraints.
   - Identify eligible, excluded, and unverified candidates.
   - Retrieve supporting course evidence.
   - Generate a personalized recommendation where sufficient evidence exists.
6. Return the answer or matching results to Streamlit.

### MCP Tools (Planned)

- search_courses
- get_course_details
- retrieve_course_documents
- save_lead

### Outputs

- Course information
- Personalized recommendations
- Reasons for course suitability
- Source references
- Lead records where consent is provided

### Business Rules

- Never invent course information.
- Never present synthetic courses as official offerings.
- Respect available prerequisites and course constraints.
- Report unknown information explicitly.
- Collect lead information only with consent.

### Implementation Status

Sprint 1 prototype implemented:
- Basic RAG chatbot
- Gemini integration
- ChromaDB retrieval
- Learner qualification
- Budget and training-format matching
- FastAPI endpoints
- Streamlit interface

Remaining enhancements are planned for Sprint 2.

---

## 3. Agent 2 — Educational RFP Research Agent

### Objective

Discover relevant educational tenders and RFP opportunities in Egypt and Saudi Arabia.

### Inputs

- Approved tender sources
- Country restrictions
- Training categories
- Deadline requirements
- Eligibility criteria
- Academy qualification information

### Workflow

1. n8n triggers the research workflow on a configured schedule or through a manual action.
2. LangGraph invokes the RFP Research Agent.
3. The agent accesses approved research connectors through FastMCP.
4. Retrieve tender information using:
   - Official APIs where available
   - Permitted public-page extraction
   - Imported tender documents
5. Extract structured tender information:
   - Title
   - Issuing organization
   - Country
   - Publication date
   - Deadline
   - Category
   - Eligibility requirements
   - Submission link
   - Available documents
6. Validate the country using deterministic Python logic.
7. Exclude opportunities outside Egypt and Saudi Arabia.
8. Reject irrelevant or expired opportunities.
9. Detect duplicate opportunities.
10. Use Gemini to summarize relevant opportunities.
11. Assess potential academy eligibility using available evidence.
12. Store opportunities in SQLite.
13. Flag relevant Egyptian opportunities for priority review.
14. Include relevant Saudi opportunities in the monitoring pipeline.
15. Generate dashboard notifications and optional n8n email alerts.

### MCP Tools (Planned)

- search_tenders
- get_tender_details
- validate_tender
- save_opportunity

### Outputs

- Structured tender records
- Relevance assessment
- Eligibility assessment
- AI summaries
- Source links
- Priority notifications

### Business Rules

- Only Egypt and Saudi Arabia are supported.
- Missing country information requires verification.
- Source URLs must be retained.
- Unverified eligibility must not be described as confirmed.
- Failed research sources must be recorded.

### Implementation Status

Planned for Sprint 2.

---

## 4. Agent 3 — Curriculum & Accreditation Agent

### Objective

Research, generate, and evaluate educational curricula.

### Inputs

- Course topic
- Target audience
- Skill level
- Intended learning outcomes
- Training duration
- Industry requirements
- Approved curriculum references
- Applicable accreditation or competency frameworks

### Workflow

1. An administrator requests a curriculum.
2. FastAPI sends the request to the LangGraph orchestrator.
3. The Curriculum Agent retrieves relevant approved references.
4. Analyze the requested skills and learning objectives.
5. Generate a structured curriculum containing:
   - Course description
   - Objectives
   - Target audience
   - Prerequisites
   - Learning outcomes
   - Modules and topics
   - Training hours
   - Practical exercises
   - Assessments
   - Capstone project
6. Retrieve applicable accreditation or competency requirements.
7. Compare the proposed curriculum against documented requirements.
8. Identify missing topics and learning outcomes.
9. Generate an accreditation-alignment report.
10. Save the curriculum as a draft.
11. Pause the workflow for administrator review.
12. Allow approval, rejection, or revision.
13. Make approved curriculum data available to other agents.

### MCP Tools (Planned)

- retrieve_standards
- search_curriculum_sources
- save_curriculum
- get_approved_curriculum

### Outputs

- Structured curriculum
- Learning objectives
- Module breakdown
- Accreditation gap analysis
- Approval status

### Business Rules

- Never claim official accreditation without evidence.
- Retain supporting source references.
- Generated curricula require instructor or administrator review.
- Unapproved curricula must not be treated as approved course information.

### Implementation Status

Planned for Sprint 2.

---

## 5. Agent 4 — Educational Document Generation Agent

### Objective

Generate professional educational documents using approved templates and course information.

### Inputs

- Document type
- Course or curriculum data
- Approved templates
- Language preferences
- Intended audience
- Formatting requirements

### Workflow

1. Administrator selects a document type.
2. Retrieve relevant course or curriculum information.
3. Retrieve the appropriate document template.
4. Validate required information.
5. Use Gemini to generate structured document content.
6. Apply the approved template.
7. Generate a downloadable PDF.
8. Save the generated file through the storage service.
9. Register file metadata and status in SQLite.
10. Allow the administrator to review and request modifications.
11. Make the generated document available for download.
12. Optionally distribute an approved document through an authorized channel.

### Supported Document Types (Target Scope)

- Course Description
- Course Proposal
- Curriculum PDF
- Participant Guide
- Facilitator / Instructor Guide
- Presentation Outline or Slides
- Question Bank
- Assessment Rubrics
- Capstone Project Brief
- Learning Outcomes and Assessment Plan

### MCP Tools (Planned)

- get_document_template
- get_course_details
- get_approved_curriculum
- save_generated_document

### Outputs

- Generated document
- Downloadable PDF
- Document metadata
- Review status
- Source references where applicable

### Business Rules

- Documents must use appropriate templates.
- Missing information must not be fabricated.
- Arabic and English should be supported where applicable.
- The Sprint 2 MVP must generate at least three professional document types.

### Implementation Status

Planned for Sprint 2.

---

## 6. Agent 5 — AI Marketing Agent

### Objective

Generate marketing content and campaign recommendations for academy courses.

### Inputs

- Approved course information
- Target audience
- Marketing platform
- Campaign objective
- Available budget
- Approved promotions
- Course learning outcomes

### Workflow

1. Administrator selects an approved course.
2. Retrieve approved information about the course.
3. Collect campaign requirements.
4. Use Gemini to generate marketing content.
5. Produce variations for selected channels:
   - Facebook
   - Instagram
   - LinkedIn
   - Email
   - WhatsApp
6. Generate campaign headlines and calls to action.
7. Recommend a basic campaign strategy.
8. Save the campaign as a draft.
9. Request administrator approval.
10. Allow revision or rejection.
11. Export approved content for distribution.
12. External publication or sending requires a separate authorized action.

### MCP Tools (Planned)

- get_approved_course
- get_approved_curriculum
- save_campaign
- get_campaign_details

### Outputs

- Social media captions
- Advertising content
- Email marketing copy
- WhatsApp promotional content
- Campaign strategy
- Multiple content variations
- Approval status

### Business Rules

- Never invent promotions or prices.
- Use approved course information.
- Require manual approval before publication.
- Do not publish automatically without authorization.

### Implementation Status

Planned for Sprint 2.

---

## 7. Multi-Agent Orchestration

LangGraph coordinates agent workflows through structured states and defined routing rules.

### Single-Agent Requests

A request that requires only one agent is routed to that agent.

Examples:

Student Question
→ REX Assistant
→ Grounded Answer

Tender Search
→ RFP Research Agent
→ Validated Opportunities

### Connected Workflow A — Curriculum to Marketing

Administrator Request
→ Curriculum Agent
→ Generate Curriculum Draft
→ Human Review
→ Approved Curriculum
→ Marketing Agent
→ Generate Campaign Draft
→ Human Review
→ Approved Campaign

An unapproved curriculum must not be promoted as an approved course.

### Connected Workflow B — Curriculum to Documents

Administrator Request
→ Curriculum Agent
→ Generate Curriculum
→ Human Approval
→ Document Generation Agent
→ Produce PDF
→ Save File
→ Download

### Shared Components

The agents use common application services:

- Gemini LLM provider
- ChromaDB knowledge retrieval
- SQLite structured records
- Local document storage
- FastMCP tools
- Logging and error handling
- Approval and notification services

### Orchestration Rules

1. Route requests to the appropriate agent.
2. Validate tool inputs and outputs.
3. Pass structured state between workflow steps.
4. Preserve provenance and approval status.
5. Pause workflows when human approval is required.
6. Resume only after an authorized decision.
7. Record failures and avoid unauthorized actions.

---

## 8. Human-in-the-Loop

Human review is required before specified AI-generated outputs become approved or are distributed.

### Approval States

- draft
- pending_review
- approved
- rejected
- revision_requested

### Approval Process

1. Agent generates draft content.
2. Application stores the draft and its version.
3. LangGraph pauses the workflow.
4. Administrator reviews the content.
5. Administrator approves, rejects, or requests changes.
6. The decision is recorded in SQLite.
7. LangGraph resumes or stops the workflow accordingly.

n8n can notify administrators but must not independently grant approval.

---

## 9. Error Handling

The system must handle:

- Gemini API errors and rate limits
- Retrieval failures
- Invalid input
- Missing approved source information
- Unsupported files
- External tender source failures
- Document generation failures
- Expired sessions
- Pending or rejected approvals

Errors should be logged without exposing credentials or sensitive user data.

---

## 10. Sprint Boundaries

### Sprint 1 — Foundation

- Define agent responsibilities and workflows.
- Select technologies.
- Prepare architecture.
- Build an initial course knowledge base.
- Build and demonstrate a basic REX Assistant.

### Sprint 2 — Agent Development

- Complete the REX Assistant workflow.
- Implement the RFP Research Agent.
- Implement the Curriculum Agent.
- Implement the Document Generation Agent.
- Implement the Marketing Agent.
- Develop necessary MCP integrations.
- Test agents independently.

### Sprint 3 — Integration and Delivery

- Integrate agents through LangGraph.
- Test connected workflows.
- Finalize interface and approvals.
- Verify source restrictions and output quality.
- Complete documentation.
- Prepare final demonstration.

---

## 11. Team Collaboration

Team Members:

- Faris Ahmed
- AbdulRahman Adham
- Ahmed AlAbiad

All members collaborate throughout development.

Primary responsibility assignments are documented in WBS.md.

Actual individual contributions are tracked through GitHub commits, pull requests, completed tasks, and implementation reviews.
