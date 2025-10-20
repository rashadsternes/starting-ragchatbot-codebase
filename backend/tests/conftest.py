"""
Shared test fixtures and configuration for pytest
"""
import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, MagicMock
from dataclasses import dataclass

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from models import Course, Lesson, CourseChunk, SourceItem
from vector_store import VectorStore, SearchResults
from search_tools import CourseSearchTool, CourseOutlineTool, ToolManager
from ai_generator import AIGenerator


@pytest.fixture
def sample_course():
    """Create a sample course for testing"""
    return Course(
        title="Introduction to Machine Learning",
        course_link="https://example.com/ml-course",
        instructor="Dr. Jane Smith",
        lessons=[
            Lesson(
                lesson_number=1,
                title="What is Machine Learning?",
                lesson_link="https://example.com/ml-course/lesson-1"
            ),
            Lesson(
                lesson_number=2,
                title="Linear Regression Basics",
                lesson_link="https://example.com/ml-course/lesson-2"
            ),
            Lesson(
                lesson_number=3,
                title="Classification Algorithms",
                lesson_link="https://example.com/ml-course/lesson-3"
            )
        ]
    )


@pytest.fixture
def sample_course_chunks(sample_course):
    """Create sample course chunks for testing"""
    return [
        CourseChunk(
            content="Machine learning is a subset of artificial intelligence that enables computers to learn from data without being explicitly programmed.",
            course_title=sample_course.title,
            lesson_number=1,
            chunk_index=0
        ),
        CourseChunk(
            content="Linear regression is a fundamental algorithm used to model the relationship between a dependent variable and one or more independent variables.",
            course_title=sample_course.title,
            lesson_number=2,
            chunk_index=1
        ),
        CourseChunk(
            content="Classification algorithms are used to predict categorical outcomes. Common algorithms include logistic regression, decision trees, and neural networks.",
            course_title=sample_course.title,
            lesson_number=3,
            chunk_index=2
        )
    ]


@pytest.fixture
def temp_chroma_db():
    """Create a temporary ChromaDB directory for testing"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    # Cleanup after test
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def mock_vector_store():
    """Create a mock VectorStore for testing"""
    mock_store = Mock(spec=VectorStore)

    # Setup default search behavior
    mock_store.search.return_value = SearchResults(
        documents=[
            "Machine learning is a subset of artificial intelligence.",
            "Linear regression models relationships between variables."
        ],
        metadata=[
            {"course_title": "Introduction to Machine Learning", "lesson_number": 1, "chunk_index": 0},
            {"course_title": "Introduction to Machine Learning", "lesson_number": 2, "chunk_index": 1}
        ],
        distances=[0.1, 0.2]
    )

    mock_store.get_lesson_link.return_value = "https://example.com/ml-course/lesson-1"
    mock_store._resolve_course_name.return_value = "Introduction to Machine Learning"

    return mock_store


@pytest.fixture
def mock_ai_client():
    """Create a mock Anthropic client for testing"""
    mock_client = Mock()

    # Default response without tool use
    mock_response = Mock()
    mock_response.stop_reason = "end_turn"
    mock_content = Mock()
    mock_content.text = "This is a test response from Claude."
    mock_response.content = [mock_content]

    mock_client.messages.create.return_value = mock_response

    return mock_client


@pytest.fixture
def mock_ai_client_with_tool_use():
    """Create a mock Anthropic client that uses tools"""
    mock_client = Mock()

    # First response with tool use
    tool_response = Mock()
    tool_response.stop_reason = "tool_use"

    # Tool use content block
    tool_block = Mock()
    tool_block.type = "tool_use"
    tool_block.name = "search_course_content"
    tool_block.id = "tool_123"
    tool_block.input = {
        "query": "what is machine learning",
        "course_name": "Introduction to Machine Learning"
    }

    tool_response.content = [tool_block]

    # Final response after tool execution
    final_response = Mock()
    final_response.stop_reason = "end_turn"
    final_content = Mock()
    final_content.text = "Machine learning is a subset of artificial intelligence that enables computers to learn from data."
    final_response.content = [final_content]

    # Mock returns tool use first, then final response
    mock_client.messages.create.side_effect = [tool_response, final_response]

    return mock_client


@pytest.fixture
def mock_ai_client_with_sequential_tool_use():
    """Create a mock Anthropic client that uses tools twice then returns final response"""
    mock_client = Mock()

    # Round 1: First tool use
    first_tool_response = Mock()
    first_tool_response.stop_reason = "tool_use"
    first_tool_block = Mock()
    first_tool_block.type = "tool_use"
    first_tool_block.name = "search_course_content"
    first_tool_block.id = "tool_1"
    first_tool_block.input = {
        "query": "machine learning basics",
        "course_name": "ML Course"
    }
    first_tool_response.content = [first_tool_block]

    # Round 2: Second tool use
    second_tool_response = Mock()
    second_tool_response.stop_reason = "tool_use"
    second_tool_block = Mock()
    second_tool_block.type = "tool_use"
    second_tool_block.name = "search_course_content"
    second_tool_block.id = "tool_2"
    second_tool_block.input = {
        "query": "machine learning applications",
        "course_name": "ML Course",
        "lesson_number": 2
    }
    second_tool_response.content = [second_tool_block]

    # Final: Text response
    final_response = Mock()
    final_response.stop_reason = "end_turn"
    final_content = Mock()
    final_content.text = "Machine learning is used for predictions and pattern recognition."
    final_response.content = [final_content]

    # Mock returns 2 tool uses, then final
    mock_client.messages.create.side_effect = [
        first_tool_response,
        second_tool_response,
        final_response
    ]

    return mock_client


@pytest.fixture
def mock_ai_client_with_early_termination():
    """Create a mock Anthropic client that uses one tool then stops"""
    mock_client = Mock()

    # Round 1: Tool use
    tool_response = Mock()
    tool_response.stop_reason = "tool_use"
    tool_block = Mock()
    tool_block.type = "tool_use"
    tool_block.name = "search_course_content"
    tool_block.id = "tool_1"
    tool_block.input = {"query": "test query"}
    tool_response.content = [tool_block]

    # Round 2: Ends without tool use
    final_response = Mock()
    final_response.stop_reason = "end_turn"
    final_content = Mock()
    final_content.text = "Here's the answer based on the search."
    final_response.content = [final_content]

    # Only 2 API calls (not 3)
    mock_client.messages.create.side_effect = [tool_response, final_response]

    return mock_client


@pytest.fixture
def empty_search_results():
    """Create empty search results for testing"""
    return SearchResults(
        documents=[],
        metadata=[],
        distances=[]
    )


@pytest.fixture
def error_search_results():
    """Create error search results for testing"""
    return SearchResults.empty("No course found matching 'NonexistentCourse'")


@pytest.fixture
def config_with_max_results():
    """Create a config object with proper MAX_RESULTS setting"""
    @dataclass
    class TestConfig:
        ANTHROPIC_API_KEY: str = "test-key"
        ANTHROPIC_MODEL: str = "claude-sonnet-4-20250514"
        EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
        CHUNK_SIZE: int = 800
        CHUNK_OVERLAP: int = 100
        MAX_RESULTS: int = 5  # Proper value, not 0
        MAX_HISTORY: int = 2
        CHROMA_PATH: str = "./test_chroma_db"

    return TestConfig()


@pytest.fixture
def config_with_zero_results():
    """Create a config object with buggy MAX_RESULTS=0 setting"""
    @dataclass
    class BuggyConfig:
        ANTHROPIC_API_KEY: str = "test-key"
        ANTHROPIC_MODEL: str = "claude-sonnet-4-20250514"
        EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
        CHUNK_SIZE: int = 800
        CHUNK_OVERLAP: int = 100
        MAX_RESULTS: int = 0  # BUG: This causes searches to return nothing
        MAX_HISTORY: int = 2
        CHROMA_PATH: str = "./test_chroma_db"

    return BuggyConfig()
