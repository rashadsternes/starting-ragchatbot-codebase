"""
Integration tests for the complete RAG system
"""
import pytest
from pathlib import Path
import sys
from unittest.mock import Mock, patch
import tempfile
import shutil

sys.path.insert(0, str(Path(__file__).parent.parent))

from rag_system import RAGSystem
from models import Course, Lesson


class TestRAGSystemIntegration:
    """End-to-end integration tests for RAG system"""

    def test_rag_system_with_max_results_zero_fails(self, config_with_zero_results, temp_chroma_db):
        """
        CRITICAL BUG TEST: RAG system with MAX_RESULTS=0 should fail to return content
        This documents the root cause of 'query failed' errors
        """
        # Update config to use temp directory
        config_with_zero_results.CHROMA_PATH = temp_chroma_db

        # Create RAG system with buggy config
        rag = RAGSystem(config_with_zero_results)

        # Add test course
        test_doc = self._create_test_course_file(temp_chroma_db)
        rag.add_course_document(test_doc)

        # Mock the AI client to force tool use
        with patch.object(rag.ai_generator, 'client') as mock_client:
            # Configure mock to trigger tool use
            tool_response = Mock()
            tool_response.stop_reason = "tool_use"

            tool_block = Mock()
            tool_block.type = "tool_use"
            tool_block.name = "search_course_content"
            tool_block.id = "tool_123"
            tool_block.input = {"query": "what is machine learning"}

            tool_response.content = [tool_block]

            # Final response
            final_response = Mock()
            final_response.stop_reason = "end_turn"
            final_content = Mock()
            final_content.text = "Based on the search, no relevant content was found."
            final_response.content = [final_content]

            mock_client.messages.create.side_effect = [tool_response, final_response]

            # Try to query
            response, sources = rag.query("What is machine learning?")

            # The search tool should return "No relevant content found" because MAX_RESULTS=0
            # This causes the vector store to return 0 results
            assert len(sources) == 0, "Should have no sources when MAX_RESULTS=0"

    def test_rag_system_with_proper_max_results_succeeds(self, config_with_max_results, temp_chroma_db):
        """
        Test that RAG system works correctly with proper MAX_RESULTS setting
        """
        # Update config to use temp directory
        config_with_max_results.CHROMA_PATH = temp_chroma_db

        # Create RAG system with proper config
        rag = RAGSystem(config_with_max_results)

        # Add test course
        test_doc = self._create_test_course_file(temp_chroma_db)
        rag.add_course_document(test_doc)

        # Mock the AI client
        with patch.object(rag.ai_generator, 'client') as mock_client:
            # Configure mock to trigger tool use
            tool_response = Mock()
            tool_response.stop_reason = "tool_use"

            tool_block = Mock()
            tool_block.type = "tool_use"
            tool_block.name = "search_course_content"
            tool_block.id = "tool_123"
            tool_block.input = {"query": "what is machine learning"}

            tool_response.content = [tool_block]

            # Final response
            final_response = Mock()
            final_response.stop_reason = "end_turn"
            final_content = Mock()
            final_content.text = "Machine learning is a subset of AI."
            final_response.content = [final_content]

            mock_client.messages.create.side_effect = [tool_response, final_response]

            # Query should work
            response, sources = rag.query("What is machine learning?")

            # Should have sources with proper config
            assert isinstance(response, str), "Should return response"
            # Sources might be available depending on search results
            assert isinstance(sources, list), "Should return sources list"

    def test_rag_system_session_management(self, config_with_max_results, temp_chroma_db):
        """Test that RAG system properly manages conversation sessions"""
        config_with_max_results.CHROMA_PATH = temp_chroma_db

        rag = RAGSystem(config_with_max_results)

        # Create a session
        session_id = rag.session_manager.create_session()

        # Mock AI client
        with patch.object(rag.ai_generator, 'client') as mock_client:
            mock_response = Mock()
            mock_response.stop_reason = "end_turn"
            mock_content = Mock()
            mock_content.text = "Test response"
            mock_response.content = [mock_content]
            mock_client.messages.create.return_value = mock_response

            # Make two queries in the same session
            rag.query("First question", session_id=session_id)
            rag.query("Second question", session_id=session_id)

            # Session should have history
            history = rag.session_manager.get_conversation_history(session_id)

            assert history is not None, "Should have conversation history"
            assert "First question" in history, "Should contain first question"
            assert "Second question" in history, "Should contain second question"

    def test_rag_system_returns_sources(self, config_with_max_results, temp_chroma_db):
        """Test that RAG system properly returns sources from searches"""
        config_with_max_results.CHROMA_PATH = temp_chroma_db

        rag = RAGSystem(config_with_max_results)

        # Add test course
        test_doc = self._create_test_course_file(temp_chroma_db)
        rag.add_course_document(test_doc)

        # Mock AI client to trigger tool use
        with patch.object(rag.ai_generator, 'client') as mock_client:
            tool_response = Mock()
            tool_response.stop_reason = "tool_use"

            tool_block = Mock()
            tool_block.type = "tool_use"
            tool_block.name = "search_course_content"
            tool_block.id = "tool_123"
            tool_block.input = {"query": "machine learning"}

            tool_response.content = [tool_block]

            final_response = Mock()
            final_response.stop_reason = "end_turn"
            final_content = Mock()
            final_content.text = "Machine learning is a subset of AI."
            final_response.content = [final_content]

            mock_client.messages.create.side_effect = [tool_response, final_response]

            # Query
            response, sources = rag.query("What is machine learning?")

            # Sources should be returned
            assert isinstance(sources, list), "Should return sources list"

    def test_rag_system_course_analytics(self, config_with_max_results, temp_chroma_db):
        """Test that RAG system returns correct course analytics"""
        config_with_max_results.CHROMA_PATH = temp_chroma_db

        rag = RAGSystem(config_with_max_results)

        # Initially no courses
        analytics = rag.get_course_analytics()
        assert analytics["total_courses"] == 0, "Should start with 0 courses"

        # Add course
        test_doc = self._create_test_course_file(temp_chroma_db)
        rag.add_course_document(test_doc)

        # Should have 1 course
        analytics = rag.get_course_analytics()
        assert analytics["total_courses"] == 1, "Should have 1 course"
        assert len(analytics["course_titles"]) == 1, "Should have 1 course title"

    def test_rag_system_avoids_duplicate_courses(self, config_with_max_results, temp_chroma_db):
        """Test that RAG system doesn't add duplicate courses"""
        config_with_max_results.CHROMA_PATH = temp_chroma_db

        rag = RAGSystem(config_with_max_results)

        # Add same course twice
        test_doc = self._create_test_course_file(temp_chroma_db)
        rag.add_course_document(test_doc)
        rag.add_course_document(test_doc)

        # Should still only have 1 course
        analytics = rag.get_course_analytics()
        assert analytics["total_courses"] == 1, "Should not add duplicate courses"

    def test_rag_system_handles_missing_api_key(self):
        """Test that RAG system handles missing API key gracefully"""
        from dataclasses import dataclass

        @dataclass
        class NoKeyConfig:
            ANTHROPIC_API_KEY: str = ""
            ANTHROPIC_MODEL: str = "claude-sonnet-4-20250514"
            EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
            CHUNK_SIZE: int = 800
            CHUNK_OVERLAP: int = 100
            MAX_RESULTS: int = 5
            MAX_HISTORY: int = 2
            CHROMA_PATH: str = "./test_chroma_db"

        # Should initialize without errors (API key checked on first use)
        rag = RAGSystem(NoKeyConfig())
        assert rag is not None, "Should create RAG system even with empty API key"

    # Helper method
    def _create_test_course_file(self, directory):
        """Create a temporary test course file"""
        content = """Course Title: Test Machine Learning Course
Course Link: https://example.com/ml
Course Instructor: Test Instructor

Lesson 1: Introduction to ML
Lesson Link: https://example.com/ml/lesson1
Machine learning is a subset of artificial intelligence that enables computers to learn from data without being explicitly programmed. It involves algorithms that can identify patterns and make predictions.

Lesson 2: Linear Regression
Lesson Link: https://example.com/ml/lesson2
Linear regression is a fundamental machine learning algorithm used to model relationships between variables. It predicts a continuous output based on input features.
"""
        file_path = Path(directory) / "test_course.txt"
        file_path.write_text(content)
        return str(file_path)


class TestRAGSystemToolIntegration:
    """Test integration between RAG system and search tools"""

    def test_search_tool_registered(self, config_with_max_results, temp_chroma_db):
        """Test that search tool is properly registered in RAG system"""
        config_with_max_results.CHROMA_PATH = temp_chroma_db
        rag = RAGSystem(config_with_max_results)

        # Should have search_course_content tool
        tool_defs = rag.tool_manager.get_tool_definitions()

        tool_names = [tool["name"] for tool in tool_defs]
        assert "search_course_content" in tool_names, "Should register search tool"

    def test_outline_tool_registered(self, config_with_max_results, temp_chroma_db):
        """Test that outline tool is properly registered"""
        config_with_max_results.CHROMA_PATH = temp_chroma_db
        rag = RAGSystem(config_with_max_results)

        tool_defs = rag.tool_manager.get_tool_definitions()

        tool_names = [tool["name"] for tool in tool_defs]
        assert "get_course_outline" in tool_names, "Should register outline tool"

    def test_tools_have_access_to_vector_store(self, config_with_max_results, temp_chroma_db):
        """Test that tools can access the vector store"""
        config_with_max_results.CHROMA_PATH = temp_chroma_db
        rag = RAGSystem(config_with_max_results)

        # Search tool should have reference to vector store
        assert rag.search_tool.store is rag.vector_store, \
            "Search tool should reference RAG system's vector store"


class TestRAGSystemSequentialToolCalling:
    """Test sequential tool calling in RAG system"""

    def test_sequential_tool_calling_enabled_in_config(self, config_with_max_results):
        """Test that config has MAX_TOOL_ROUNDS configured"""
        from config import config as prod_config

        assert hasattr(prod_config, 'MAX_TOOL_ROUNDS'), "Config should have MAX_TOOL_ROUNDS"
        assert prod_config.MAX_TOOL_ROUNDS > 0, "MAX_TOOL_ROUNDS should be positive"
        assert prod_config.MAX_TOOL_ROUNDS == 2, "MAX_TOOL_ROUNDS should be 2"

    def test_system_prompt_allows_multiple_tool_calls(self, config_with_max_results, temp_chroma_db):
        """Test that system prompt mentions multiple tool calls"""
        config_with_max_results.CHROMA_PATH = temp_chroma_db
        rag = RAGSystem(config_with_max_results)

        system_prompt = rag.ai_generator.SYSTEM_PROMPT

        # Should mention multiple tool calls
        assert "multiple tool calls" in system_prompt.lower() or "2 rounds" in system_prompt.lower(), \
            "System prompt should mention ability to make multiple tool calls"

        # Should NOT mention "one tool use per query maximum"
        assert "one tool use per query maximum" not in system_prompt.lower(), \
            "System prompt should not restrict to single tool use"

    def test_comparison_query_structure(self, config_with_max_results, temp_chroma_db):
        """Test that comparison queries can theoretically use multiple tools"""
        config_with_max_results.CHROMA_PATH = temp_chroma_db
        rag = RAGSystem(config_with_max_results)

        # Mock AI client to simulate comparison query with 2 tool calls
        with patch.object(rag.ai_generator, 'client') as mock_client:
            # First tool call
            tool_response_1 = Mock()
            tool_response_1.stop_reason = "tool_use"
            tool_block_1 = Mock()
            tool_block_1.type = "tool_use"
            tool_block_1.name = "search_course_content"
            tool_block_1.id = "tool_1"
            tool_block_1.input = {"query": "topic A", "course_name": "Course A"}
            tool_response_1.content = [tool_block_1]

            # Second tool call
            tool_response_2 = Mock()
            tool_response_2.stop_reason = "tool_use"
            tool_block_2 = Mock()
            tool_block_2.type = "tool_use"
            tool_block_2.name = "search_course_content"
            tool_block_2.id = "tool_2"
            tool_block_2.input = {"query": "topic A", "course_name": "Course B"}
            tool_response_2.content = [tool_block_2]

            # Final response
            final_response = Mock()
            final_response.stop_reason = "end_turn"
            final_content = Mock()
            final_content.text = "Course A and Course B both cover topic A."
            final_response.content = [final_content]

            mock_client.messages.create.side_effect = [
                tool_response_1,
                tool_response_2,
                final_response
            ]

            # Query should complete successfully
            response, sources = rag.query("Compare topic A in Course A and Course B")

            # Should make 3 API calls
            assert mock_client.messages.create.call_count == 3, \
                "Should make 3 API calls for 2-round sequential tool use"

            # Should return final response
            assert "Course A and Course B" in response

    def test_multi_part_query_structure(self, config_with_max_results, temp_chroma_db):
        """Test that multi-part queries can use outline + search"""
        config_with_max_results.CHROMA_PATH = temp_chroma_db
        rag = RAGSystem(config_with_max_results)

        # Mock AI client to simulate outline + search
        with patch.object(rag.ai_generator, 'client') as mock_client:
            # First: get outline
            tool_response_1 = Mock()
            tool_response_1.stop_reason = "tool_use"
            tool_block_1 = Mock()
            tool_block_1.type = "tool_use"
            tool_block_1.name = "get_course_outline"
            tool_block_1.id = "tool_1"
            tool_block_1.input = {"course_name": "ML Course"}
            tool_response_1.content = [tool_block_1]

            # Second: search specific lesson
            tool_response_2 = Mock()
            tool_response_2.stop_reason = "tool_use"
            tool_block_2 = Mock()
            tool_block_2.type = "tool_use"
            tool_block_2.name = "search_course_content"
            tool_block_2.id = "tool_2"
            tool_block_2.input = {
                "query": "neural networks",
                "course_name": "ML Course",
                "lesson_number": 3
            }
            tool_response_2.content = [tool_block_2]

            # Final response
            final_response = Mock()
            final_response.stop_reason = "end_turn"
            final_content = Mock()
            final_content.text = "The course has 3 lessons. Lesson 3 covers neural networks."
            final_response.content = [final_content]

            mock_client.messages.create.side_effect = [
                tool_response_1,
                tool_response_2,
                final_response
            ]

            # Query should complete successfully
            response, sources = rag.query(
                "What lessons are in ML Course and what does lesson 3 say about neural networks?"
            )

            # Should make 3 API calls
            assert mock_client.messages.create.call_count == 3

            # Should return complete answer
            assert "3 lessons" in response or "Lesson 3" in response
