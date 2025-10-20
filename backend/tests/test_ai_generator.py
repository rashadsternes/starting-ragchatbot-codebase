"""
Tests for AIGenerator tool calling behavior
"""
import pytest
from pathlib import Path
import sys
from unittest.mock import Mock, patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

from ai_generator import AIGenerator
from search_tools import ToolManager, CourseSearchTool


class TestAIGeneratorToolCalling:
    """Test AIGenerator's ability to call tools correctly"""

    def test_generate_response_without_tools(self, mock_ai_client):
        """Test basic response generation without tool use"""
        # Create generator with mock client
        with patch('ai_generator.anthropic.Anthropic', return_value=mock_ai_client):
            generator = AIGenerator(api_key="test-key", model="claude-sonnet-4-20250514")
            generator.client = mock_ai_client

        # Generate response
        response = generator.generate_response(query="What is 2+2?")

        # Should call API
        mock_ai_client.messages.create.assert_called_once()

        # Should return text response
        assert isinstance(response, str), "Should return string"
        assert len(response) > 0, "Should return non-empty response"

    def test_generate_response_includes_query_in_messages(self, mock_ai_client):
        """Test that user query is included in API call"""
        with patch('ai_generator.anthropic.Anthropic', return_value=mock_ai_client):
            generator = AIGenerator(api_key="test-key", model="claude-sonnet-4-20250514")
            generator.client = mock_ai_client

        query = "What is machine learning?"
        generator.generate_response(query=query)

        # Check API was called with correct message
        call_args = mock_ai_client.messages.create.call_args
        messages = call_args[1]["messages"]

        assert len(messages) > 0, "Should have messages"
        assert messages[0]["role"] == "user", "First message should be from user"
        assert query in messages[0]["content"], "Message should contain query"

    def test_generate_response_with_conversation_history(self, mock_ai_client):
        """Test that conversation history is included in system prompt"""
        with patch('ai_generator.anthropic.Anthropic', return_value=mock_ai_client):
            generator = AIGenerator(api_key="test-key", model="claude-sonnet-4-20250514")
            generator.client = mock_ai_client

        history = "User: Previous question\nAssistant: Previous answer"
        generator.generate_response(query="New question", conversation_history=history)

        # Check system prompt includes history
        call_args = mock_ai_client.messages.create.call_args
        system_content = call_args[1]["system"]

        assert history in system_content, "System prompt should include conversation history"

    def test_generate_response_with_tools_passes_tool_definitions(self, mock_ai_client, mock_vector_store):
        """Test that tool definitions are passed to API when tools provided"""
        with patch('ai_generator.anthropic.Anthropic', return_value=mock_ai_client):
            generator = AIGenerator(api_key="test-key", model="claude-sonnet-4-20250514")
            generator.client = mock_ai_client

        # Create tool manager with search tool
        tool_manager = ToolManager()
        search_tool = CourseSearchTool(mock_vector_store)
        tool_manager.register_tool(search_tool)

        # Generate response with tools
        generator.generate_response(
            query="What is machine learning?",
            tools=tool_manager.get_tool_definitions(),
            tool_manager=tool_manager
        )

        # Check tools were passed to API
        call_args = mock_ai_client.messages.create.call_args
        assert "tools" in call_args[1], "Should pass tools parameter"
        assert len(call_args[1]["tools"]) > 0, "Should have tool definitions"

    def test_generate_response_handles_tool_use(self, mock_ai_client_with_tool_use, mock_vector_store):
        """Test that AI generator correctly handles tool use responses"""
        with patch('ai_generator.anthropic.Anthropic', return_value=mock_ai_client_with_tool_use):
            generator = AIGenerator(api_key="test-key", model="claude-sonnet-4-20250514")
            generator.client = mock_ai_client_with_tool_use

        # Create tool manager
        tool_manager = ToolManager()
        search_tool = CourseSearchTool(mock_vector_store)
        tool_manager.register_tool(search_tool)

        # Generate response that triggers tool use
        response = generator.generate_response(
            query="What is machine learning in the ML course?",
            tools=tool_manager.get_tool_definitions(),
            tool_manager=tool_manager
        )

        # Should make two API calls (initial + follow-up after tool execution)
        assert mock_ai_client_with_tool_use.messages.create.call_count == 2, \
            "Should make two API calls when tool is used"

        # Should return final response
        assert isinstance(response, str), "Should return string response"
        assert len(response) > 0, "Should return non-empty response"

    def test_tool_execution_calls_tool_manager(self, mock_ai_client_with_tool_use, mock_vector_store):
        """Test that tool execution actually calls the tool manager"""
        with patch('ai_generator.anthropic.Anthropic', return_value=mock_ai_client_with_tool_use):
            generator = AIGenerator(api_key="test-key", model="claude-sonnet-4-20250514")
            generator.client = mock_ai_client_with_tool_use

        # Create tool manager with spy
        tool_manager = ToolManager()
        search_tool = CourseSearchTool(mock_vector_store)
        tool_manager.register_tool(search_tool)

        # Mock the execute_tool method to track calls
        original_execute = tool_manager.execute_tool
        tool_manager.execute_tool = Mock(side_effect=original_execute)

        # Generate response
        generator.generate_response(
            query="What is machine learning?",
            tools=tool_manager.get_tool_definitions(),
            tool_manager=tool_manager
        )

        # Tool manager should have been called
        tool_manager.execute_tool.assert_called_once()
        call_args = tool_manager.execute_tool.call_args

        # Should call search_course_content tool
        assert call_args[0][0] == "search_course_content", "Should call search_course_content tool"

    def test_tool_results_sent_back_to_api(self, mock_ai_client_with_tool_use, mock_vector_store):
        """Test that tool results are sent back to Claude in follow-up request"""
        with patch('ai_generator.anthropic.Anthropic', return_value=mock_ai_client_with_tool_use):
            generator = AIGenerator(api_key="test-key", model="claude-sonnet-4-20250514")
            generator.client = mock_ai_client_with_tool_use

        # Create tool manager
        tool_manager = ToolManager()
        search_tool = CourseSearchTool(mock_vector_store)
        tool_manager.register_tool(search_tool)

        # Generate response
        generator.generate_response(
            query="What is machine learning?",
            tools=tool_manager.get_tool_definitions(),
            tool_manager=tool_manager
        )

        # Check second API call includes tool results
        second_call_args = mock_ai_client_with_tool_use.messages.create.call_args_list[1]
        messages = second_call_args[1]["messages"]

        # Should have user message with tool results
        has_tool_result = any(
            msg["role"] == "user" and
            isinstance(msg["content"], list) and
            any(block.get("type") == "tool_result" for block in msg["content"])
            for msg in messages
        )

        assert has_tool_result, "Second API call should include tool results"

    def test_system_prompt_contains_tool_usage_instructions(self, mock_ai_client):
        """Test that system prompt includes instructions for using tools"""
        with patch('ai_generator.anthropic.Anthropic', return_value=mock_ai_client):
            generator = AIGenerator(api_key="test-key", model="claude-sonnet-4-20250514")
            generator.client = mock_ai_client

        generator.generate_response(query="test")

        # Check system prompt
        call_args = mock_ai_client.messages.create.call_args
        system_content = call_args[1]["system"]

        # Should mention tools or search
        assert "search" in system_content.lower() or "tool" in system_content.lower(), \
            "System prompt should mention tools/search"

    def test_temperature_set_to_zero(self, mock_ai_client):
        """Test that temperature is set to 0 for consistent responses"""
        with patch('ai_generator.anthropic.Anthropic', return_value=mock_ai_client):
            generator = AIGenerator(api_key="test-key", model="claude-sonnet-4-20250514")
            generator.client = mock_ai_client

        generator.generate_response(query="test")

        # Check temperature parameter
        call_args = mock_ai_client.messages.create.call_args
        assert call_args[1]["temperature"] == 0, "Temperature should be 0"

    def test_max_tokens_configured(self, mock_ai_client):
        """Test that max_tokens is configured"""
        with patch('ai_generator.anthropic.Anthropic', return_value=mock_ai_client):
            generator = AIGenerator(api_key="test-key", model="claude-sonnet-4-20250514")
            generator.client = mock_ai_client

        generator.generate_response(query="test")

        # Check max_tokens parameter
        call_args = mock_ai_client.messages.create.call_args
        assert "max_tokens" in call_args[1], "Should set max_tokens"
        assert call_args[1]["max_tokens"] > 0, "max_tokens should be positive"


class TestAIGeneratorConfiguration:
    """Test AIGenerator configuration and initialization"""

    def test_initialization_sets_api_key(self, mock_ai_client):
        """Test that API key is properly set during initialization"""
        with patch('ai_generator.anthropic.Anthropic', return_value=mock_ai_client) as mock_anthropic:
            generator = AIGenerator(api_key="test-api-key", model="claude-sonnet-4-20250514")

            # Should create Anthropic client with API key
            mock_anthropic.assert_called_once_with(api_key="test-api-key")

    def test_initialization_sets_model(self, mock_ai_client):
        """Test that model is stored correctly"""
        with patch('ai_generator.anthropic.Anthropic', return_value=mock_ai_client):
            generator = AIGenerator(api_key="test-key", model="claude-sonnet-4-20250514")

            assert generator.model == "claude-sonnet-4-20250514", "Model should be stored"

    def test_base_params_configured(self, mock_ai_client):
        """Test that base parameters are pre-configured"""
        with patch('ai_generator.anthropic.Anthropic', return_value=mock_ai_client):
            generator = AIGenerator(api_key="test-key", model="claude-sonnet-4-20250514")

            assert hasattr(generator, 'base_params'), "Should have base_params"
            assert 'model' in generator.base_params, "Should configure model"
            assert 'temperature' in generator.base_params, "Should configure temperature"
            assert 'max_tokens' in generator.base_params, "Should configure max_tokens"


class TestAIGeneratorSequentialToolCalling:
    """Test sequential tool calling functionality"""

    def test_sequential_tool_use_makes_three_api_calls(self, mock_ai_client_with_sequential_tool_use, mock_vector_store):
        """Verify loop makes 3 API calls for 2-round tool use"""
        with patch('ai_generator.anthropic.Anthropic', return_value=mock_ai_client_with_sequential_tool_use):
            generator = AIGenerator(api_key="test-key", model="claude-sonnet-4-20250514")
            generator.client = mock_ai_client_with_sequential_tool_use

        # Create tool manager
        tool_manager = ToolManager()
        search_tool = CourseSearchTool(mock_vector_store)
        tool_manager.register_tool(search_tool)

        # Generate response
        response = generator.generate_response(
            query="Compare ML basics and applications",
            tools=tool_manager.get_tool_definitions(),
            tool_manager=tool_manager
        )

        # Should make 3 API calls (initial + round1 + round2)
        assert mock_ai_client_with_sequential_tool_use.messages.create.call_count == 3, \
            "Should make 3 API calls for 2 rounds of tool use"

        # Should return final response
        assert response == "Machine learning is used for predictions and pattern recognition."

    def test_sequential_tool_use_accumulates_messages(self, mock_ai_client_with_sequential_tool_use, mock_vector_store):
        """Verify messages grow with each round"""
        with patch('ai_generator.anthropic.Anthropic', return_value=mock_ai_client_with_sequential_tool_use):
            generator = AIGenerator(api_key="test-key", model="claude-sonnet-4-20250514")
            generator.client = mock_ai_client_with_sequential_tool_use

        tool_manager = ToolManager()
        search_tool = CourseSearchTool(mock_vector_store)
        tool_manager.register_tool(search_tool)

        generator.generate_response(
            query="Test query",
            tools=tool_manager.get_tool_definitions(),
            tool_manager=tool_manager
        )

        # Inspect third API call's messages parameter
        third_call_args = mock_ai_client_with_sequential_tool_use.messages.create.call_args_list[2]
        messages = third_call_args[1]["messages"]

        # Should have 5 messages: user, assistant (tool1), user (results), assistant (tool2), user (results)
        assert len(messages) == 5, f"Expected 5 messages but got {len(messages)}"

    def test_sequential_tool_use_preserves_tools_in_params(self, mock_ai_client_with_sequential_tool_use, mock_vector_store):
        """Verify tools available in subsequent rounds"""
        with patch('ai_generator.anthropic.Anthropic', return_value=mock_ai_client_with_sequential_tool_use):
            generator = AIGenerator(api_key="test-key", model="claude-sonnet-4-20250514")
            generator.client = mock_ai_client_with_sequential_tool_use

        tool_manager = ToolManager()
        search_tool = CourseSearchTool(mock_vector_store)
        tool_manager.register_tool(search_tool)
        tool_defs = tool_manager.get_tool_definitions()

        generator.generate_response(
            query="Test query",
            tools=tool_defs,
            tool_manager=tool_manager
        )

        # Check second and third API calls have tools
        second_call_args = mock_ai_client_with_sequential_tool_use.messages.create.call_args_list[1]
        third_call_args = mock_ai_client_with_sequential_tool_use.messages.create.call_args_list[2]

        assert "tools" in second_call_args[1], "Second call should have tools"
        assert "tools" in third_call_args[1], "Third call should have tools"

    def test_early_termination_after_one_tool(self, mock_ai_client_with_early_termination, mock_vector_store):
        """Verify Claude can stop after first tool use"""
        with patch('ai_generator.anthropic.Anthropic', return_value=mock_ai_client_with_early_termination):
            generator = AIGenerator(api_key="test-key", model="claude-sonnet-4-20250514")
            generator.client = mock_ai_client_with_early_termination

        tool_manager = ToolManager()
        search_tool = CourseSearchTool(mock_vector_store)
        tool_manager.register_tool(search_tool)

        response = generator.generate_response(
            query="Simple query",
            tools=tool_manager.get_tool_definitions(),
            tool_manager=tool_manager
        )

        # Should only make 2 API calls (not 3)
        assert mock_ai_client_with_early_termination.messages.create.call_count == 2, \
            "Should only make 2 API calls when Claude stops early"

        # Should return response successfully
        assert response == "Here's the answer based on the search."

    def test_max_rounds_limits_to_two_tools(self, mock_vector_store):
        """Verify loop exits after 2 rounds"""
        # Create mock that would continue indefinitely
        mock_client = Mock()

        # All responses request tools (infinite loop scenario)
        tool_response = Mock()
        tool_response.stop_reason = "tool_use"
        tool_block = Mock()
        tool_block.type = "tool_use"
        tool_block.name = "search_course_content"
        tool_block.id = "tool_inf"
        tool_block.input = {"query": "test"}
        # Add text attribute to mock for final extraction
        tool_block.text = ""  # Empty text
        tool_response.content = [tool_block]

        # Mock returns tool_use forever
        mock_client.messages.create.return_value = tool_response

        with patch('ai_generator.anthropic.Anthropic', return_value=mock_client):
            generator = AIGenerator(api_key="test-key", model="claude-sonnet-4-20250514")
            generator.client = mock_client

        tool_manager = ToolManager()
        search_tool = CourseSearchTool(mock_vector_store)
        tool_manager.register_tool(search_tool)

        # Should not hang - should exit after MAX_TOOL_ROUNDS
        response = generator.generate_response(
            query="Test query",
            tools=tool_manager.get_tool_definitions(),
            tool_manager=tool_manager
        )

        # Should make exactly 3 API calls (initial + 2 rounds)
        # With MAX_TOOL_ROUNDS=2, we make 2 tool execution rounds
        assert mock_client.messages.create.call_count == 3, \
            "Should exit after MAX_TOOL_ROUNDS=2"

    def test_tool_execution_error_passed_to_claude(self, mock_ai_client_with_tool_use):
        """Verify errors sent back as tool results"""
        # Create tool manager that raises exception
        mock_tool_manager = Mock(spec=ToolManager)
        mock_tool_manager.execute_tool.side_effect = Exception("Database connection failed")
        mock_tool_manager.get_tool_definitions.return_value = [{"name": "search_course_content"}]

        with patch('ai_generator.anthropic.Anthropic', return_value=mock_ai_client_with_tool_use):
            generator = AIGenerator(api_key="test-key", model="claude-sonnet-4-20250514")
            generator.client = mock_ai_client_with_tool_use

        # Should not crash
        response = generator.generate_response(
            query="Test query",
            tools=mock_tool_manager.get_tool_definitions(),
            tool_manager=mock_tool_manager
        )

        # Should still return a response
        assert response is not None
        assert len(response) > 0

    def test_no_regression_for_single_tool_use(self, mock_ai_client_with_tool_use, mock_vector_store):
        """Verify existing single tool use still works"""
        with patch('ai_generator.anthropic.Anthropic', return_value=mock_ai_client_with_tool_use):
            generator = AIGenerator(api_key="test-key", model="claude-sonnet-4-20250514")
            generator.client = mock_ai_client_with_tool_use

        tool_manager = ToolManager()
        search_tool = CourseSearchTool(mock_vector_store)
        tool_manager.register_tool(search_tool)

        response = generator.generate_response(
            query="What is machine learning?",
            tools=tool_manager.get_tool_definitions(),
            tool_manager=tool_manager
        )

        # Should return correct response
        assert "Machine learning is a subset of artificial intelligence" in response

        # Should make 2 API calls (initial + final)
        assert mock_ai_client_with_tool_use.messages.create.call_count == 2
