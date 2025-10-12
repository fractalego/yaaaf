import unittest
from yaaaf.server.accessories import StreamStatus, update_stream_status, get_stream_status


class TestStatusTracking(unittest.TestCase):
    def test_stream_status_creation(self):
        """Test that StreamStatus objects are created correctly."""
        status = StreamStatus()
        
        self.assertEqual(status.goal, "")
        self.assertEqual(status.current_agent, "")
        self.assertEqual(status.is_active, False)

    def test_update_stream_status(self):
        """Test that stream status can be updated."""
        stream_id = "test_stream_123"
        
        # Update goal
        update_stream_status(stream_id, goal="Test goal")
        status = get_stream_status(stream_id)
        
        self.assertIsNotNone(status)
        self.assertEqual(status.goal, "Test goal")
        self.assertEqual(status.current_agent, "")
        
        # Update agent
        update_stream_status(stream_id, current_agent="test_agent")
        status = get_stream_status(stream_id)
        
        self.assertEqual(status.goal, "Test goal")
        self.assertEqual(status.current_agent, "test_agent")

    def test_get_nonexistent_stream_status(self):
        """Test that getting status for non-existent stream returns None."""
        status = get_stream_status("nonexistent_stream")
        self.assertIsNone(status)


if __name__ == "__main__":
    unittest.main()