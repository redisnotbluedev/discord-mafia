import pytest
from classes.scheduler import GameConfig, MafiaSchedulerConfig

def test_game_config_clamp_overflow():
    """Test that clamp reduces town then mafia when total players decreases."""
    config_data: MafiaSchedulerConfig = {
        "mafia": 5, "town": 5, 
        "role_Doctor": True, "role_Sheriff": True, 
        "role_Vigilante": False, "role_Jester": False
    }
    config = GameConfig(config_data)
    
    # Total players 8, current 5+5=10. 
    # max_mafia = min(8//2, 8-3) = min(4, 5) = 4.
    config.clamp(8)
    assert config["mafia"] == 4
    assert config["town"] == 4
    
    # Total players 4, current 4+4=8. 
    # With 4 players, max_mafia = min(4//2, 4-3) = min(2, 1) = 1.
    config.clamp(4)
    assert config["mafia"] == 1
    assert config["town"] == 3

def test_game_config_clamp_underflow():
    """Test that clamp increases town when total players increases."""
    config_data: MafiaSchedulerConfig = {
        "mafia": 1, "town": 1, 
        "role_Doctor": True, "role_Sheriff": True, 
        "role_Vigilante": False, "role_Jester": False
    }
    config = GameConfig(config_data)
    
    # Total players 5, current 1+1=2. Should add to town.
    config.clamp(5)
    assert config["mafia"] == 1
    assert config["town"] == 4

def test_game_config_smart_defaults():
    """Test the 1/3 mafia rule and town-priority distribution."""
    config_data: MafiaSchedulerConfig = {
        "mafia": 1, "town": 1, 
        "role_Doctor": True, "role_Sheriff": True, 
        "role_Vigilante": False, "role_Jester": False
    }
    config = GameConfig(config_data)
    
    # 9 players: 9//3 = 3 mafia, 6 town
    config.apply_smart_defaults(9)
    assert config["mafia"] == 3
    assert config["town"] == 6
    
    # 5 players: min(5//3, 5-3) = 1.
    config.apply_smart_defaults(5)
    assert config["mafia"] == 1
    assert config["town"] == 4

def test_game_config_increment_mafia():
    """Test that increment_mafia respects constraints and adjusts town."""
    config_data: MafiaSchedulerConfig = {
        "mafia": 1, "town": 4, 
        "role_Doctor": True, "role_Sheriff": True, 
        "role_Vigilante": False, "role_Jester": False
    }
    config = GameConfig(config_data)
    
    # 5 players. Mafia can go up to 2 (since 2 <= 5//2 and 2 <= 5-3).
    config.increment_mafia(5)
    assert config["mafia"] == 2
    assert config["town"] == 3
    
    # Increment again. 3 <= 5-3 is false.
    config.increment_mafia(5)
    assert config["mafia"] == 2

def test_game_config_increment_town():
    """Test that increment_town respects total players and pushes mafia down."""
    config_data: MafiaSchedulerConfig = {
        "mafia": 2, "town": 3, 
        "role_Doctor": True, "role_Sheriff": True, 
        "role_Vigilante": False, "role_Jester": False
    }
    config = GameConfig(config_data)
    
    # 5 players. Town is 3. Max town is total - 1 = 4.
    config.increment_town(5)
    assert config["town"] == 4
    assert config["mafia"] == 1
