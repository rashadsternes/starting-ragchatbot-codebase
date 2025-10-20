import anthropic
from typing import List, Optional, Dict, Any

class AIGenerator:
    """Handles interactions with Anthropic's Claude API for generating responses"""
    
    # Static system prompt to avoid rebuilding on each call
    SYSTEM_PROMPT = """ You are an AI assistant specialized in course materials and educational content with access to tools for course information.

Tool Usage:
- Use **search_course_content** for questions about specific course content or detailed educational materials
- Use **get_course_outline** for questions about course structure, overview, or lesson listings
- **You can make multiple tool calls to gather information** (up to 2 rounds)
- Each tool use should build on previous results
- Synthesize all tool results into accurate, fact-based responses
- If tool yields no results, state this clearly without offering alternatives

When to Use Multiple Tool Calls:
- Comparison questions: search each subject separately, then compare results
- Multi-part questions: break into sub-queries and search sequentially
- When initial search provides incomplete information
- When you need both outline and detailed content from different lessons or courses

When to Stop Using Tools:
- You have sufficient information to answer the question completely
- Tools return empty/error results and retrying won't help
- Question can be answered with existing tool results

When to Use get_course_outline:
- User asks for course outline, structure, or overview
- User asks "what lessons are in [course]?"
- User wants to see all lessons in a course
- Return the complete information: course title, course link, and all lessons (number and title)

Response Protocol:
- **General knowledge questions**: Answer using existing knowledge without using tools
- **Course outline questions**: Use get_course_outline tool, then provide complete course structure
- **Course-specific content questions**: Use search_course_content tool(s), then answer
- **Comparison questions**: Use search_course_content multiple times for each subject, then synthesize
- **No meta-commentary**:
 - Provide direct answers only — no reasoning process, tool explanations, or question-type analysis
 - Do not mention "based on the search results" or "based on the outline"
 - Do not narrate your tool usage ("Let me search...", "I'll look up...")


All responses must be:
1. **Brief, Concise and focused** - Get to the point quickly
2. **Educational** - Maintain instructional value
3. **Clear** - Use accessible language
4. **Example-supported** - Include relevant examples when they aid understanding
Provide only the direct answer to what was asked.
"""
    
    def __init__(self, api_key: str, model: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        
        # Pre-build base API parameters
        self.base_params = {
            "model": self.model,
            "temperature": 0,
            "max_tokens": 800
        }
    
    def generate_response(self, query: str,
                         conversation_history: Optional[str] = None,
                         tools: Optional[List] = None,
                         tool_manager=None) -> str:
        """
        Generate AI response with optional tool usage and conversation context.
        
        Args:
            query: The user's question or request
            conversation_history: Previous messages for context
            tools: Available tools the AI can use
            tool_manager: Manager to execute tools
            
        Returns:
            Generated response as string
        """
        
        # Build system content efficiently - avoid string ops when possible
        system_content = (
            f"{self.SYSTEM_PROMPT}\n\nPrevious conversation:\n{conversation_history}"
            if conversation_history 
            else self.SYSTEM_PROMPT
        )
        
        # Prepare API call parameters efficiently
        api_params = {
            **self.base_params,
            "messages": [{"role": "user", "content": query}],
            "system": system_content
        }
        
        # Add tools if available
        if tools:
            api_params["tools"] = tools
            api_params["tool_choice"] = {"type": "auto"}
        
        # Get response from Claude
        response = self.client.messages.create(**api_params)
        
        # Handle tool execution if needed
        if response.stop_reason == "tool_use" and tool_manager:
            return self._handle_tool_execution(response, api_params, tool_manager)
        
        # Return direct response
        return response.content[0].text
    
    def _handle_tool_execution(self, initial_response, base_params: Dict[str, Any], tool_manager):
        """
        Handle execution of tool calls with support for sequential multi-round tool use.

        Allows Claude to make up to MAX_TOOL_ROUNDS sequential tool calls to gather
        information for complex queries like comparisons or multi-part questions.

        Args:
            initial_response: The response containing tool use requests
            base_params: Base API parameters (including tools)
            tool_manager: Manager to execute tools

        Returns:
            Final response text after tool execution (potentially multiple rounds)
        """
        from config import config

        MAX_ROUNDS = config.MAX_TOOL_ROUNDS
        round_count = 0

        # Initialize message history from base params
        messages = base_params["messages"].copy()
        current_response = initial_response

        # Iterative loop for sequential tool calling
        while round_count < MAX_ROUNDS:
            round_count += 1

            # Check if current response wants to use tools
            if current_response.stop_reason != "tool_use":
                # Claude decided not to use tools - return final answer
                break

            # Add Claude's response (with tool requests) to messages
            messages.append({
                "role": "assistant",
                "content": current_response.content
            })

            # Execute all requested tools
            tool_results = []
            for content_block in current_response.content:
                if content_block.type == "tool_use":
                    try:
                        tool_result = tool_manager.execute_tool(
                            content_block.name,
                            **content_block.input
                        )
                    except Exception as e:
                        # Handle tool execution errors gracefully
                        tool_result = f"Error executing tool: {str(e)}"

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": content_block.id,
                        "content": tool_result
                    })

            # Add tool results to messages
            if tool_results:
                messages.append({
                    "role": "user",
                    "content": tool_results
                })

            # Prepare next API call - KEEP TOOLS AVAILABLE
            next_params = {
                **self.base_params,
                "messages": messages,
                "system": base_params["system"],
                "tools": base_params.get("tools"),      # Critical: preserve tools
                "tool_choice": {"type": "auto"}          # Let Claude decide
            }

            # Make next API call
            current_response = self.client.messages.create(**next_params)

            # Loop continues - check stop_reason in next iteration

        # Extract final text response
        # Handle both pure text responses and mixed content
        final_text = ""
        for content_block in current_response.content:
            if hasattr(content_block, 'text'):
                final_text += content_block.text

        return final_text if final_text else current_response.content[0].text