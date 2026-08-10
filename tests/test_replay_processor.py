import pytest
import os
import tempfile
from core.models import MatchTimeline
from vision.replay_processor import ReplayProcessor

def test_parse_time_to_seconds():
    processor = ReplayProcessor(use_mock_vision=True)
    assert processor.parse_time_to_seconds("02:15") == 135
    assert processor.parse_time_to_seconds("00:45") == 45
    assert processor.parse_time_to_seconds("10:00") == 600
    assert processor.parse_time_to_seconds("01:02:03") == 3723
    assert processor.parse_time_to_seconds("") == 0
    assert processor.parse_time_to_seconds("invalid") == 0

def test_replay_processor_simulation():
    processor = ReplayProcessor(use_mock_vision=True)
    
    # Process a non-existent video path, which triggers simulation
    timeline = processor.process_video("non_existent_file.mp4", sample_interval_seconds=10)
    
    assert isinstance(timeline, MatchTimeline)
    assert len(timeline.events) > 0
    assert len(timeline.gold_diff_history) > 0
    
    # Check that events have valid fields
    for event in timeline.events:
        assert event.timestamp != ""
        assert event.event_type in ["objective", "gold", "kda", "item_buy", "warning", "general"]
        assert event.text != ""
        assert event.severity in ["info", "warning", "critical"]

    # Verify that KDA conforms to K/D/A format
    import re
    assert re.match(r'^\d+/\d+/\d+$', timeline.ally_kda)
    assert timeline.ally_total_gold > 0
    assert timeline.enemy_total_gold > 0

def test_save_timeline_to_json():
    processor = ReplayProcessor(use_mock_vision=True)
    timeline = processor.process_video("non_existent_file.mp4", sample_interval_seconds=15)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        json_path = os.path.join(tmpdir, "timeline.json")
        processor.save_timeline_to_json(timeline, json_path)
        
        assert os.path.exists(json_path)
        with open(json_path, "r") as f:
            import json
            data = json.load(f)
            assert "ally_total_gold" in data
            assert "gold_diff_history" in data
            assert "events" in data
            assert len(data["events"]) == len(timeline.events)
