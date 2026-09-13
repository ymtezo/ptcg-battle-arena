"""Card definitions and data models for Pokemon TCG."""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any


class CardType(Enum):
    """Types of cards in Pokemon TCG."""
    POKEMON = "POKEMON"
    TRAINER_ITEM = "TRAINER_ITEM"
    TRAINER_SUPPORTER = "TRAINER_SUPPORTER"
    ENERGY = "ENERGY"


class PokemonStage(Enum):
    """Evolution stage of a Pokemon."""
    BASIC = "BASIC"
    STAGE_1 = "STAGE_1"
    STAGE_2 = "STAGE_2"


@dataclass
class Attack:
    """Represents a Pokemon attack."""
    name: str
    energy_cost: List[str]  # e.g., ["DARK", "COLORLESS", "COLORLESS"]
    damage: int
    bench_damage: int = 0


@dataclass
class Card:
    """Represents a single card template."""
    id: str
    name: str
    card_type: CardType
    stage: Optional[PokemonStage] = None
    evolves_from: Optional[str] = None
    hp: int = 0
    pokemon_type: Optional[str] = None
    prize_value: int = 1  # Standard is 1, ex / V is 2
    retreat_cost: int = 1
    weakness: Optional[str] = None
    attacks: List[Attack] = field(default_factory=list)
    effect: Optional[str] = None
    energy_type: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Card":
        """Create a Card instance from a dictionary definition."""
        card_type = CardType(data["card_type"])
        stage = PokemonStage(data["stage"]) if "stage" in data and data["stage"] else None

        attacks = []
        if "attacks" in data:
            for atk in data["attacks"]:
                attacks.append(
                    Attack(
                        name=atk["name"],
                        energy_cost=atk.get("energy_cost", []),
                        damage=atk.get("damage", 0),
                        bench_damage=atk.get("bench_damage", 0),
                    )
                )

        return cls(
            id=data["id"],
            name=data["name"],
            card_type=card_type,
            stage=stage,
            evolves_from=data.get("evolves_from"),
            hp=data.get("hp", 0),
            pokemon_type=data.get("pokemon_type"),
            prize_value=data.get("prize_value", 1),
            retreat_cost=data.get("retreat_cost", 1),
            weakness=data.get("weakness"),
            attacks=attacks,
            effect=data.get("effect"),
            energy_type=data.get("energy_type"),
        )
