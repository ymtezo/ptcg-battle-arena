"""Rule logic and legal action generation for Pokemon TCG."""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any
from engine.card import Card, CardType, PokemonStage, Attack
from engine.gamestate import GameState, PlayerState, PokemonInstance


class ActionType(Enum):
    """Types of actions a player can take on their turn."""
    PLAY_BASIC = "PLAY_BASIC"
    EVOLVE = "EVOLVE"
    ATTACH_ENERGY = "ATTACH_ENERGY"
    PLAY_ITEM = "PLAY_ITEM"
    PLAY_SUPPORTER = "PLAY_SUPPORTER"
    RETREAT = "RETREAT"
    ATTACK = "ATTACK"
    END_TURN = "END_TURN"


@dataclass
class Action:
    """Action structure taken by an agent."""
    action_type: ActionType
    card_idx: int = -1       # Index in hand if applicable
    target_idx: int = -1     # -1 for active, 0..4 for bench
    attack_idx: int = -1     # Index of attack on active Pokemon
    extra_args: Dict[str, Any] = field(default_factory=dict)

    def __repr__(self) -> str:
        return (
            f"Action({self.action_type.name}, card_idx={self.card_idx}, "
            f"target={self.target_idx}, attack={self.attack_idx}, extra={self.extra_args})"
        )


def check_attack_energy_cost(attached: List[str], cost: List[str]) -> bool:
    """
    Check if attached energies satisfy the attack cost.
    Colorless energy requirement can be satisfied by any energy type.
    """
    if len(attached) < len(cost):
        return False

    available = list(attached)
    colorless_needed = 0

    for req in cost:
        if req == "COLORLESS":
            colorless_needed += 1
        else:
            if req in available:
                available.remove(req)
            else:
                return False

    return len(available) >= colorless_needed


def get_legal_actions(state: GameState) -> List[Action]:
    """Generate all valid actions for the current player in the current state."""
    actions: List[Action] = []
    player = state.current_player
    opp = state.opponent_player

    # 1. Attack Actions (Terminal action for turn)
    # First turn of player 1 (turn_count == 1) cannot attack by PTCG official rules
    can_attack = not (state.turn_count == 1 and state.current_player_idx == 0)
    if can_attack and player.active_pokemon is not None:
        for atk_idx, atk in enumerate(player.active_pokemon.card.attacks):
            if check_attack_energy_cost(player.active_pokemon.attached_energies, atk.energy_cost):
                actions.append(Action(action_type=ActionType.ATTACK, attack_idx=atk_idx))

    # 2. Play Basic Pokemon to Bench (Max 5 bench)
    if len(player.bench) < 5:
        for idx, card in enumerate(player.hand):
            if card.card_type == CardType.POKEMON and card.stage == PokemonStage.BASIC:
                actions.append(Action(action_type=ActionType.PLAY_BASIC, card_idx=idx))

    # 3. Evolution Actions (Normal Stage 1 & Stage 2)
    for idx, card in enumerate(player.hand):
        if card.card_type == CardType.POKEMON and card.stage in (PokemonStage.STAGE_1, PokemonStage.STAGE_2):
            # Check active Pokemon
            if (
                player.active_pokemon is not None
                and player.active_pokemon.turns_in_play > 0
                and not player.active_pokemon.evolved_this_turn
                and player.active_pokemon.card.name == card.evolves_from
            ):
                actions.append(Action(action_type=ActionType.EVOLVE, card_idx=idx, target_idx=-1))

            # Check bench Pokemon
            for b_idx, b_poke in enumerate(player.bench):
                if (
                    b_poke.turns_in_play > 0
                    and not b_poke.evolved_this_turn
                    and b_poke.card.name == card.evolves_from
                ):
                    actions.append(Action(action_type=ActionType.EVOLVE, card_idx=idx, target_idx=b_idx))

    # 4. Attach Energy (Once per turn)
    if not player.energy_attached_this_turn:
        energy_indices = [
            i for i, c in enumerate(player.hand) if c.card_type == CardType.ENERGY
        ]
        if energy_indices:
            e_idx = energy_indices[0]  # Avoid redundant choices of identical basic energy
            if player.active_pokemon is not None:
                actions.append(Action(action_type=ActionType.ATTACH_ENERGY, card_idx=e_idx, target_idx=-1))
            for b_idx in range(len(player.bench)):
                actions.append(Action(action_type=ActionType.ATTACH_ENERGY, card_idx=e_idx, target_idx=b_idx))

    # 5. Play Item Cards
    for idx, card in enumerate(player.hand):
        if card.card_type == CardType.TRAINER_ITEM:
            if card.effect == "SEARCH_BASIC_TO_BENCH":
                if len(player.bench) < 5 and any(c.card_type == CardType.POKEMON and c.stage == PokemonStage.BASIC for c in player.deck):
                    actions.append(Action(action_type=ActionType.PLAY_ITEM, card_idx=idx))
            elif card.effect == "SEARCH_ANY_POKEMON":
                if len(player.hand) >= 3 and any(c.card_type == CardType.POKEMON for c in player.deck):
                    actions.append(Action(action_type=ActionType.PLAY_ITEM, card_idx=idx))
            elif card.effect == "SWITCH_ACTIVE_WITH_BENCH":
                if len(player.bench) > 0:
                    for b_idx in range(len(player.bench)):
                        actions.append(Action(action_type=ActionType.PLAY_ITEM, card_idx=idx, target_idx=b_idx))
            elif card.effect == "EVOLVE_BASIC_TO_STAGE2":
                # Rare Candy: Stage 2 in hand to Basic in play
                stage2_cards = [
                    (i, c) for i, c in enumerate(player.hand)
                    if c.card_type == CardType.POKEMON and c.stage == PokemonStage.STAGE_2
                ]
                for s2_idx, s2_card in enumerate(player.hand):
                    if s2_card.card_type == CardType.POKEMON and s2_card.stage == PokemonStage.STAGE_2:
                        # Check target basic
                        if player.active_pokemon and player.active_pokemon.card.stage == PokemonStage.BASIC and player.active_pokemon.turns_in_play > 0:
                            actions.append(Action(action_type=ActionType.PLAY_ITEM, card_idx=idx, target_idx=-1, extra_args={"s2_idx": s2_idx}))
                        for b_idx, b_poke in enumerate(player.bench):
                            if b_poke.card.stage == PokemonStage.BASIC and b_poke.turns_in_play > 0:
                                actions.append(Action(action_type=ActionType.PLAY_ITEM, card_idx=idx, target_idx=b_idx, extra_args={"s2_idx": s2_idx}))

    # 6. Play Supporter Cards (Once per turn, first turn player 1 cannot play supporters)
    can_play_supporter = not (state.turn_count == 1 and state.current_player_idx == 0)
    if can_play_supporter and not player.supporter_played_this_turn:
        for idx, card in enumerate(player.hand):
            if card.card_type == CardType.TRAINER_SUPPORTER:
                if card.effect == "DISCARD_AND_DRAW_7":
                    actions.append(Action(action_type=ActionType.PLAY_SUPPORTER, card_idx=idx))
                elif card.effect == "HAND_TO_DECK_DRAW_PRIZES":
                    actions.append(Action(action_type=ActionType.PLAY_SUPPORTER, card_idx=idx))
                elif card.effect == "SWITCH_OPPONENT_ACTIVE":
                    if len(opp.bench) > 0:
                        for opp_b_idx in range(len(opp.bench)):
                            actions.append(Action(action_type=ActionType.PLAY_SUPPORTER, card_idx=idx, target_idx=opp_b_idx))

    # 7. Retreat Active Pokemon (Once per turn)
    if (
        not player.retreated_this_turn
        and player.active_pokemon is not None
        and player.active_pokemon.can_retreat()
        and len(player.bench) > 0
    ):
        for b_idx in range(len(player.bench)):
            actions.append(Action(action_type=ActionType.RETREAT, target_idx=b_idx))

    # 8. End Turn (Always legal)
    actions.append(Action(action_type=ActionType.END_TURN))

    return actions
