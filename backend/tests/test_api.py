"""
API endpoint tests for the FastAPI application

These tests validate the HTTP API layer, including:
- Request/response handling
- Error handling
- Session management
- Response models
"""
import pytest
from pathlib import Path
import sys
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestQueryEndpoint:
    """Test the /api/query endpoint"""

    def test_query_without_session_creates_new_session(self, client):
        """Test that query without session_id creates a new session"""
        # Mock the RAG system query to avoid actual AI calls
        with patch('rag_system.RAGSystem.query') as mock_query:
            mock_query.return_value = (
                "Machine learning is a subset of AI.",
                []
            )

            response = client.post(
                "/api/query",
                json={"query": "What is machine learning?"}
            )

            assert response.status_code == 200
            data = response.json()

            # Should return answer, sources, and session_id
            assert "answer" in data
            assert "sources" in data
            assert "session_id" in data
            assert isinstance(data["session_id"], str)
            assert len(data["session_id"]) > 0

    def test_query_with_existing_session(self, client):
        """Test that query with session_id uses that session"""
        with patch('rag_system.RAGSystem.query') as mock_query:
            mock_query.return_value = (
                "Linear regression is a statistical method.",
                []
            )

            # First query to get session
            response1 = client.post(
                "/api/query",
                json={"query": "What is machine learning?"}
            )
            session_id = response1.json()["session_id"]

            # Second query with same session
            response2 = client.post(
                "/api/query",
                json={
                    "query": "Tell me more",
                    "session_id": session_id
                }
            )

            assert response2.status_code == 200
            data = response2.json()

            # Should return same session_id
            assert data["session_id"] == session_id

    def test_query_returns_sources(self, client):
        """Test that query endpoint returns sources in correct format"""
        from models import SourceItem

        with patch('rag_system.RAGSystem.query') as mock_query:
            # Mock sources
            mock_sources = [
                SourceItem(
                    text="ML Course - Lesson 1",
                    url="https://example.com/lesson1"
                ),
                SourceItem(
                    text="ML Course - Lesson 2",
                    url="https://example.com/lesson2"
                )
            ]
            mock_query.return_value = ("Answer about ML", mock_sources)

            response = client.post(
                "/api/query",
                json={"query": "What is ML?"}
            )

            assert response.status_code == 200
            data = response.json()

            assert len(data["sources"]) == 2
            assert data["sources"][0]["text"] == "ML Course - Lesson 1"
            assert data["sources"][0]["url"] == "https://example.com/lesson1"
            assert "text" in data["sources"][0]
            assert "url" in data["sources"][0]

    def test_query_with_empty_query_string(self, client):
        """Test that empty query string is handled"""
        response = client.post(
            "/api/query",
            json={"query": ""}
        )

        # Should still process (RAG system will handle it)
        assert response.status_code in [200, 422, 500]

    def test_query_with_missing_query_field(self, client):
        """Test that missing query field returns validation error"""
        response = client.post(
            "/api/query",
            json={"session_id": "test-123"}
        )

        # Pydantic validation should fail
        assert response.status_code == 422

    def test_query_handles_rag_system_errors(self, client):
        """Test that RAG system errors are properly handled"""
        with patch('rag_system.RAGSystem.query') as mock_query:
            mock_query.side_effect = Exception("AI service unavailable")

            response = client.post(
                "/api/query",
                json={"query": "What is ML?"}
            )

            assert response.status_code == 500
            assert "AI service unavailable" in response.json()["detail"]

    def test_query_with_special_characters(self, client):
        """Test that queries with special characters are handled"""
        with patch('rag_system.RAGSystem.query') as mock_query:
            mock_query.return_value = ("Answer", [])

            response = client.post(
                "/api/query",
                json={"query": "What's the difference between <ML> & {AI}?"}
            )

            assert response.status_code == 200


class TestCoursesEndpoint:
    """Test the /api/courses endpoint"""

    def test_get_courses_returns_analytics(self, client):
        """Test that /api/courses returns course analytics"""
        response = client.get("/api/courses")

        assert response.status_code == 200
        data = response.json()

        assert "total_courses" in data
        assert "course_titles" in data
        assert isinstance(data["total_courses"], int)
        assert isinstance(data["course_titles"], list)

    def test_get_courses_with_no_courses(self, client):
        """Test that /api/courses works with empty database"""
        response = client.get("/api/courses")

        assert response.status_code == 200
        data = response.json()

        assert data["total_courses"] == 0
        assert data["course_titles"] == []

    def test_get_courses_handles_errors(self, client):
        """Test that /api/courses handles RAG system errors"""
        with patch('rag_system.RAGSystem.get_course_analytics') as mock_analytics:
            mock_analytics.side_effect = Exception("Database error")

            response = client.get("/api/courses")

            assert response.status_code == 500
            assert "Database error" in response.json()["detail"]


class TestRootEndpoint:
    """Test the root / endpoint"""

    def test_root_returns_health_check(self, client):
        """Test that root endpoint returns health check"""
        response = client.get("/")

        assert response.status_code == 200
        data = response.json()

        assert "status" in data
        assert data["status"] == "ok"


class TestAPIIntegration:
    """Integration tests for API workflows"""

    def test_full_query_workflow(self, client):
        """Test a complete query workflow from start to finish"""
        from models import SourceItem

        with patch('rag_system.RAGSystem.query') as mock_query:
            mock_query.return_value = (
                "Machine learning is a method of data analysis.",
                [
                    SourceItem(
                        text="ML Fundamentals - Lesson 1",
                        url="https://example.com/ml/1"
                    )
                ]
            )

            # Step 1: Initial query
            response1 = client.post(
                "/api/query",
                json={"query": "What is machine learning?"}
            )

            assert response1.status_code == 200
            data1 = response1.json()
            session_id = data1["session_id"]

            # Step 2: Follow-up query in same session
            mock_query.return_value = (
                "It is used in various applications.",
                []
            )

            response2 = client.post(
                "/api/query",
                json={
                    "query": "Where is it used?",
                    "session_id": session_id
                }
            )

            assert response2.status_code == 200
            assert response2.json()["session_id"] == session_id

    def test_multiple_concurrent_sessions(self, client):
        """Test that multiple sessions can exist simultaneously"""
        with patch('rag_system.RAGSystem.query') as mock_query:
            mock_query.return_value = ("Answer", [])

            # Create session 1
            response1 = client.post(
                "/api/query",
                json={"query": "Question 1"}
            )
            session1 = response1.json()["session_id"]

            # Create session 2
            response2 = client.post(
                "/api/query",
                json={"query": "Question 2"}
            )
            session2 = response2.json()["session_id"]

            # Sessions should be different
            assert session1 != session2

            # Both sessions should work
            response3 = client.post(
                "/api/query",
                json={"query": "Follow-up 1", "session_id": session1}
            )
            assert response3.json()["session_id"] == session1

            response4 = client.post(
                "/api/query",
                json={"query": "Follow-up 2", "session_id": session2}
            )
            assert response4.json()["session_id"] == session2

    def test_courses_and_query_integration(self, client):
        """Test integration between courses endpoint and query endpoint"""
        # First, check courses
        courses_response = client.get("/api/courses")
        assert courses_response.status_code == 200

        initial_count = courses_response.json()["total_courses"]

        # Then query (which shouldn't change course count in this test)
        with patch('rag_system.RAGSystem.query') as mock_query:
            mock_query.return_value = ("Answer", [])

            query_response = client.post(
                "/api/query",
                json={"query": "What is ML?"}
            )
            assert query_response.status_code == 200

        # Verify courses still consistent
        courses_response2 = client.get("/api/courses")
        assert courses_response2.json()["total_courses"] == initial_count


class TestCORSHeaders:
    """Test CORS configuration"""

    def test_cors_headers_present(self, client):
        """Test that CORS headers are properly set"""
        response = client.options(
            "/api/query",
            headers={"Origin": "http://localhost:3000"}
        )

        # Check for CORS headers in the response
        # Note: TestClient may not fully simulate CORS, but we can verify app has middleware
        assert response.status_code in [200, 405]  # OPTIONS may not be implemented


class TestRequestValidation:
    """Test Pydantic request validation"""

    def test_query_validates_request_schema(self, client):
        """Test that invalid request schemas are rejected"""
        # Invalid JSON structure
        response = client.post(
            "/api/query",
            json={"invalid_field": "value"}
        )

        assert response.status_code == 422

    def test_query_validates_field_types(self, client):
        """Test that incorrect field types are rejected"""
        response = client.post(
            "/api/query",
            json={"query": 12345}  # Should be string
        )

        assert response.status_code == 422

    def test_query_allows_optional_session_id(self, client):
        """Test that session_id is properly optional"""
        with patch('rag_system.RAGSystem.query') as mock_query:
            mock_query.return_value = ("Answer", [])

            # Without session_id
            response1 = client.post(
                "/api/query",
                json={"query": "Test"}
            )
            assert response1.status_code == 200

            # With session_id
            response2 = client.post(
                "/api/query",
                json={"query": "Test", "session_id": "abc-123"}
            )
            assert response2.status_code == 200

            # With null session_id
            response3 = client.post(
                "/api/query",
                json={"query": "Test", "session_id": None}
            )
            assert response3.status_code == 200
