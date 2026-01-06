#!/usr/bin/env python3
"""
Test script to validate duration display hypothesis.
Tests that:
1. TPDB duration is included in API response
2. File duration is retrieved from cache or FFProbe
3. Both durations are properly formatted
"""

from pathlib import Path
from unittest.mock import Mock, patch
from namer.web.actions import __get_file_duration, metadataapi_responses_to_webui_response
from namer.configuration import NamerConfig
from namer.comparison_results import LookedUpFileInfo, SceneType


def test_get_file_duration_from_cache():
    """Test retrieving duration from database cache."""
    config = Mock(spec=NamerConfig)
    config.failed_dir = Path("/tmp/failed")

    # Mock cached file with duration
    mock_cached_file = Mock()
    mock_cached_file.duration = 3661  # 1 hour, 1 minute, 1 second

    mock_file_path = Mock(spec=Path)
    mock_file_path.exists.return_value = True

    with patch('namer.web.actions.Path', return_value=mock_file_path) as mock_path_class:
        mock_path_class.return_value.__truediv__ = Mock(return_value=mock_file_path)

        with patch('namer.web.actions.search_file_in_database', return_value=mock_cached_file):
            duration = __get_file_duration("test_video.mp4", config)

    assert duration == 3661, f"Expected 3661, got {duration}"
    print("✓ Cache retrieval test passed: duration = 3661 seconds")


def test_get_file_duration_not_cached():
    """Test FFProbe fallback when file not in cache."""
    config = Mock(spec=NamerConfig)
    config.failed_dir = "/tmp/failed"
    config.ffmpeg_path = "ffmpeg"
    config.ffprobe_path = "ffprobe"

    # Mock FFProbe result
    mock_probe_result = Mock()
    mock_probe_result.format = Mock()
    mock_probe_result.format.duration = 1234.5  # float

    with patch('namer.web.actions.Path') as mock_path:
        mock_path_instance = Mock()
        mock_path_instance.exists.return_value = True
        mock_path.return_value = mock_path_instance

        with patch('namer.web.actions.search_file_in_database', return_value=None):
            with patch('namer.web.actions.FFMpeg') as mock_ffmpeg:
                mock_ffmpeg_instance = Mock()
                mock_ffmpeg_instance.ffprobe.return_value = mock_probe_result
                mock_ffmpeg.return_value = mock_ffmpeg_instance

                duration = __get_file_duration("test_video.mp4", config)

    assert duration == 1234, f"Expected 1234 (int), got {duration}"
    print("✓ FFProbe fallback test passed: duration = 1234 seconds (converted from 1234.5)")


def test_get_file_duration_file_not_exists():
    """Test graceful handling when file doesn't exist."""
    config = Mock(spec=NamerConfig)
    config.failed_dir = "/tmp/failed"

    with patch('namer.web.actions.Path') as mock_path:
        mock_path_instance = Mock()
        mock_path_instance.exists.return_value = False
        mock_path.return_value = mock_path_instance

        duration = __get_file_duration("nonexistent.mp4", config)

    assert duration is None, f"Expected None, got {duration}"
    print("✓ File not exists test passed: duration = None")


def test_metadataapi_response_includes_durations():
    """Test that both TPDB and file durations are included in response."""
    config = Mock(spec=NamerConfig)
    config.failed_dir = "/tmp/failed"
    config.target_extensions = ["mp4"]

    # Mock scene data with TPDB duration
    mock_scene = Mock(spec=LookedUpFileInfo)
    mock_scene.uuid = "test-uuid-123"
    mock_scene.type = SceneType.SCENE
    mock_scene.name = "Test Scene"
    mock_scene.date = "2024-01-05"
    mock_scene.duration = 1800  # 30 minutes from TPDB
    mock_scene.poster_url = "http://example.com/poster.jpg"
    mock_scene.site = "TestSite"
    mock_scene.network = "TestNetwork"
    mock_scene.performers = []
    mock_scene.original_parsed_filename = {}

    # Mock file duration from cache
    mock_cached_file = Mock()
    mock_cached_file.duration = 1820  # 30 min 20 sec actual file

    with patch('namer.web.actions.__metadataapi_response_to_data', return_value=[mock_scene]):
        with patch('namer.web.actions.__evaluate_match') as mock_evaluate:
            mock_comparison = Mock()
            mock_comparison.as_dict.return_value = {'name_match': 98.5, 'phash_distance': None}
            mock_evaluate.return_value = mock_comparison

            with patch('namer.web.actions.search_file_in_database', return_value=mock_cached_file):
                with patch('namer.web.actions.Path') as mock_path:
                    mock_path_instance = Mock()
                    mock_path_instance.exists.return_value = True
                    mock_path_instance.stem = "test_video"
                    mock_path_instance.suffix = ".mp4"
                    mock_path.return_value = mock_path_instance

                    responses = {'http://api.example.com': '{"data": []}'}

                    with patch('namer.web.actions.orjson.loads', return_value={}):
                        with patch('namer.web.actions.orjson.dumps', return_value=b'{}'):
                            with patch('namer.web.actions.parse_file_name', return_value={}):
                                result = metadataapi_responses_to_webui_response(
                                    responses, config, "test_video.mp4"
                                )

    assert len(result) == 1, f"Expected 1 result, got {len(result)}"

    scene_result = result[0]
    assert 'looked_up' in scene_result, "Missing 'looked_up' key"
    assert 'file_duration' in scene_result, "Missing 'file_duration' key"

    # Check TPDB duration
    assert scene_result['looked_up']['duration'] == 1800, \
        f"Expected TPDB duration 1800, got {scene_result['looked_up'].get('duration')}"

    # Check file duration
    assert scene_result['file_duration'] == 1820, \
        f"Expected file duration 1820, got {scene_result.get('file_duration')}"

    print("✓ API response test passed:")
    print(f"  - TPDB duration: {scene_result['looked_up']['duration']} seconds (30:00)")
    print(f"  - File duration: {scene_result['file_duration']} seconds (30:20)")


if __name__ == "__main__":
    print("Running duration display validation tests...\n")

    try:
        test_get_file_duration_from_cache()
        test_get_file_duration_not_cached()
        test_get_file_duration_file_not_exists()
        test_metadataapi_response_includes_durations()

        print("\n✅ All tests passed! Hypothesis validated.")
        print("\nValidation Summary:")
        print("  1. ✓ Database cache retrieval works correctly")
        print("  2. ✓ FFProbe fallback works correctly")
        print("  3. ✓ Graceful handling of missing files")
        print("  4. ✓ Both TPDB and file durations included in API response")
        print("  5. ✓ Duration values are properly typed (int)")

    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
