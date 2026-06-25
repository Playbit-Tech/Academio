# SchoolCare v3 — AI Service Architecture

---

## 1. AI LAYER OVERVIEW

```
┌─────────────────────────────────────────────────────────────────────┐
│                        AI GATEWAY                                    │
│                                                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │
│  │  OpenAI      │  │  Anthropic   │  │  Open Source  │               │
│  │  GPT-4o/o1  │  │  Claude 4    │  │  (Llama/Mistral)              │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘               │
│         │                 │                  │                        │
│         └────────┬────────┴──────────────────┘                        │
│                  ▼                                                     │
│         ┌────────────────┐                                            │
│         │  Model Router  │  ← Task routing (cost/quality optimization)│
│         └───────┬────────┘                                            │
│                 │                                                      │
│    ┌────────────┼────────────┬────────────┬────────────┐              │
│    ▼            ▼            ▼            ▼            ▼              │
│ ┌──────┐  ┌──────────┐  ┌────────┐  ┌────────┐  ┌─────────┐        │
│ │ RAG  │  │  Agents  │  │ Search │  │ Stream │  │ Batch   │        │
│ │Engine│  │Framework │  │ Engine │  │ (SSE)  │  │ Process │        │
│ └──┬───┘  └────┬─────┘  └───┬────┘  └────────┘  └─────────┘        │
│    │           │             │                                        │
│    ▼           ▼             ▼                                        │
│ ┌──────┐  ┌─────────┐  ┌────────┐                                    │
│ │Vector│  │  Agent  │  │ Search │                                    │
│ │ DB   │  │  Runner │  │ Index  │                                    │
│ └──────┘  └─────────┘  └────────┘                                    │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. AI USE CASES BY DOMAIN

### 2.1 Student AI Assistant
| Feature | Model | Mechanism | Context |
|---------|-------|-----------|---------|
| Homework Help | GPT-4o/Claude 4 | RAG + curriculum context | Student's subjects, level, curriculum |
| Subject Tutoring | GPT-4o | Conversational agent | Student's performance data, weak areas |
| Study Plans | GPT-4o | Structured generation | Exam schedule, subjects, performance |
| Academic Guidance | Claude 4 | RAG + policy context | School policies, graduation requirements |
| Performance Coaching | GPT-4o-mini | Analysis + recommendations | Grades, attendance, trends |

### 2.2 Teacher AI Assistant
| Feature | Model | Mechanism | Context |
|---------|-------|-----------|---------|
| Lesson Planning | GPT-4o | Structured generation | Subject, level, curriculum, duration |
| Question Generation | GPT-4o | RAG + curriculum | Subject, topic, difficulty, question type |
| Rubric Creation | GPT-4o | Template-based | Assessment type, criteria, grade levels |
| Marking Assistance | GPT-4o/Claude 4 | Image + text analysis | Student answers, rubric |
| Classroom Insights | Claude 4 | Pattern analysis | Attendance, grades, engagement data |

### 2.3 Parent AI Assistant
| Feature | Model | Mechanism | Context |
|---------|-------|-----------|---------|
| Performance Summary | GPT-4o-mini | Data synthesis | Grades, attendance, behavior trends |
| Attendance Insights | GPT-4o-mini | Pattern analysis | Attendance records, patterns |
| Recommendations | GPT-4o | RAG + best practices | Student profile, areas for improvement |

### 2.4 Career Guidance Engine
| Feature | Model | Mechanism | Context |
|---------|-------|-----------|---------|
| Career Recommendations | GPT-4o | RAG + career database | Skills, interests, academic performance |
| University Matching | GPT-4o | RAG + university data | Grades, preferences, location |
| Skills Assessment | GPT-4o-mini | Rubric-based evaluation | Subject performance, extracurricular |
| Scholarship Matching | Claude 4 | RAG + scholarship DB | Profile, needs, eligibility criteria |
| Career Roadmap | GPT-4o | Structured generation | Career path, milestones, timeline |

### 2.5 Enrollment Forecasting Engine
| Feature | Model | Mechanism | Context |
|---------|-------|-----------|---------|
| Enrollment Growth | Claude 4 | Time series analysis | Historical data, demographics, trends |
| Conversion Rates | GPT-4o-mini | Funnel analysis | Application stages, drop-off points |
| Revenue Projects | GPT-4o-mini | Calculation + analysis | Fee structures, enrollment projections |
| Capacity Planning | GPT-4o | Scenario modeling | Current capacity, growth projections |

### 2.6 Risk Monitoring
| Feature | Model | Mechanism | Context |
|---------|-------|-----------|---------|
| At-Risk Detection | Claude 4 | Multi-factor analysis | Grades, attendance, behavior, fees |
| Intervention Plans | GPT-4o | Structured generation | Risk factors, student profile, resources |
| Early Warning | GPT-4o-mini | Threshold + AI analysis | Real-time data streams |

### 2.7 Natural Language Search
| Feature | Model | Mechanism | Context |
|---------|-------|-----------|---------|
| Query Parsing | GPT-4o-mini | NL → SQL/Filter | Schema context, user role, permissions |
| Result Explanation | GPT-4o-mini | Summarization | Query results, context |
| Search Suggestions | GPT-4o-mini | Embedding similarity | User history, popular queries |

---

## 3. RAG ARCHITECTURE

```
┌─────────────────────────────────────────────────────────────────┐
│                  RAG ENGINE                                       │
│                                                                  │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐                   │
│  │ Document │    │ Chunk &  │    │ Generate │                   │
│  │ Ingest   │───►│ Embed    │───►│ Embedding│                   │
│  └──────────┘    └──────────┘    └────┬─────┘                   │
│                                        │                         │
│                                        ▼                         │
│                               ┌──────────────┐                   │
│                               │  Vector DB    │                   │
│                               │  (Qdrant)     │                   │
│                               └──────────────┘                   │
│                                                                  │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐                   │
│  │ User     │    │ Embed    │    │ Semantic │                   │
│  │ Query    │───►│ Query    │───►│ Search   │                   │
│  └──────────┘    └──────────┘    └────┬─────┘                   │
│                                        │                         │
│                                        ▼                         │
│                               ┌──────────────┐                   │
│                               │  Context +    │                   │
│                               │  Query → LLM  │                   │
│                               └──────┬───────┘                   │
│                                      │                           │
│                                      ▼                           │
│                               ┌──────────────┐                   │
│                               │   Response    │                   │
│                               └──────────────┘                   │
└─────────────────────────────────────────────────────────────────┘
```

### Document Sources for RAG
```
Academic Curriculum      → Curriculum documents, syllabi
School Policies          → Rules, code of conduct, academic policies
FAQ                      → Common questions and answers
Subject Matter           → Textbooks, reference materials
Carrer Database          → Career paths, university info, scholarships
Previous Exam Questions  → Past questions, marking schemes
Institutional Knowledge  → School history, programs, achievements
```

---

## 4. AI AGENT FRAMEWORK

```
┌─────────────────────────────────────────────────────────────────┐
│                     AI AGENT FRAMEWORK                           │
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐       │
│  │ Agent Config │    │   Context    │    │  Tools        │       │
│  │ (Role, Goal) │    │ (Memory, RAG)│    │ (APIs, DB)    │       │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘       │
│         │                   │                   │                │
│         └───────────────────┼───────────────────┘                │
│                             ▼                                    │
│                    ┌────────────────┐                            │
│                    │  Agent Runner   │                            │
│                    │  (LangChain)    │                            │
│                    │                 │                            │
│                    │  Plan → Act →   │                            │
│                    │  Observe →      │                            │
│                    │  Reflect         │                            │
│                    └────────────────┘                            │
│                             │                                    │
│                             ▼                                    │
│                    ┌────────────────┐                            │
│                    │   Output        │                            │
│                    │   (Response/    │                            │
│                    │    Action)       │                            │
│                    └────────────────┘                            │
└─────────────────────────────────────────────────────────────────┘
```

### Agent Types
```
┌─────────────────┬────────────────────┬──────────────────────┐
│ Agent           │ Triggers           │ Tools Available       │
├─────────────────┼────────────────────┼──────────────────────┤
│ Academic Tutor  │ Student homework   │ RAG, DB query,       │
│                 │ question           │ curriculum lookup     │
├─────────────────┼────────────────────┼──────────────────────┤
│ Lesson Planner  │ Teacher request    │ RAG, curriculum DB,  │
│                 │                    │ timetable, resources  │
├─────────────────┼────────────────────┼──────────────────────┤
│ Question Gen    │ Teacher request +  │ RAG, question bank,  │
│                 │ topic              │ curriculum            │
├─────────────────┼────────────────────┼──────────────────────┤
│ Essay Grader    │ Submission alert   │ RAG (rubric),        │
│                 │                    │ submission DB         │
├─────────────────┼────────────────────┼──────────────────────┤
│ Risk Analyzer   │ Scheduled/event    │ Student DB, grades,  │
│                 │ driven             │ attendance, behavior  │
├─────────────────┼────────────────────┼──────────────────────┤
│ Career Guide    │ Student request    │ RAG, career DB,      │
│                 │                    │ alumni DB            │
├─────────────────┼────────────────────┼──────────────────────┤
│ Enrollment      │ Monthly schedule   │ Historical data,     │
│ Forecaster      │                    │ trend analysis       │
├─────────────────┼────────────────────┼──────────────────────┤
│ NL Search       │ User search query  │ Schema-aware DB      │
│                 │                    │ query, vector search  │
└─────────────────┴────────────────────┴──────────────────────┘
```

---

## 5. NL → SEARCH ENGINE

```
User Query: "Show students with attendance below 70%"
                     │
                     ▼
┌───────────────────────────────────────────────┐
│ 1. NL Parser (GPT-4o-mini)                    │
│    Context: User role, school schema,          │
│    permissions                                 │
│    Output: Structured intent                   │
│    {                                           │
│      intent: "query_students",                 │
│      filters: [{                               │
│        field: "attendance_percentage",         │
│        operator: "lt",                         │
│        value: 70                               │
│      }],                                       │
│      sort: "attendance_percentage asc"         │
│    }                                           │
└──────────────────────┬────────────────────────┘
                       ▼
┌───────────────────────────────────────────────┐
│ 2. Query Builder                               │
│    Converts intent → Safe SQL/GORM query       │
│    Applies tenant isolation                    │
│    Applies role-based row filtering            │
│    Output: GORM query + params                 │
└──────────────────────┬────────────────────────┘
                       ▼
┌───────────────────────────────────────────────┐
│ 3. Query Executor                              │
│    Executes query with timeout                 │
│    Paginates results                           │
│    Returns data + metadata                     │
└──────────────────────┬────────────────────────┘
                       ▼
┌───────────────────────────────────────────────┐
│ 4. Response Formatter                          │
│    Option A: Raw data (API)                    │
│    Option B: AI summary (dashboard)            │
│    "Found 23 students with attendance below    │
│     70%. 15 are in SS2, 8 in SS1. Average     │
│     attendance is 62%."                        │
└───────────────────────────────────────────────┘
```

---

## 6. AI COST OPTIMIZATION

### Model Routing Strategy

| Task Complexity | Model | Cost | When |
|----------------|-------|------|------|
| Simple | GPT-4o-mini | $0.15/1M tokens | Summaries, simple Q&A, data extraction |
| Medium | GPT-4o | $2.50/1M tokens | Tutoring, lesson planning, essay grading |
| Complex | Claude 4 | $3.00/1M tokens | Risk analysis, career guidance, deep reasoning |
| Batch | Claude 4 Batch | 50% discount | Report generation, bulk analysis |
| Embedding | text-embedding-3-small | $0.02/1M tokens | All vector embeddings |

### Caching Strategy
```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│ Prompt Cache │    │ Response     │    │ Embedding    │
│ (Redis)      │───►│ Cache (Redis)│───►│ Cache        │
│              │    │ (semantic    │    │ (Vector DB)  │
│              │    │  similarity) │    │              │
└──────────────┘    └──────────────┘    └──────────────┘

- Identical prompts: Return cached response (TTL based on context freshness)
- Similar prompts (>95% semantic similarity): Return cached response
- Frequent embeddings: Stored permanently in Qdrant
```

### Rate Limiting & Quotas
- Per-tenant per-day token limits
- Per-user per-minute request limits
- Different limits for different AI features (tutoring > search)
- Over-quota → queue for batch processing
- Enterprise: dedicated model deployment

---

## 7. AI SERVICE IMPLEMENTATION (internal/ai/)

```
internal/ai/
├── gateway.go              # AI provider abstraction interface
├── openai.go               # OpenAI provider implementation
├── anthropic.go            # Anthropic provider implementation
├── model_router.go         # Routes requests to optimal model
│
├── rag/
│   ├── engine.go           # RAG pipeline (query → retrieve → augment → generate)
│   ├── chunker.go          # Document chunking strategies
│   ├── embedder.go         # Text embedding generation
│   └── retriever.go        # Vector search retrieval
│
├── agents/
│   ├── base.go             # Base agent interface
│   ├── runner.go           # Agent execution loop
│   ├── academic_tutor.go   # Student tutoring agent
│   ├── lesson_planner.go   # Teacher lesson planning agent
│   ├── question_generator.go # Question generation agent
│   ├── essay_grader.go     # Essay grading agent
│   ├── risk_analyzer.go    # Student risk analysis agent
│   ├── career_guide.go     # Career guidance agent
│   ├── enrollment_forecaster.go # Enrollment prediction agent
│   ├── parent_summarizer.go # Parent report generation agent
│   └── search_agent.go     # Natural language search agent
│
├── search/
│   ├── engine.go           # NL search pipeline
│   ├── parser.go           # Natural language → structured query
│   ├── query_builder.go    # Structured query → GORM/SQL
│   └── formatter.go        # Results → human-readable format
│
├── prompts/
│   ├── templates.go        # Go-embedded prompt templates
│   ├── templates.yaml      # Externalized prompt templates
│   └── manager.go          # Prompt template manager
│
├── conversation/
│   ├── store.go            # Conversation persistence
│   └── context.go          # Context window management
│
├── cache/
│   ├── response_cache.go   # Semantic response caching
│   └── embedding_cache.go  # Embedding cache
│
└── metrics/
    ├── tracker.go           # Token usage tracking
    └── cost.go              # Cost calculation
```
