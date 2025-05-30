from __future__ import annotations

from abc import ABC, abstractmethod
from collections import Counter
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List

from bunker.core.loader import GameData
from bunker.domain.models.models import Game
from bunker.domain.game_init import GameInitializer

# ── настройки ──────────────────────────────────────────────
MAX_ATTRIBUTES = 7
FIRST_DISCUSSION_ATTR_INDEX = 1

ACTION_START_GAME = "start_game"
ACTION_OPEN_BUNKER = "open_bunker"
ACTION_REVEAL_NEXT = "reveal"
ACTION_END_DISCUSSION = "end_discussion"
ACTION_CAST_VOTE = "cast_vote"
ACTION_REVEAL_RESULTS = "reveal_results"

STATE_LOBBY = "lobby"
STATE_BUNKER = "bunker"
STATE_REVEAL = "reveal"
STATE_DISCUSSION = "discussion"
STATE_VOTING = "voting"
STATE_PHASE2 = "phase2"

# ─── data singletons ──────────────────────────────────────
_DATA_DIR = Path(r"C:/Users/Zema/bunker-game/backend/data")
_GAME_DATA = GameData(root=_DATA_DIR)
_INITIALIZER = GameInitializer(_GAME_DATA)


# ── инфраструктура ─────────────────────────────────────────
@dataclass
class GameAction:
    type: str
    data: Dict[str, Any]


class GameState(ABC):
    def __init__(self, game: Game):
        self.game = game

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def can_execute(self, a: GameAction) -> bool: ...

    @abstractmethod
    def execute(self, a: GameAction) -> "GameState | None": ...

    @abstractmethod
    def get_available_actions(self) -> List[str]: ...

    # utility
    def _alive_ids(self) -> List[str]:
        return self.game.alive_ids()


# ───────────────── Lobby ───────────────────────────────────
class LobbyState(GameState):
    name = STATE_LOBBY

    def can_execute(self, a: GameAction) -> bool:
        return a.type == ACTION_START_GAME

    def execute(self, a: GameAction) -> "GameState":
        self.game.shuffle_turn_order()
        self.game.turn = 1
        self.game.attr_index = 0
        self.game.status = "in_progress"
        _INITIALIZER.setup_new_game(self.game)
        return BunkerState(self.game)

    def get_available_actions(self) -> List[str]:
        return [ACTION_START_GAME]


# ───────────────── Bunker ──────────────────────────────────
class BunkerState(GameState):
    name = STATE_BUNKER

    def can_execute(self, a: GameAction) -> bool:
        return a.type == ACTION_OPEN_BUNKER

    def execute(self, a: GameAction) -> "GameState":
        if self.game.bunker_reveal_idx >= len(self.game.bunker_cards):
            raise ValueError("Все карты бункера уже раскрыты")

        # берём объект карты и превращаем в обычный dict
        card_obj = self.game.bunker_cards[self.game.bunker_reveal_idx]
        card_dict = asdict(card_obj)  # <-- фикc: сериализуемый dict

        # фиксируем открытую карту
        self.game.bunker_reveal_idx += 1
        self.game.revealed_bunker_cards.append(card_dict)

        # новый раунд, первый игрок снова нулевой
        self.game.current_idx = 0
        return RevealState(self.game)

    def get_available_actions(self) -> List[str]:
        return [ACTION_OPEN_BUNKER]


# ───────────────── Reveal ──────────────────────────────────
class RevealState(GameState):
    name = STATE_REVEAL

    def can_execute(self, a: GameAction) -> bool:
        return (
            a.type == ACTION_REVEAL_NEXT
            and {"player_id", "attribute"} <= a.data.keys()
            and self._valid(a.data["player_id"], a.data["attribute"])
        )

    def execute(self, a: GameAction) -> "GameState":
        pid, attr = a.data["player_id"], a.data["attribute"]
        self.game.characters[pid].reveal(attr)
        return self._advance()

    def get_available_actions(self) -> List[str]:
        return [ACTION_REVEAL_NEXT]

    # helpers ------------------------------------------------
    def _valid(self, pid: str, attr: str) -> bool:
        expected, allowed = self.get_current_reveal_info()
        return pid == expected and attr in allowed

    def _advance(self) -> "GameState":
        if self.game.current_idx >= len(self.game.turn_order) - 1:
            self.game.attr_index += 1  # ← фикс
            self.game.shuffle_turn_order()
            return DiscussionState(self.game)
        self.game.current_idx += 1
        return self

    def get_current_reveal_info(self) -> tuple[str, List[str]]:
        pid = self.game.turn_order[self.game.current_idx]
        char = self.game.characters[pid]
        if self.game.attr_index == 0:
            return pid, [self.game.first_round_attribute]
        return pid, [a for a in char.reveal_order if not char.is_revealed(a)]


# ───────────────── Discussion ──────────────────────────────
class DiscussionState(GameState):
    name = STATE_DISCUSSION

    def can_execute(self, a: GameAction) -> bool:
        return a.type == ACTION_END_DISCUSSION

    def execute(self, a: GameAction) -> "GameState":
        if self.game.attr_index == FIRST_DISCUSSION_ATTR_INDEX:
            return BunkerState(self.game)
        return VotingState(self.game)

    def get_available_actions(self) -> List[str]:
        return [ACTION_END_DISCUSSION]


# ───────────────── Voting ──────────────────────────────────
class VotingState(GameState):
    name = STATE_VOTING

    def can_execute(self, a: GameAction) -> bool:
        return a.type in (ACTION_CAST_VOTE, ACTION_REVEAL_RESULTS)

    def execute(self, a: GameAction) -> "GameState":
        if a.type == ACTION_CAST_VOTE:
            self.game.votes[a.data["voter_id"]] = a.data["target_id"]
            return self

        eliminated = Counter(self.game.votes.values()).most_common(1)[0][0]
        self.game.eliminated_ids.add(eliminated)
        self.game.votes.clear()

        alive = len(self._alive_ids())
        kicked = len(self.game.eliminated_ids)
        if alive <= kicked or self.game.attr_index >= MAX_ATTRIBUTES:
            return Phase2State(self.game)
        return BunkerState(self.game)

    def get_available_actions(self) -> List[str]:
        return (
            [ACTION_REVEAL_RESULTS]
            if len(self.game.votes) >= len(self._alive_ids())
            else [ACTION_CAST_VOTE]
        )


# ───────────────── Phase2 (stub) ───────────────────────────
class Phase2State(GameState):
    name = STATE_PHASE2

    def can_execute(self, a):
        return False

    def execute(self, a):
        return None

    def get_available_actions(self):
        return []
