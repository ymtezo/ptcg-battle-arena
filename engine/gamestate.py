"""GameState and PlayerState models for Pokemon TCG."""

from dataclasses import dataclass, field
from typing import List, Optional, Dict
import copy
from engine.card import Card, CardType, PokemonStage


@dataclass
class PokemonInstance:
    """An instance of a Pokemon on the battlefield (Active or Bench)."""
    card: Card
    current_hp: int
    attached_energies: List[str] = field(default_factory=list)
    turns_in_play: int = 0
    evolved_this_turn: bool = False

    @property
    def is_knocked_out(self) -> bool:
        """Check if Pokemon has 0 HP."""
        return self.current_hp <= 0

    def take_damage(self, damage: int) -> None:
        """Apply damage, ensuring HP does not drop below 0."""
        self.current_hp = max(0, self.current_hp - damage)

    def attach_energy(self, energy_type: str) -> None:
        """Attach an energy to this Pokemon."""
        self.attached_energies.append(energy_type)

    def can_retreat(self) -> bool:
        """Check if Pokemon has enough energies to pay retreat cost."""
        return len(self.attached_energies) >= self.card.retreat_cost

    def pay_retreat_cost(self) -> None:
        """Discard energies to pay retreat cost."""
        cost = self.card.retreat_cost
        for _ in range(min(cost, len(self.attached_energies))):
            self.attached_energies.pop()

    def clone(self) -> "PokemonInstance":
        """Fast clone for search simulations."""
        return PokemonInstance(
            card=self.card,
            current_hp=self.current_hp,
            attached_energies=list(self.attached_energies),
            turns_in_play=self.turns_in_play,
            evolved_this_turn=self.evolved_this_turn,
        )


@dataclass
class PlayerState:
    """State of a single player in the game."""
    player_id: int
    name: str
    deck: List[Card] = field(default_factory=list)
    hand: List[Card] = field(default_factory=list)
    discard_pile: List[Card] = field(default_factory=list)
    prizes: List[Card] = field(default_factory=list)
    active_pokemon: Optional[PokemonInstance] = None
    bench: List[PokemonInstance] = field(default_factory=list)
    energy_attached_this_turn: bool = False
    supporter_played_this_turn: bool = False
    retreated_this_turn: bool = False

    @property
    def total_pokemon_count(self) -> int:
        """Return total active + bench Pokemon count."""
        count = 1 if self.active_pokemon is not None else 0
        return count + len(self.bench)

    def clone(self) -> "PlayerState":
        """Fast clone for search simulations."""
        return PlayerState(
            player_id=self.player_id,
            name=self.name,
            deck=list(self.deck),
            hand=list(self.hand),
            discard_pile=list(self.discard_pile),
            prizes=list(self.prizes),
            active_pokemon=self.active_pokemon.clone() if self.active_pokemon else None,
            bench=[b.clone() for b in self.bench],
            energy_attached_this_turn=self.energy_attached_this_turn,
            supporter_played_this_turn=self.supporter_played_this_turn,
            retreated_this_turn=self.retreated_this_turn,
        )


@dataclass
class GameState:
    """Complete snapshot of a match between two players."""
    turn_count: int = 1
    current_player_idx: int = 0
    players: List[PlayerState] = field(default_factory=list)
    winner: Optional[int] = None
    game_over_reason: Optional[str] = None
    log: List[str] = field(default_factory=list)

    @property
    def current_player(self) -> PlayerState:
        """Get the current active player state."""
        return self.players[self.current_player_idx]

    @property
    def opponent_player(self) -> PlayerState:
        """Get the opponent player state."""
        return self.players[1 - self.current_player_idx]

    @property
    def is_game_over(self) -> bool:
        """Check if game has concluded."""
        return self.winner is not None

    def clone(self) -> "GameState":
        """Deep clone state for lookahead planning."""
        return GameState(
            turn_count=self.turn_count,
            current_player_idx=self.current_player_idx,
            players=[self.players[0].clone(), self.players[1].clone()],
            winner=self.winner,
            game_over_reason=self.game_over_reason,
            log=list(self.log),
        )
