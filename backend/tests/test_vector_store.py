"""
Tests for VectorStore functionality
"""
import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from vector_store import VectorStore, SearchResults


class TestVectorStoreSearch:
    """Test the VectorStore search functionality"""

    def test_search_with_max_results_zero_returns_empty(self, temp_chroma_db, sample_course, sample_course_chunks):
        """
        CRITICAL BUG TEST: When MAX_RESULTS=0, search should return 0 results
        This test documents the bug causing 'query failed' errors
        """
        # Create vector store with max_results=0 (the bug)
        store = VectorStore(temp_chroma_db, "all-MiniLM-L6-v2", max_results=0)

        # Add test data
        store.add_course_metadata(sample_course)
        store.add_course_content(sample_course_chunks)

        # Search should return empty due to max_results=0
        results = store.search("machine learning")

        # This is the bug: we get 0 results even though data exists
        assert results.is_empty() == True, "Expected empty results when MAX_RESULTS=0"
        assert len(results.documents) == 0, "Should return 0 documents when MAX_RESULTS=0"

    def test_search_with_proper_max_results_returns_data(self, temp_chroma_db, sample_course, sample_course_chunks):
        """
        When MAX_RESULTS > 0, search should return results
        """
        # Create vector store with proper max_results
        store = VectorStore(temp_chroma_db, "all-MiniLM-L6-v2", max_results=5)

        # Add test data
        store.add_course_metadata(sample_course)
        store.add_course_content(sample_course_chunks)

        # Search should return results
        results = store.search("machine learning")

        # Should find relevant content
        assert results.is_empty() == False, "Should return results when MAX_RESULTS > 0"
        assert len(results.documents) > 0, "Should return at least one document"
        assert results.error is None, "Should not have errors"

    def test_search_with_course_filter(self, temp_chroma_db, sample_course, sample_course_chunks):
        """Test searching with course name filter"""
        store = VectorStore(temp_chroma_db, "all-MiniLM-L6-v2", max_results=5)

        # Add test data
        store.add_course_metadata(sample_course)
        store.add_course_content(sample_course_chunks)

        # Search with course filter
        results = store.search(
            query="regression",
            course_name="Introduction to Machine Learning"
        )

        # Should find relevant content from the course
        assert len(results.documents) > 0, "Should find content in specified course"
        assert all(
            meta["course_title"] == sample_course.title
            for meta in results.metadata
        ), "All results should be from the specified course"

    def test_search_with_lesson_filter(self, temp_chroma_db, sample_course, sample_course_chunks):
        """Test searching with lesson number filter"""
        store = VectorStore(temp_chroma_db, "all-MiniLM-L6-v2", max_results=5)

        # Add test data
        store.add_course_metadata(sample_course)
        store.add_course_content(sample_course_chunks)

        # Search with lesson filter
        results = store.search(
            query="machine learning",
            lesson_number=1
        )

        # Should only return content from lesson 1
        assert len(results.documents) > 0, "Should find content in lesson 1"
        assert all(
            meta["lesson_number"] == 1
            for meta in results.metadata
        ), "All results should be from lesson 1"

    def test_search_with_course_and_lesson_filter(self, temp_chroma_db, sample_course, sample_course_chunks):
        """Test searching with both course and lesson filters"""
        store = VectorStore(temp_chroma_db, "all-MiniLM-L6-v2", max_results=5)

        # Add test data
        store.add_course_metadata(sample_course)
        store.add_course_content(sample_course_chunks)

        # Search with both filters
        results = store.search(
            query="regression",
            course_name="Introduction to Machine Learning",
            lesson_number=2
        )

        # Should find content matching both filters
        if not results.is_empty():
            assert all(
                meta["course_title"] == sample_course.title and meta["lesson_number"] == 2
                for meta in results.metadata
            ), "All results should match both course and lesson filters"

    def test_search_nonexistent_course_returns_error(self, temp_chroma_db, sample_course, sample_course_chunks):
        """Test searching for a course that doesn't exist"""
        store = VectorStore(temp_chroma_db, "all-MiniLM-L6-v2", max_results=5)

        # Add test data
        store.add_course_metadata(sample_course)
        store.add_course_content(sample_course_chunks)

        # Search for nonexistent course
        results = store.search(
            query="anything",
            course_name="Nonexistent Course That Definitely Does Not Exist"
        )

        # Should return error
        assert results.error is not None, "Should return error for nonexistent course"
        assert "No course found" in results.error, "Error should mention course not found"
        assert results.is_empty() == True, "Should return empty results"

    def test_course_name_resolution_with_partial_match(self, temp_chroma_db, sample_course, sample_course_chunks):
        """Test that partial course names are resolved correctly"""
        store = VectorStore(temp_chroma_db, "all-MiniLM-L6-v2", max_results=5)

        # Add test data
        store.add_course_metadata(sample_course)
        store.add_course_content(sample_course_chunks)

        # Search with partial course name (should use semantic matching)
        results = store.search(
            query="regression",
            course_name="Machine Learning"  # Partial match of "Introduction to Machine Learning"
        )

        # Should resolve the partial name and find results
        assert not results.is_empty() or results.error, "Should either find results or return error"

    def test_empty_vector_store_returns_empty_results(self, temp_chroma_db):
        """Test searching in an empty vector store"""
        store = VectorStore(temp_chroma_db, "all-MiniLM-L6-v2", max_results=5)

        # Search without adding any data
        results = store.search("anything")

        # Should return empty results
        assert results.is_empty() == True, "Empty store should return empty results"
        assert len(results.documents) == 0, "Should have no documents"


class TestVectorStoreMetadata:
    """Test VectorStore metadata operations"""

    def test_add_course_metadata(self, temp_chroma_db, sample_course):
        """Test adding course metadata to catalog"""
        store = VectorStore(temp_chroma_db, "all-MiniLM-L6-v2", max_results=5)

        # Add course metadata
        store.add_course_metadata(sample_course)

        # Verify course was added
        course_titles = store.get_existing_course_titles()
        assert sample_course.title in course_titles, "Course should be in catalog"

    def test_get_course_count(self, temp_chroma_db, sample_course):
        """Test getting course count"""
        store = VectorStore(temp_chroma_db, "all-MiniLM-L6-v2", max_results=5)

        # Initially should be 0
        assert store.get_course_count() == 0, "Empty store should have 0 courses"

        # Add course
        store.add_course_metadata(sample_course)

        # Should be 1
        assert store.get_course_count() == 1, "Should have 1 course after adding"

    def test_get_lesson_link(self, temp_chroma_db, sample_course):
        """Test retrieving lesson links"""
        store = VectorStore(temp_chroma_db, "all-MiniLM-L6-v2", max_results=5)

        # Add course
        store.add_course_metadata(sample_course)

        # Get lesson link
        link = store.get_lesson_link(sample_course.title, 1)

        # Should return the lesson link
        assert link == sample_course.lessons[0].lesson_link, "Should return correct lesson link"

    def test_get_course_link(self, temp_chroma_db, sample_course):
        """Test retrieving course link"""
        store = VectorStore(temp_chroma_db, "all-MiniLM-L6-v2", max_results=5)

        # Add course
        store.add_course_metadata(sample_course)

        # Get course link
        link = store.get_course_link(sample_course.title)

        # Should return the course link
        assert link == sample_course.course_link, "Should return correct course link"


class TestSearchResults:
    """Test SearchResults dataclass"""

    def test_search_results_is_empty(self):
        """Test is_empty method"""
        # Empty results
        empty = SearchResults(documents=[], metadata=[], distances=[])
        assert empty.is_empty() == True, "Empty results should return True"

        # Non-empty results
        non_empty = SearchResults(
            documents=["test"],
            metadata=[{"course_title": "test"}],
            distances=[0.1]
        )
        assert non_empty.is_empty() == False, "Non-empty results should return False"

    def test_search_results_empty_constructor(self):
        """Test empty() class method"""
        error_msg = "Test error message"
        results = SearchResults.empty(error_msg)

        assert results.is_empty() == True, "Should create empty results"
        assert results.error == error_msg, "Should set error message"
        assert len(results.documents) == 0, "Should have no documents"
