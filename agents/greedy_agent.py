"""Greedy baseline agent focusing on immediate maximum damage and aggression."""

from typing import List
from agents.base import BaseAgent
from engine.gamestate import GameState
from engine.rules import Action, ActionType


class GreedyAgent(BaseAgent):
    """
    A greedy agent that always picks actions for immediate maximum output.
    Prioritizes:
    1. Attacks dealing highest immediate damage.
    2. Rare Candy / Evolution to maximize Pokemon power.
    3. Attaching energy to active Pokemon for attacking.
    4. Playing supporters and search items.
    5. Playing basic Pokemon to bench.
    """

    def __init__(self, name: str = "GreedyAgent") -> None:
        super().__init__(name)

    def choose_action(self, state: GameState, legal_actions: List[Action]) -> Action:
        """Select action greedily based on immediate utility."""
        if not legal_actions:
            return Action(action_type=ActionType.END_TURN)

        player = state.current_player

        # 1. ATTACK: If we can attack, choose attack with maximum damage
        attacks = [a for a in legal_actions if a.action_type == ActionType.ATTACK]
        if attacks and player.active_pokemon:
            best_atk_action = None
            max_dmg = -1
            for a in attacks:
                dmg = player.active_pokemon.card.attacks[a.attack_idx].damage
                if dmg > max_dmg:
                    max_dmg = dmg
                    best_atk_action = a
            if best_atk_action:
                return best_atk_action

        # 2. EVOLVE / RARE CANDY: Prioritize evolving
        evolutions = [
            a for a in legal_actions
            if a.action_type == ActionType.EVOLVE or (a.action_type == ActionType.PLAY_ITEM and "s2_idx" in a.extra_args)
        ]
        if evolutions:
            return evolutions[0]

        # 3. ATTACH ENERGY: Always attach to active first, otherwise bench[0]
        attaches = [a for a in legal_actions if a.action_type == ActionType.ATTACH_ENERGY]
        if attaches:
            active_attaches = [a for a in attaches if a.target_idx == -1]
            if active_attaches:
                return active_attaches[0]
            return attaches[0]

        # 4. SUPPORTER: Play draw supporters
        supporters = [a for a in legal_actions if a.action_type == ActionType.PLAY_SUPPORTER]
        if supporters:
            return supporters[0]

        # 5. ITEM: Play search / utility items
        items = [a for a in legal_actions if a.action_type == ActionType.PLAY_ITEM]
        if items:
            return items[0]

        # 6. PLAY BASIC: Expand bench
        basics = [a for a in legal_actions if a.action_type == ActionType.PLAY_BASIC]
        if basics:
            return basics[0]

        # Fallback to end turn
        return Action(action_type=ActionType.END_TURN)
