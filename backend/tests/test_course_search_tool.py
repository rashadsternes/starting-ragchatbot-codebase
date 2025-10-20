"""
Tests for CourseSearchTool functionality
"""
import pytest
from pathlib import Path
import sys
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).parent.parent))

from search_tools import CourseSearchTool, ToolManager
from vector_store import SearchResults
from models import SourceItem


class TestCourseSearchToolExecute:
    """Test CourseSearchTool.execute() method outputs"""

    def test_execute_with_valid_query_returns_formatted_results(self, mock_vector_store):
        """Test that execute() returns properly formatted results for valid queries"""
        tool = CourseSearchTool(mock_vector_store)

        # Execute search
        result = tool.execute(query="what is machine learning")

        # Should return formatted string
        assert isinstance(result, str), "Should return string"
        assert len(result) > 0, "Should return non-empty result"
        assert "Machine learning" in result or "machine learning" in result.lower(), "Should contain query-related content"

    def test_execute_with_course_filter(self, mock_vector_store):
        """Test execute() with course_name parameter"""
        tool = CourseSearchTool(mock_vector_store)

        # Execute search with course filter
        result = tool.execute(
            query="regression",
            course_name="Introduction to Machine Learning"
        )

        # Should pass course_name to vector store search
        mock_vector_store.search.assert_called_once()
        call_args = mock_vector_store.search.call_args
        assert call_args[1]["course_name"] == "Introduction to Machine Learning"
        assert isinstance(result, str), "Should return string result"

    def test_execute_with_lesson_filter(self, mock_vector_store):
        """Test execute() with lesson_number parameter"""
        tool = CourseSearchTool(mock_vector_store)

        # Execute search with lesson filter
        result = tool.execute(
            query="classification",
            lesson_number=3
        )

        # Should pass lesson_number to vector store search
        mock_vector_store.search.assert_called_once()
        call_args = mock_vector_store.search.call_args
        assert call_args[1]["lesson_number"] == 3
        assert isinstance(result, str), "Should return string result"

    def test_execute_with_both_filters(self, mock_vector_store):
        """Test execute() with both course_name and lesson_number"""
        tool = CourseSearchTool(mock_vector_store)

        # Execute search with both filters
        result = tool.execute(
            query="algorithms",
            course_name="Machine Learning",
            lesson_number=2
        )

        # Should pass both filters to vector store
        mock_vector_store.search.assert_called_once()
        call_args = mock_vector_store.search.call_args
        assert call_args[1]["course_name"] == "Machine Learning"
        assert call_args[1]["lesson_number"] == 2

    def test_execute_with_empty_results(self, mock_vector_store):
        """Test execute() when no results are found"""
        # Configure mock to return empty results
        mock_vector_store.search.return_value = SearchResults(
            documents=[],
            metadata=[],
            distances=[]
        )

        tool = CourseSearchTool(mock_vector_store)
        result = tool.execute(query="nonexistent topic")

        # Should return appropriate message
        assert isinstance(result, str), "Should return string"
        assert "No relevant content found" in result, "Should indicate no content found"

    def test_execute_with_empty_results_includes_filter_info(self, mock_vector_store):
        """Test that empty results message includes filter information"""
        # Configure mock to return empty results
        mock_vector_store.search.return_value = SearchResults(
            documents=[],
            metadata=[],
            distances=[]
        )

        tool = CourseSearchTool(mock_vector_store)

        # With course filter
        result = tool.execute(query="test", course_name="TestCourse")
        assert "TestCourse" in result, "Should mention course name in error"

        # With lesson filter
        result = tool.execute(query="test", lesson_number=5)
        assert "lesson 5" in result.lower(), "Should mention lesson number in error"

    def test_execute_with_error_returns_error_message(self, mock_vector_store):
        """Test execute() when search returns an error"""
        # Configure mock to return error
        mock_vector_store.search.return_value = SearchResults.empty(
            "No course found matching 'NonexistentCourse'"
        )

        tool = CourseSearchTool(mock_vector_store)
        result = tool.execute(query="test", course_name="NonexistentCourse")

        # Should return the error message
        assert isinstance(result, str), "Should return string"
        assert "No course found" in result, "Should contain error message"

    def test_execute_formats_results_with_course_context(self, mock_vector_store):
        """Test that results include course and lesson context headers"""
        tool = CourseSearchTool(mock_vector_store)
        result = tool.execute(query="machine learning")

        # Should include course title in formatted output
        assert "[" in result, "Should have header markers"
        assert "Introduction to Machine Learning" in result, "Should include course title"

    def test_execute_tracks_sources(self, mock_vector_store):
        """Test that execute() properly tracks sources in last_sources"""
        tool = CourseSearchTool(mock_vector_store)

        # Execute search
        tool.execute(query="machine learning")

        # Should populate last_sources
        assert len(tool.last_sources) > 0, "Should track sources"
        assert all(isinstance(source, SourceItem) for source in tool.last_sources), \
            "All sources should be SourceItem instances"

    def test_execute_sources_include_lesson_links(self, mock_vector_store):
        """Test that sources include lesson links when available"""
        mock_vector_store.get_lesson_link.return_value = "https://example.com/lesson-1"

        tool = CourseSearchTool(mock_vector_store)
        tool.execute(query="machine learning")

        # Check sources have URLs
        if tool.last_sources:
            # At least one source should have a URL
            has_url = any(source.url is not None for source in tool.last_sources)
            assert has_url, "Should include lesson links in sources"

    def test_execute_resets_previous_sources(self, mock_vector_store):
        """Test that executing a new search doesn't accumulate sources"""
        tool = CourseSearchTool(mock_vector_store)

        # First search
        tool.execute(query="first query")
        first_count = len(tool.last_sources)

        # Second search with same mock data
        tool.execute(query="second query")
        second_count = len(tool.last_sources)

        # Should replace, not accumulate
        assert second_count == first_count, "Should replace sources, not accumulate"


class TestCourseSearchToolDefinition:
    """Test CourseSearchTool tool definition"""

    def test_get_tool_definition_structure(self, mock_vector_store):
        """Test that tool definition has correct structure"""
        tool = CourseSearchTool(mock_vector_store)
        definition = tool.get_tool_definition()

        # Should have required fields
        assert "name" in definition, "Should have name field"
        assert "description" in definition, "Should have description field"
        assert "input_schema" in definition, "Should have input_schema field"

    def test_get_tool_definition_name(self, mock_vector_store):
        """Test that tool name is correct"""
        tool = CourseSearchTool(mock_vector_store)
        definition = tool.get_tool_definition()

        assert definition["name"] == "search_course_content", "Tool name should be search_course_content"

    def test_get_tool_definition_parameters(self, mock_vector_store):
        """Test that tool definition includes correct parameters"""
        tool = CourseSearchTool(mock_vector_store)
        definition = tool.get_tool_definition()

        schema = definition["input_schema"]
        properties = schema["properties"]

        # Should have query parameter
        assert "query" in properties, "Should have query parameter"
        assert "query" in schema["required"], "Query should be required"

        # Should have optional course_name
        assert "course_name" in properties, "Should have course_name parameter"
        assert "course_name" not in schema.get("required", []), "course_name should be optional"

        # Should have optional lesson_number
        assert "lesson_number" in properties, "Should have lesson_number parameter"
        assert "lesson_number" not in schema.get("required", []), "lesson_number should be optional"


class TestToolManager:
    """Test ToolManager functionality"""

    def test_register_tool(self, mock_vector_store):
        """Test registering a tool with the manager"""
        manager = ToolManager()
        tool = CourseSearchTool(mock_vector_store)

        manager.register_tool(tool)

        # Tool should be registered
        assert "search_course_content" in manager.tools, "Tool should be registered"

    def test_get_tool_definitions(self, mock_vector_store):
        """Test getting all tool definitions"""
        manager = ToolManager()
        tool = CourseSearchTool(mock_vector_store)
        manager.register_tool(tool)

        definitions = manager.get_tool_definitions()

        # Should return list of definitions
        assert isinstance(definitions, list), "Should return list"
        assert len(definitions) == 1, "Should have one tool"
        assert definitions[0]["name"] == "search_course_content", "Should have correct tool name"

    def test_execute_tool(self, mock_vector_store):
        """Test executing a tool through the manager"""
        manager = ToolManager()
        tool = CourseSearchTool(mock_vector_store)
        manager.register_tool(tool)

        # Execute tool
        result = manager.execute_tool("search_course_content", query="test query")

        # Should return result
        assert isinstance(result, str), "Should return string result"

    def test_execute_nonexistent_tool(self, mock_vector_store):
        """Test executing a tool that doesn't exist"""
        manager = ToolManager()

        result = manager.execute_tool("nonexistent_tool", query="test")

        # Should return error message
        assert "not found" in result, "Should indicate tool not found"

    def test_get_last_sources(self, mock_vector_store):
        """Test retrieving sources from last tool execution"""
        manager = ToolManager()
        tool = CourseSearchTool(mock_vector_store)
        manager.register_tool(tool)

        # Execute search
        manager.execute_tool("search_course_content", query="test")

        # Get sources
        sources = manager.get_last_sources()

        # Should return sources from the tool
        assert isinstance(sources, list), "Should return list of sources"

    def test_reset_sources(self, mock_vector_store):
        """Test resetting sources across all tools"""
        manager = ToolManager()
        tool = CourseSearchTool(mock_vector_store)
        manager.register_tool(tool)

        # Execute and populate sources
        manager.execute_tool("search_course_content", query="test")
        assert len(manager.get_last_sources()) > 0, "Should have sources after search"

        # Reset sources
        manager.reset_sources()

        # Sources should be empty
        assert len(manager.get_last_sources()) == 0, "Sources should be reset"
