import json
import pytest
from unittest.mock import patch, mock_open, MagicMock
import sys
import importlib


@pytest.fixture(autouse=True)
def _reload_data_module():
    original_data = sys.modules.get('data')
    if 'data' in sys.modules:
        del sys.modules['data']
    import data as fresh_data
    yield fresh_data
    if original_data:
        sys.modules['data'] = original_data


def test_save_writes_json_to_file():
    import data
    test_data = {"key": "value", "nested": {"inner": 123}}
    m = mock_open()
    with patch("builtins.open", m):
        data.save(test_data)
    
    m.assert_called_once_with("data.json", "w")


def test_save_empty_dict():
    import data
    test_data = {}
    m = mock_open()
    with patch("builtins.open", m):
        data.save(test_data)
    
    m.assert_called_once_with("data.json", "w")


def test_save_complex_nested_structure():
    import data
    test_data = {
        "guilds": {
            "123": {"name": "Guild1", "channels": [1, 2, 3]},
            "456": {"name": "Guild2", "channels": []}
        },
        "users": ["user1", "user2"]
    }
    m = mock_open()
    with patch("builtins.open", m):
        data.save(test_data)
    
    m.assert_called_once_with("data.json", "w")


def test_load_reads_json_from_file():
    import data
    test_data = {"key": "value", "number": 42}
    m = mock_open(read_data=json.dumps(test_data))
    with patch("builtins.open", m):
        result = data.load()
    
    assert result == test_data
    m.assert_called_once_with("data.json", "r")


def test_load_returns_empty_dict_on_file_not_found():
    import data
    m = mock_open()
    m.side_effect = [FileNotFoundError(), MagicMock()]
    with patch("builtins.open", m):
        result = data.load()
    
    assert result == {}


def test_load_returns_empty_dict_on_json_decode_error():
    import data
    m = mock_open(read_data="invalid json {")
    with patch("builtins.open", m):
        with patch("json.load", side_effect=json.JSONDecodeError("msg", "doc", 0)):
            result = data.load()
    
    assert result == {}


def test_load_creates_empty_file_on_file_not_found():
    import data
    m = mock_open()
    m.side_effect = [FileNotFoundError(), MagicMock()]
    with patch("builtins.open", m):
        result = data.load()
    
    assert result == {}
    assert m.call_count == 2


def test_load_returns_empty_dict_when_json_is_null():
    import data
    m = mock_open(read_data="null")
    with patch("builtins.open", m):
        result = data.load()
    
    assert result == {}


def test_load_returns_dict_with_data():
    import data
    test_data = {"guilds": {}, "users": [], "config": {"debug": True}}
    m = mock_open(read_data=json.dumps(test_data))
    with patch("builtins.open", m):
        result = data.load()
    
    assert result == test_data


def test_update_game_status_writes_1_when_game_running():
    import data
    bot = MagicMock()
    abstractor = MagicMock()
    abstractor.running = True
    bot.abstractors = [abstractor]
    
    m = mock_open()
    with patch("builtins.open", m), \
         patch("os.path.exists", return_value=False):
        data.update_game_status(bot)
    
    m.assert_called_once_with("games_ongoing.txt", "w")
    handle = m()
    handle.write.assert_called_once_with("1")


def test_update_game_status_writes_0_when_no_game_running():
    import data
    bot = MagicMock()
    abstractor = MagicMock()
    abstractor.running = False
    bot.abstractors = [abstractor]
    
    m = mock_open()
    with patch("builtins.open", m), \
         patch("os.path.exists", return_value=False):
        data.update_game_status(bot)
    
    m.assert_called_once_with("games_ongoing.txt", "w")
    handle = m()
    handle.write.assert_called_once_with("0")


def test_update_game_status_early_return_when_status_unchanged():
    import data
    bot = MagicMock()
    abstractor = MagicMock()
    abstractor.running = True
    bot.abstractors = [abstractor]
    
    m = mock_open(read_data="1")
    with patch("builtins.open", m), \
         patch("os.path.exists", return_value=True):
        data.update_game_status(bot)
    
    m.assert_called_once_with("games_ongoing.txt", "r")


def test_update_game_status_no_abstractors():
    import data
    bot = MagicMock()
    bot.abstractors = []
    
    m = mock_open()
    with patch("builtins.open", m), \
         patch("os.path.exists", return_value=False):
        data.update_game_status(bot)
    
    m.assert_called_once_with("games_ongoing.txt", "w")
    handle = m()
    handle.write.assert_called_once_with("0")


def test_update_game_status_bot_without_abstractors_attribute():
    import data
    bot = MagicMock(spec=[])
    
    m = mock_open()
    with patch("builtins.open", m), \
         patch("os.path.exists", return_value=False):
        data.update_game_status(bot)
    
    m.assert_called_once_with("games_ongoing.txt", "w")
    handle = m()
    handle.write.assert_called_once_with("0")


def test_update_game_status_multiple_abstractors_one_running():
    import data
    bot = MagicMock()
    abstractor1 = MagicMock()
    abstractor1.running = False
    abstractor2 = MagicMock()
    abstractor2.running = True
    abstractor3 = MagicMock()
    abstractor3.running = False
    bot.abstractors = [abstractor1, abstractor2, abstractor3]
    
    m = mock_open()
    with patch("builtins.open", m), \
         patch("os.path.exists", return_value=False):
        data.update_game_status(bot)
    
    m.assert_called_once_with("games_ongoing.txt", "w")
    handle = m()
    handle.write.assert_called_once_with("1")


def test_update_game_status_exception_handling():
    import data
    bot = MagicMock()
    bot.abstractors = []
    
    with patch("builtins.open", side_effect=Exception("File error")), \
         patch("os.path.exists", return_value=False):
        data.update_game_status(bot)


def test_update_game_status_writes_0_when_status_changed_from_1():
    import data
    bot = MagicMock()
    bot.abstractors = []
    
    m = mock_open(read_data="1")
    with patch("builtins.open", m), \
         patch("os.path.exists", return_value=True):
        data.update_game_status(bot)
    
    assert m.call_count == 2
    calls = m.call_args_list
    assert calls[0][0] == ("games_ongoing.txt", "r")
    assert calls[1][0] == ("games_ongoing.txt", "w")
