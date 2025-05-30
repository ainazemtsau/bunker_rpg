from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Set, Optional
import random
from uuid import uuid4
from bunker.domain.models.character import Character
import string
from datetime import datetime
import uuid


def _gen_player_id() -> str:
    return uuid4().hex[:8].upper()


def _gen_game_id(k: int = 6) -> str:
    import string

    return "".join(random.choices(string.ascii_uppercase + string.digits, k=k))


# ── helpers ─────────────────────────────────────────────────
def _gen_code(k: int = 6) -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=k))


# ───────────────── Player ─────────────────


@dataclass(slots=True)
class Player:
    name: str
    sid: str
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8].upper())
    joined_at: datetime = field(default_factory=datetime.utcnow)
    online: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "online": self.online,
            "joined_at": self.joined_at.isoformat(),
        }


def gen_code(k: int = 6) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(random.choices(alphabet, k=k))


# ── Game  (данные, без логики) ─────────────────────────────
@dataclass
class Game:
    host: Player
    id: str = field(default_factory=_gen_code)

    status: str = "waiting"  # waiting | in_progress | finished
    phase: str = "lobby"  # кэш-поле, обновляет движок

    players: Dict[str, Player] = field(default_factory=dict)
    characters: Dict[str, Character] = field(default_factory=dict)

    bunker_cards: List[Any] = field(default_factory=list)
    bunker_reveal_idx: int = 0
    revealed_bunker_cards: List[Any] = field(default_factory=list)
    phase2_pending_actions: List[Dict[str, Any]] = field(default_factory=list)
    crises: List[Any] = field(default_factory=list)
    actions: List[Any] = field(default_factory=list)

    eliminated_ids: Set[str] = field(default_factory=set)
    votes: Dict[str, str] = field(default_factory=dict)
    turn_order: List[str] = field(default_factory=list)
    current_idx: int = 0
    attr_index: int = 0
    first_round_attribute: Optional[str] = "profession"

    # === NEW: команды для фазы 2 ===
    team_in_bunker: set = field(default_factory=set)  # id игроков в бункере
    team_outside: set = field(default_factory=set)  # id вне бункера

    phase2_round: int = 1  # номер раунда
    phase2_team: str = "outside"  # чья очередь: "outside" | "bunker"
    phase2_team_order: list = field(default_factory=list)  # порядок ходов в команде
    phase2_team_current_idx: int = 0  # текущий индекс в очереди внутри команды
    phase2_team_actions: dict = field(
        default_factory=dict
    )  # {player_id: {action_type, params}}
    phase2_results: list = field(
        default_factory=list
    )  # [{round, team, actions: [...], summary: ...}]
    phase2_bunker_hp: int = 10  # здоровье бункера (MVP)
    winner: Optional[str] = None  # "bunker"|"outside"|None

    def reset_phase2(self):
        """Очистить все phase2-поля, если понадобится рестарт."""
        self.team_in_bunker.clear()
        self.team_outside.clear()
        self.phase2_turn_order.clear()
        self.phase2_current_idx = 0
        self.phase2_round = 1
        self.phase2_action_log.clear()
        self.phase2_pending_actions.clear()
        self.bunker_health = 10

    def alive_ids(self) -> List[str]:
        return [pid for pid in self.players if pid not in self.eliminated_ids]

    def shuffle_turn_order(self) -> None:
        self.turn_order = self.alive_ids()
        random.shuffle(self.turn_order)
        self.current_idx = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "status": self.status,
            "phase": self.phase,
            "attr_index": self.attr_index,
            "host_id": self.host.id,
            "players": [p.to_dict() for p in self.players.values()],
            "characters": {
                pid: c.to_public_dict() for pid, c in self.characters.items()
            },
            "bunker_reveal_idx": self.bunker_reveal_idx,
            "revealed_bunker_cards": self.revealed_bunker_cards,
            "eliminated_ids": list(self.eliminated_ids),
            "team_in_bunker": list(self.team_in_bunker),  # ← NEW
            "team_outside": list(self.team_outside),  # ← NEW
        }
