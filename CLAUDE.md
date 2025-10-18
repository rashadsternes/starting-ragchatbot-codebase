# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Retrieval-Augmented Generation (RAG) chatbot system for querying course materials. The system uses ChromaDB for vector storage, Anthropic's Claude API with tool calling for AI generation, and provides a web interface for user interaction.

## Development Commands

**IMPORTANT**: This project uses `uv` as the package manager. Always use `uv` for running Python commands - do NOT use `pip` or run Python scripts directly.

### Setup
```bash
# Install dependencies (uses uv.lock)
uv sync

# Create .env file with your Anthropic API key
cp .env.example .env
# Then edit .env to add: ANTHROPIC_API_KEY=your-key-here
```

### Running the Application
```bash
# Quick start (recommended)
./run.sh

# Manual start - ALWAYS use 'uv run'
cd backend && uv run uvicorn app:app --reload --port 8000

# Access points:
# - Web UI: http://localhost:8000
# - API docs: http://localhost:8000/docs
```

### Running Python Scripts and Files
```bash
# Always use 'uv run' to execute any Python file
uv run python script.py
uv run python backend/app.py

# For module execution
uv run python -m module_name

# Running uvicorn (as used in this project)
uv run uvicorn app:app --reload --port 8000

# NEVER run Python directly without uv:
# NOT: python script.py
# NOT: python backend/app.py
# NOT: python -m uvicorn app:app
```

**Critical**: Every Python execution command must be prefixed with `uv run`. This ensures the correct virtual environment and dependencies are used.

### Managing Dependencies
```bash
# Add a new dependency
uv add package-name

# Add a development dependency
uv add --dev package-name

# Remove a dependency
uv remove package-name

# Update dependencies
uv sync

# NOT: pip install package
# NOT: pip uninstall package
# NOT: pip freeze > requirements.txt
```

All dependencies are managed in `pyproject.toml` and locked in `uv.lock`. Never modify these files manually - always use `uv add` and `uv remove` commands.

### Requirements
- Python 3.13+
- uv package manager (do NOT use pip directly - always use uv for all Python operations)
- Anthropic API key

## Architecture Overview

### Request Flow
User query follows this path through the system:

1. **Frontend** (`frontend/script.js`) → POST to `/api/query` with `{query, session_id}`
2. **API Layer** (`backend/app.py`) → Validates request, creates/retrieves session
3. **RAG Orchestrator** (`backend/rag_system.py`) → Coordinates all components:
   - Retrieves conversation history from SessionManager
   - Calls AIGenerator with tools and history
4. **AI Generator** (`backend/ai_generator.py`) → Makes Claude API call
   - If Claude decides to search: triggers tool execution flow
   - If general question: returns direct answer
5. **Tool Execution** (when needed):
   - `search_tools.py` → CourseSearchTool executes
   - `vector_store.py` → Performs semantic search in ChromaDB:
     - Resolves partial course names to exact titles (semantic matching)
     - Builds metadata filters (course_title, lesson_number)
     - Searches course_content collection for top 5 chunks
   - Results formatted and sent back to Claude
   - Claude synthesizes final answer from search results
6. **Response** → Sources extracted, conversation saved to session, returned to frontend

### Core Components

**RAGSystem** (`rag_system.py`)
- Central orchestrator coordinating all components
- Key methods:
  - `add_course_folder()`: Batch loads course documents from `/docs`
  - `query()`: Main pipeline that handles tool-based search
  - `get_course_analytics()`: Returns course statistics

**VectorStore** (`vector_store.py`)
- Two ChromaDB collections:
  - `course_catalog`: Course metadata (for semantic course name resolution)
  - `course_content`: Document chunks with embeddings
- `search()` method is the main interface with three-step process:
  1. Resolve course name via semantic search (if provided)
  2. Build metadata filter
  3. Semantic search in course_content
- Embedding model: `all-MiniLM-L6-v2` (384 dimensions)

**AIGenerator** (`ai_generator.py`)
- Handles Claude API interactions with tool calling
- Uses Claude Sonnet 4 (model ID in `config.py`)
- System prompt defines educational assistant behavior
- `_handle_tool_execution()`: Multi-turn conversation for tool use
  1. Claude requests tool use
  2. Tool executes and returns results
  3. Claude receives results and synthesizes answer

**SessionManager** (`session_manager.py`)
- Tracks conversation history per session (in-memory)
- Maintains last 2 exchanges (4 messages) per session
- History injected into system prompt for context

**DocumentProcessor** (`document_processor.py`)
- Parses structured course documents
- Creates chunks with sentence-based splitting (800 chars, 100 overlap)
- Extracts course metadata and lesson information

**Search Tools** (`search_tools.py`)
- Defines `search_course_content` tool for Claude
- Parameters: `query` (required), `course_name` (optional), `lesson_number` (optional)
- Tracks sources for UI display

### Data Models (`models.py`)
- `Course`: Contains title, instructor, course_link, lessons
- `Lesson`: lesson_number, title, lesson_link
- `CourseChunk`: content, course_title, lesson_number, chunk_index

### Configuration (`config.py`)
All system settings centralized here:
- `ANTHROPIC_MODEL`: Claude Sonnet 4 model ID
- `EMBEDDING_MODEL`: all-MiniLM-L6-v2
- `CHUNK_SIZE`: 800 characters
- `CHUNK_OVERLAP`: 100 characters
- `MAX_RESULTS`: 5 search results
- `MAX_HISTORY`: 2 conversation exchanges
- `CHROMA_PATH`: ./chroma_db (persisted to disk)

## Adding Course Documents

Course documents must follow this specific format in `/docs`:

```
Course Title: [Title]
Course Link: [URL]
Course Instructor: [Name]

Lesson 0: [Lesson Title]
Lesson Link: [URL]
[Lesson content...]

Lesson 1: [Next Lesson Title]
Lesson Link: [URL]
[Lesson content...]
```

Supported file types: `.txt`, `.pdf`, `.docx`

Documents are automatically loaded on server startup. The system:
- Checks for existing courses to avoid duplicates
- Parses metadata headers
- Chunks content with sentence-based splitting
- Stores in ChromaDB with embeddings

## Key Implementation Details

**Tool Calling Flow**
- Claude has access to ONE tool: `search_course_content`
- When user asks course-specific questions, Claude autonomously decides to use the tool
- Tool execution happens synchronously within the request
- Sources tracked separately and returned alongside the answer

**Session Management**
- Sessions created on first query (returns session_id)
- Subsequent queries include session_id to maintain context
- History format: `"User: question\nAssistant: answer\n..."`
- Limited to last 2 exchanges to control token usage

**Vector Search Strategy**
- Course name resolution uses semantic matching (partial names like "MCP" work)
- Filters applied as ChromaDB `where` clauses
- Top 5 chunks returned by default
- Results include metadata: course_title, lesson_number, chunk_index

**ChromaDB Collections**
- `course_catalog`: IDs are course titles, documents are titles (for semantic search)
- `course_content`: IDs are `{course_title}_{chunk_index}`, documents are chunk content
- Both use same embedding function (SentenceTransformer)

## Frontend Architecture

Simple vanilla JavaScript with no framework:
- Global session tracking
- Fetch API for async HTTP
- Marked.js for markdown rendering
- Collapsible sources display
- Loading indicators during API calls

The frontend is served as static files by FastAPI from the `/frontend` directory.
