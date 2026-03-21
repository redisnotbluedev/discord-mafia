import pytest
from unittest.mock import MagicMock, patch, mock_open
import json
import discord

from classes.player import Player, AIAbstraction, create_ai_players


class TestPlayerInit:
    def test_player_init_with_mock_user(self, mock_user):
        player = Player(mock_user)
        assert player.user is mock_user
        assert player.role is None
        assert player.name == "TestUser"
        assert player.alive is True
        assert player.role_state == {}
        assert player.death_reason is None

    def test_player_init_with_ai_abstraction(self):
        ai = AIAbstraction("gpt-4o", "GPT", "https://example.com/avatar.png")
        player = Player(ai)
        assert player.user is ai
        assert player.role is None
        assert player.name == "GPT"
        assert player.alive is True
        assert player.role_state == {}
        assert player.death_reason is None

    def test_player_init_preserves_user_name(self):
        user = MagicMock(spec=discord.Member)
        user.name = "CustomName"
        player = Player(user)
        assert player.name == "CustomName"


class TestPlayerRoleOrDie:
    def test_role_or_die_returns_role_when_set(self, mock_user):
        player = Player(mock_user)
        mock_role = MagicMock()
        player.role = mock_role
        assert player.role_or_die is mock_role

    def test_role_or_die_raises_type_error_when_none(self, mock_user):
        player = Player(mock_user)
        with pytest.raises(TypeError, match="role unexpectedly none"):
            _ = player.role_or_die


class TestAIAbstractionInit:
    def test_ai_abstraction_init_basic(self):
        ai = AIAbstraction("gpt-4o", "GPT", "https://example.com/avatar.png")
        assert ai.model == "gpt-4o"
        assert ai.id == -1
        assert ai.name == "GPT"
        assert ai.avatar == "https://example.com/avatar.png"

    def test_ai_abstraction_init_without_avatar(self):
        ai = AIAbstraction("gpt-4o", "GPT")
        assert ai.model == "gpt-4o"
        assert ai.id == -1
        assert ai.name == "GPT"
        assert ai.avatar is None

    def test_ai_abstraction_creates_player(self):
        ai = AIAbstraction("gpt-4o", "GPT", "https://example.com/avatar.png")
        assert isinstance(ai.player, Player)
        assert ai.player.user is ai
        assert ai.player.name == "GPT"

    def test_ai_abstraction_player_has_correct_attributes(self):
        ai = AIAbstraction("claude-3", "Claude", "https://example.com/claude.png")
        player = ai.player
        assert player.role is None
        assert player.alive is True
        assert player.role_state == {}
        assert player.death_reason is None


class TestCreateAIPlayers:
    def test_create_ai_players_all_models(self):
        models_data = {
            "models": [
                {"model": "gpt-4o", "name": "GPT-4", "avatar": "gpt4.png"},
                {"model": "claude-3", "name": "Claude", "avatar": "claude.png"}
            ],
            "avatar_template": "https://example.com/{}"
        }
        
        with patch("builtins.open", mock_open(read_data=json.dumps(models_data))):
            players = create_ai_players()
        
        assert len(players) == 2
        assert all(isinstance(p, Player) for p in players)
        assert players[0].name == "GPT-4"
        assert players[1].name == "Claude"

    def test_create_ai_players_with_selected_models(self):
        models_data = {
            "models": [
                {"model": "gpt-4o", "name": "GPT-4", "avatar": "gpt4.png"},
                {"model": "claude-3", "name": "Claude", "avatar": "claude.png"},
                {"model": "llama-2", "name": "Llama", "avatar": "llama.png"}
            ],
            "avatar_template": "https://example.com/{}"
        }
        
        with patch("builtins.open", mock_open(read_data=json.dumps(models_data))):
            players = create_ai_players(selected_models=["gpt-4o", "llama-2"])
        
        assert len(players) == 2
        assert players[0].name == "GPT-4"
        assert players[1].name == "Llama"

    def test_create_ai_players_empty_selection(self):
        models_data = {
            "models": [
                {"model": "gpt-4o", "name": "GPT-4", "avatar": "gpt4.png"},
                {"model": "claude-3", "name": "Claude", "avatar": "claude.png"}
            ],
            "avatar_template": "https://example.com/{}"
        }
        
        with patch("builtins.open", mock_open(read_data=json.dumps(models_data))):
            players = create_ai_players(selected_models=[])
        
        assert len(players) == 0

    def test_create_ai_players_avatar_url_fallback(self):
        models_data = {
            "models": [
                {"model": "gpt-4o", "name": "GPT-4", "avatar_url": "gpt4.png"}
            ],
            "avatar_template": "https://example.com/{}"
        }
        
        with patch("builtins.open", mock_open(read_data=json.dumps(models_data))):
            players = create_ai_players()
        
        assert len(players) == 1
        assert players[0].user.avatar == "https://example.com/gpt4.png"

    def test_create_ai_players_missing_name_defaults_to_unknown(self):
        models_data = {
            "models": [
                {"model": "gpt-4o", "avatar": "gpt4.png"}
            ],
            "avatar_template": "https://example.com/{}"
        }
        
        with patch("builtins.open", mock_open(read_data=json.dumps(models_data))):
            players = create_ai_players()
        
        assert len(players) == 1
        assert players[0].name == "Unknown"

    def test_create_ai_players_returns_player_instances(self):
        models_data = {
            "models": [
                {"model": "gpt-4o", "name": "GPT-4", "avatar": "gpt4.png"}
            ],
            "avatar_template": "https://example.com/{}"
        }
        
        with patch("builtins.open", mock_open(read_data=json.dumps(models_data))):
            players = create_ai_players()
        
        player = players[0]
        assert isinstance(player, Player)
        assert player.role is None
        assert player.alive is True
        assert player.role_state == {}
        assert player.death_reason is None

    def test_create_ai_players_ai_abstraction_has_correct_model(self):
        models_data = {
            "models": [
                {"model": "gpt-4o", "name": "GPT-4", "avatar": "gpt4.png"}
            ],
            "avatar_template": "https://example.com/{}"
        }
        
        with patch("builtins.open", mock_open(read_data=json.dumps(models_data))):
            players = create_ai_players()
        
        ai = players[0].user
        assert ai.model == "gpt-4o"
        assert ai.id == -1
