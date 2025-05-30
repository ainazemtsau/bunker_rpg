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


@dataclass(slots=True)
class BunkerObjectState:
    """Состояние объекта бункера"""

    object_id: str
    name: str
    status: str = "working"  # working | damaged | destroyed

    def is_usable(self) -> bool:
        return self.status == "working"


@dataclass(slots=True)
class DebuffEffect:
    """Эффект дебафа"""

    effect_id: str
    name: str
    stat_penalties: Dict[str, int]
    remaining_rounds: int
    source: str  # откуда пришел дебаф


@dataclass(slots=True)
class PhobiaStatus:
    """Активный статус фобии"""

    phobia_name: str
    trigger_source: str  # что вызвало фобию
    affected_stats: Dict[str, int]  # какие статы обнулены


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

    eliminated_ids: Set[str] = field(default_factory=set)
    votes: Dict[str, str] = field(default_factory=dict)
    turn_order: List[str] = field(default_factory=list)
    current_idx: int = 0
    attr_index: int = 0
    first_round_attribute: Optional[str] = "profession"

    # === Phase2 consolidated fields ===
    team_in_bunker: Set[str] = field(default_factory=set)
    team_outside: Set[str] = field(default_factory=set)

    # Phase2 game state
    phase2_round: int = 1
    phase2_current_team: str = "outside"  # "outside" | "bunker"
    phase2_bunker_hp: int = 10
    phase2_morale: int = 10  # новое
    phase2_supplies: int = 10  # новое
    phase2_supplies_countdown: int = 0  # счетчик для поражения от голода
    phase2_morale_countdown: int = 0  # счетчик для поражения от морали

    # Объекты бункера и эффекты
    phase2_bunker_objects: Dict[str, BunkerObjectState] = field(default_factory=dict)
    phase2_team_debuffs: Dict[str, List[DebuffEffect]] = field(
        default_factory=dict
    )  # team -> debuffs
    phase2_player_phobias: Dict[str, PhobiaStatus] = field(
        default_factory=dict
    )  # player_id -> phobia
    phase2_active_statuses: List[str] = field(
        default_factory=list
    )  # глобальные статусы (пожар, заражение)

    phase2_action_queue: List[Dict[str, Any]] = field(default_factory=list)
    phase2_processed_actions: List[Dict[str, Any]] = field(default_factory=list)
    phase2_current_action_index: int = 0
    phase2_team_stats: Dict[str, Dict[str, int]] = field(default_factory=dict)

    # Phase2 results and winner
    phase2_action_log: List[Dict[str, Any]] = field(default_factory=list)
    winner: Optional[str] = None

    def reset_phase2(self):
        """Очистить все phase2-поля, если понадобится рестарт."""
        self.team_in_bunker.clear()
        self.team_outside.clear()
        self.phase2_round = 1
        self.phase2_current_team = "outside"
        self.phase2_bunker_hp = 10
        self.phase2_morale = 10
        self.phase2_supplies = 10
        self.phase2_supplies_countdown = 0
        self.phase2_morale_countdown = 0
        self.phase2_bunker_objects.clear()
        self.phase2_team_debuffs.clear()
        self.phase2_player_phobias.clear()
        self.phase2_active_statuses.clear()
        self.phase2_action_queue.clear()
        self.phase2_processed_actions.clear()
        self.phase2_current_action_index = 0
        self.phase2_team_stats.clear()
        self.phase2_action_log.clear()
        self.winner = None

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
            "team_in_bunker": list(self.team_in_bunker),
            "team_outside": list(self.team_outside),
        }
