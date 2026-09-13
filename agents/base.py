"""Base class definition for PTCG Battle Agents."""

from abc import ABC, abstractmethod
from typing import List
from engine.gamestate import GameState
from engine.rules import Action


class BaseAgent(ABC):
    """Abstract base class that all agents must inherit from."""

    def __init__(self, name: str) -> None:
        self.name = name

    @abstractmethod
    def choose_action(self, state: GameState, legal_actions: List[Action]) -> Action:
        """
        Evaluate the game state and legal actions, and choose the next action.

        Args:
            state: Current GameState snapshot (read-only recommended).
            legal_actions: List of valid actions that can be legally played.

        Returns:
            Chosen Action instance.
        """
        pass
