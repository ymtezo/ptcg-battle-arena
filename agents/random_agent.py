"""Random baseline agent for PTCG simulation."""

import random
from typing import List, Optional
from agents.base import BaseAgent
from engine.gamestate import GameState
from engine.rules import Action, ActionType


class RandomAgent(BaseAgent):
    """An agent that chooses actions randomly among legal options."""

    def __init__(self, name: str = "RandomAgent", seed: Optional[int] = None) -> None:
        super().__init__(name)
        self.rng = random.Random(seed)

    def choose_action(self, state: GameState, legal_actions: List[Action]) -> Action:
        """Pick a legal action, favoring non-END_TURN actions if available."""
        if not legal_actions:
            return Action(action_type=ActionType.END_TURN)

        non_end_actions = [a for a in legal_actions if a.action_type != ActionType.END_TURN]

        # If there are active actions, 85% of the time pick one; 15% pass
        if non_end_actions and self.rng.random() < 0.85:
            return self.rng.choice(non_end_actions)

        # Fallback to any legal action
        return self.rng.choice(legal_actions)
