# RAG Chatbot Query Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                 FRONTEND                                     │
│                            (frontend/script.js)                              │
└─────────────────────────────────────────────────────────────────────────────┘

    User types: "What is MCP?"
         │
         ▼
    ┌─────────────────┐
    │ sendMessage()   │  Line 45
    │ - Clear input   │
    │ - Show loading  │
    └────────┬────────┘
             │
             ▼
    ┌──────────────────────────────────┐
    │   POST /api/query                │  Line 63
    │   {                              │
    │     query: "What is MCP?",       │
    │     session_id: "session_1"      │
    │   }                              │
    └────────┬─────────────────────────┘
             │
             │ HTTP Request
             ▼

┌─────────────────────────────────────────────────────────────────────────────┐
│                              BACKEND - API LAYER                             │
│                              (backend/app.py)                                │
└─────────────────────────────────────────────────────────────────────────────┘

    ┌──────────────────────────┐
    │ query_documents()        │  Line 56
    │ - Validate request       │
    │ - Get/create session     │
    └──────────┬───────────────┘
               │
               ▼
    ┌──────────────────────────┐
    │ rag_system.query()       │  Line 66
    └──────────┬───────────────┘
               │
               ▼

┌─────────────────────────────────────────────────────────────────────────────┐
│                          BACKEND - RAG ORCHESTRATOR                          │
│                           (backend/rag_system.py)                            │
└─────────────────────────────────────────────────────────────────────────────┘

    ┌────────────────────────────────────┐
    │ query()                            │  Line 102
    │ 1. Format prompt                   │
    │ 2. Get conversation history ──┐    │
    └────────┬───────────────────────┼────┘
             │                       │
             │                       ▼
             │          ┌──────────────────────────────┐
             │          │ session_manager              │
             │          │ .get_conversation_history()  │  session_manager.py:42
             │          │                              │
             │          │ Returns:                     │
             │          │ "User: previous Q\n          │
             │          │  Assistant: previous A"      │
             │          └──────────────┬───────────────┘
             │                         │
             ▼◄────────────────────────┘
    ┌────────────────────────────────────┐
    │ ai_generator.generate_response()   │  Line 122
    │ - Query                            │
    │ - History                          │
    │ - Tools (search_course_content)    │
    │ - Tool manager                     │
    └────────┬───────────────────────────┘
             │
             ▼

┌─────────────────────────────────────────────────────────────────────────────┐
│                          BACKEND - AI GENERATOR                              │
│                          (backend/ai_generator.py)                           │
└─────────────────────────────────────────────────────────────────────────────┘

    ┌──────────────────────────────────┐
    │ generate_response()              │  Line 43
    │                                  │
    │ 1. Build system prompt:          │
    │    - Educational assistant role  │
    │    - Conversation history        │
    │                                  │
    │ 2. Prepare API call:             │
    │    - Model: Claude Sonnet 4      │
    │    - Temperature: 0              │
    │    - Max tokens: 800             │
    │    - Tools: [search tool]        │
    └──────────┬───────────────────────┘
               │
               ▼
    ┌──────────────────────────────────┐
    │  Anthropic API Call              │  Line 80
    │  client.messages.create()        │
    └──────────┬───────────────────────┘
               │
               ▼
         ┌─────────────────────────────────────┐
         │                                     │
    ┌────▼─────────────┐         ┌────────────▼──────────┐
    │ Direct Answer    │         │ Tool Use Required     │
    │ (general Q)      │         │ (course-specific Q)   │
    │                  │         │                       │
    │ Return text ─────┼──┐      │ stop_reason:          │
    │                  │  │      │ "tool_use"            │
    └──────────────────┘  │      └──────┬────────────────┘
                          │             │
                          │             ▼
                          │  ┌──────────────────────────┐
                          │  │ _handle_tool_execution() │  Line 89
                          │  │                          │
                          │  │ Claude says:             │
                          │  │ "I'll use the search     │
                          │  │  tool with query='MCP'"  │
                          │  └──────┬───────────────────┘
                          │         │
                          │         ▼

┌─────────────────────────────────────────────────────────────────────────────┐
│                          BACKEND - TOOL EXECUTION                            │
│                          (backend/search_tools.py)                           │
└─────────────────────────────────────────────────────────────────────────────┘

                          ┌──────────────────────────────┐
                          │ tool_manager.execute_tool()  │  Line 135
                          │                              │
                          │ Tool: "search_course_content"│
                          │ Params: {                    │
                          │   query: "MCP",              │
                          │   course_name: null,         │
                          │   lesson_number: null        │
                          │ }                            │
                          └──────┬───────────────────────┘
                                 │
                                 ▼
                          ┌──────────────────────────────┐
                          │ CourseSearchTool.execute()   │  Line 52
                          │                              │
                          │ Call vector_store.search()   │
                          └──────┬───────────────────────┘
                                 │
                                 ▼

┌─────────────────────────────────────────────────────────────────────────────┐
│                          BACKEND - VECTOR STORE                              │
│                          (backend/vector_store.py)                           │
└─────────────────────────────────────────────────────────────────────────────┘

    ┌────────────────────────────────────────────────────────────┐
    │ search()                                        Line 61    │
    │                                                            │
    │ ┌────────────────────────────────────────────────────────┐ │
    │ │ Step 1: Resolve Course Name (if provided)             │ │
    │ │ ───────────────────────────────────────               │ │
    │ │ If course_name = "MCP intro":                         │ │
    │ │   • Query course_catalog collection                   │ │
    │ │   • Semantic search for best match                    │ │
    │ │   • Return: "Introduction to MCP"                     │ │
    │ └────────────────────────────────────────────────────────┘ │
    │                                                            │
    │ ┌────────────────────────────────────────────────────────┐ │
    │ │ Step 2: Build Metadata Filter                Line 86  │ │
    │ │ ─────────────────────────────                         │ │
    │ │ Examples:                                             │ │
    │ │   • Course only: {course_title: "Intro to MCP"}       │ │
    │ │   • Lesson only: {lesson_number: 2}                   │ │
    │ │   • Both: {$and: [{course_title: ...}, {lesson_..}]}  │ │
    │ └────────────────────────────────────────────────────────┘ │
    │                                                            │
    │ ┌────────────────────────────────────────────────────────┐ │
    │ │ Step 3: Semantic Search in ChromaDB       Line 93     │ │
    │ │ ────────────────────────────────────                  │ │
    │ │                                                        │ │
    │ │   ┌──────────────────────────────────┐                │ │
    │ │   │  course_content collection       │                │ │
    │ │   │  ───────────────────────────     │                │ │
    │ │   │  • Query: "MCP"                  │                │ │
    │ │   │  • Embedding: all-MiniLM-L6-v2   │                │ │
    │ │   │  • Filter: (metadata filters)    │                │ │
    │ │   │  • n_results: 5                  │                │ │
    │ │   └──────────────┬───────────────────┘                │ │
    │ │                  │                                    │ │
    │ │                  ▼                                    │ │
    │ │   ┌──────────────────────────────────┐                │ │
    │ │   │ Returns: Top 5 Similar Chunks    │                │ │
    │ │   │ ────────────────────────────     │                │ │
    │ │   │ Chunk 1: [Course A, Lesson 1]    │                │ │
    │ │   │   "MCP stands for Model..."      │                │ │
    │ │   │                                  │                │ │
    │ │   │ Chunk 2: [Course A, Lesson 2]    │                │ │
    │ │   │   "MCP allows you to..."         │                │ │
    │ │   │                                  │                │ │
    │ │   │ Chunk 3: [Course B, Lesson 1]    │                │ │
    │ │   │   "Using MCP, you can..."        │                │ │
    │ │   └──────────────────────────────────┘                │ │
    │ └────────────────────────────────────────────────────────┘ │
    └──────────────────┬─────────────────────────────────────────┘
                       │
                       ▼
         ┌─────────────────────────────┐
         │ Return SearchResults        │
         │ - documents: [chunk texts]  │
         │ - metadata: [course, lesson]│
         │ - distances: [similarities] │
         └─────────────┬───────────────┘
                       │
                       ▼

┌─────────────────────────────────────────────────────────────────────────────┐
│                       BACK TO TOOL EXECUTION                                 │
└─────────────────────────────────────────────────────────────────────────────┘

         ┌─────────────────────────────────────┐
         │ CourseSearchTool._format_results()  │  search_tools.py:88
         │                                     │
         │ Format each chunk:                  │
         │ ┌─────────────────────────────────┐ │
         │ │ [Course A - Lesson 1]           │ │
         │ │ MCP stands for Model...         │ │
         │ │                                 │ │
         │ │ [Course A - Lesson 2]           │ │
         │ │ MCP allows you to...            │ │
         │ │                                 │ │
         │ │ [Course B - Lesson 1]           │ │
         │ │ Using MCP, you can...           │ │
         │ └─────────────────────────────────┘ │
         │                                     │
         │ Track sources:                      │
         │ ["Course A - Lesson 1",             │
         │  "Course A - Lesson 2",             │
         │  "Course B - Lesson 1"]             │
         └─────────────┬───────────────────────┘
                       │
                       ▼

┌─────────────────────────────────────────────────────────────────────────────┐
│                       BACK TO AI GENERATOR                                   │
└─────────────────────────────────────────────────────────────────────────────┘

         ┌─────────────────────────────────────┐
         │ _handle_tool_execution()            │  ai_generator.py:116
         │                                     │
         │ Package tool result:                │
         │ {                                   │
         │   type: "tool_result",              │
         │   tool_use_id: "toolu_xxx",         │
         │   content: "[Course A - Lesson 1]   │
         │             MCP stands for..."      │
         │ }                                   │
         └─────────────┬───────────────────────┘
                       │
                       ▼
         ┌─────────────────────────────────────┐
         │ Second Claude API Call              │  Line 134
         │                                     │
         │ Messages:                           │
         │ 1. User: "What is MCP?"             │
         │ 2. Assistant: [tool_use request]    │
         │ 3. User: [tool_result with chunks]  │
         │                                     │
         │ Claude synthesizes answer:          │
         │ "MCP (Model Context Protocol) is    │
         │  a framework that allows..."        │
         └─────────────┬───────────────────────┘
                       │
                       ▼
         ┌─────────────────────────────────────┐
         │ Return final answer text            │  Line 135
         └─────────────┬───────────────────────┘
                       │
                       ▼

┌─────────────────────────────────────────────────────────────────────────────┐
│                       BACK TO RAG ORCHESTRATOR                               │
└─────────────────────────────────────────────────────────────────────────────┘

         ┌─────────────────────────────────────┐
         │ query() - Cleanup                   │  rag_system.py:129
         │                                     │
         │ 1. Get sources from tool manager    │
         │    sources = ["Course A - Lesson 1",│
         │               "Course A - Lesson 2",│
         │               "Course B - Lesson 1"]│
         │                                     │
         │ 2. Reset tool sources               │
         │                                     │
         │ 3. Save to session history:         │
         │    session_manager.add_exchange()   │
         │      User: "What is MCP?"           │
         │      Assistant: "MCP is a..."       │
         └─────────────┬───────────────────────┘
                       │
                       ▼
         ┌─────────────────────────────────────┐
         │ Return (answer, sources)            │  Line 140
         └─────────────┬───────────────────────┘
                       │
                       ▼

┌─────────────────────────────────────────────────────────────────────────────┐
│                           BACK TO API LAYER                                  │
└─────────────────────────────────────────────────────────────────────────────┘

         ┌─────────────────────────────────────┐
         │ query_documents()                   │  app.py:68
         │                                     │
         │ Return QueryResponse:               │
         │ {                                   │
         │   answer: "MCP is a...",            │
         │   sources: ["Course A - Lesson 1",  │
         │             "Course A - Lesson 2",  │
         │             "Course B - Lesson 1"], │
         │   session_id: "session_1"           │
         │ }                                   │
         └─────────────┬───────────────────────┘
                       │
                       │ JSON Response
                       ▼

┌─────────────────────────────────────────────────────────────────────────────┐
│                           BACK TO FRONTEND                                   │
└─────────────────────────────────────────────────────────────────────────────┘

         ┌─────────────────────────────────────┐
         │ sendMessage() - Handle Response     │  script.js:76
         │                                     │
         │ 1. Parse JSON                       │
         │ 2. Update session_id                │
         │ 3. Remove loading indicator         │
         └─────────────┬───────────────────────┘
                       │
                       ▼
         ┌─────────────────────────────────────┐
         │ addMessage()                        │  Line 113
         │                                     │
         │ 1. Convert markdown → HTML          │
         │    (using marked.js)                │
         │                                     │
         │ 2. Create message div:              │
         │    ┌───────────────────────────┐    │
         │    │ MCP is a framework that   │    │
         │    │ allows AI assistants to   │    │
         │    │ connect to external tools │    │
         │    │                           │    │
         │    │ ▼ Sources                 │    │
         │    │   Course A - Lesson 1,    │    │
         │    │   Course A - Lesson 2,    │    │
         │    │   Course B - Lesson 1     │    │
         │    └───────────────────────────┘    │
         │                                     │
         │ 3. Append to chat                   │
         │ 4. Scroll to bottom                 │
         └─────────────────────────────────────┘

═════════════════════════════════════════════════════════════════════════════
                            USER SEES ANSWER
═════════════════════════════════════════════════════════════════════════════


┌─────────────────────────────────────────────────────────────────────────────┐
│                          KEY COMPONENTS SUMMARY                              │
└─────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────┐
│ SessionManager       │  Tracks conversation history (last 2 exchanges)
└──────────────────────┘

┌──────────────────────┐
│ ChromaDB Collections │  • course_catalog: Course metadata
│                      │  • course_content: Document chunks (embedded)
└──────────────────────┘

┌──────────────────────┐
│ Embedding Model      │  all-MiniLM-L6-v2 (384 dimensions)
└──────────────────────┘

┌──────────────────────┐
│ AI Model             │  Claude Sonnet 4 (Temperature: 0, Max: 800 tokens)
└──────────────────────┘

┌──────────────────────┐
│ Tool                 │  search_course_content(query, course_name?, lesson_number?)
└──────────────────────┘


TIMING BREAKDOWN:
─────────────────
1. Frontend → Backend:          ~50ms   (HTTP request)
2. Session lookup:               ~1ms    (in-memory)
3. First Claude API call:        ~500ms  (decides to use tool)
4. Course name resolution:       ~10ms   (if needed)
5. Vector search (ChromaDB):     ~50ms   (semantic search)
6. Format results:               ~1ms
7. Second Claude API call:       ~800ms  (synthesize answer)
8. Save session + return:        ~2ms
9. Backend → Frontend:           ~50ms   (HTTP response)
10. Render in browser:           ~10ms   (markdown → HTML)

TOTAL: ~1.5 seconds (typical query with tool use)
```
