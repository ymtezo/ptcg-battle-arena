"""Automated unit tests and verification suite for PTCG Battle Arena."""

import sys
import unittest
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from engine.card import Card, CardType, PokemonStage, Attack
from engine.gamestate import GameState, PlayerState, PokemonInstance
from engine.rules import (
    Action,
    ActionType,
    check_attack_energy_cost,
    get_legal_actions,
)
from engine.simulator import setup_game, apply_action
from engine.loader import load_card_database, load_sample_decks
from agents.random_agent import RandomAgent
from agents.greedy_agent import GreedyAgent
from agents.minimax_defensive_agent import MinimaxDefensiveAgent
from arena import play_single_match, run_arena_series


class TestPTCGEngine(unittest.TestCase):
    """Unit tests for the core game engine logic."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.card_db = load_card_database(PROJECT_ROOT / "data" / "card_database.json")
        cls.decks = load_sample_decks(PROJECT_ROOT / "data" / "sample_decks.json", cls.card_db)

    def test_01_deck_integrity(self) -> None:
        """Verify that all decks have exactly 60 cards and valid IDs."""
        self.assertIn("grimmsnarl_control", self.decks)
        self.assertIn("miraidon_aggro", self.decks)

        for deck_key, (name, cards) in self.decks.items():
            self.assertEqual(
                len(cards), 60, f"Deck {deck_key} ({name}) must have exactly 60 cards, found {len(cards)}"
            )

    def test_02_game_setup(self) -> None:
        """Verify starting game state configuration."""
        deck_a = self.decks["grimmsnarl_control"][1]
        deck_b = self.decks["miraidon_aggro"][1]
        state = setup_game(deck_a, deck_b, seed=42)

        self.assertEqual(len(state.players[0].prizes), 6)
        self.assertEqual(len(state.players[1].prizes), 6)
        self.assertIsNotNone(state.players[0].active_pokemon)
        self.assertIsNotNone(state.players[1].active_pokemon)
        self.assertEqual(state.players[0].active_pokemon.card.stage, PokemonStage.BASIC)
        self.assertEqual(state.players[1].active_pokemon.card.stage, PokemonStage.BASIC)
        self.assertEqual(state.current_player_idx, 0)
        self.assertEqual(state.turn_count, 1)

    def test_03_first_turn_restrictions(self) -> None:
        """Verify official PTCG rule: Player going first (Turn 1) cannot attack or play supporters."""
        deck_a = self.decks["grimmsnarl_control"][1]
        deck_b = self.decks["miraidon_aggro"][1]
        state = setup_game(deck_a, deck_b, seed=123)

        legal_actions = get_legal_actions(state)
        attack_actions = [a for a in legal_actions if a.action_type == ActionType.ATTACK]
        self.assertEqual(len(attack_actions), 0, "Player 1 Turn 1 cannot attack!")

        supporter_actions = [a for a in legal_actions if a.action_type == ActionType.PLAY_SUPPORTER]
        self.assertEqual(len(supporter_actions), 0, "Player 1 Turn 1 cannot play supporters!")

    def test_04_energy_cost_checking(self) -> None:
        """Verify energy fulfillment logic including Colorless requirements."""
        cost = ["DARK", "COLORLESS", "COLORLESS"]
        self.assertFalse(check_attack_energy_cost([], cost))
        self.assertFalse(check_attack_energy_cost(["DARK"], cost))
        self.assertFalse(check_attack_energy_cost(["LIGHTNING", "LIGHTNING", "LIGHTNING"], cost))
        self.assertFalse(check_attack_energy_cost(["DARK", "COLORLESS"], cost))

        self.assertTrue(check_attack_energy_cost(["DARK", "DARK", "DARK"], cost))
        self.assertTrue(check_attack_energy_cost(["DARK", "LIGHTNING", "COLORLESS"], cost))
        self.assertTrue(check_attack_energy_cost(["DARK", "LIGHTNING", "LIGHTNING", "LIGHTNING"], cost))

    def test_05_single_match_completion(self) -> None:
        """Verify a single match can run to completion without errors."""
        deck_a = self.decks["grimmsnarl_control"][1]
        deck_b = self.decks["miraidon_aggro"][1]
        res = play_single_match(
            match_id=1,
            agent0_cls=MinimaxDefensiveAgent,
            agent1_cls=GreedyAgent,
            deck0=deck_a,
            deck1=deck_b,
            seed=999,
        )
        self.assertIn(res.winner_idx, [0, 1])
        self.assertGreater(res.total_turns, 0)
        self.assertTrue(len(res.reason) > 0)


def run_tournament_verification() -> None:
    """Run cross-deck and mirror tournaments to prove strategic superiority."""
    card_db = load_card_database(PROJECT_ROOT / "data" / "card_database.json")
    decks = load_sample_decks(PROJECT_ROOT / "data" / "sample_decks.json", card_db)

    grimmsnarl = decks["grimmsnarl_control"][1]
    miraidon = decks["miraidon_aggro"][1]

    # Series 1: Grimmsnarl Control vs Miraidon Aggro
    print("\n>>> SERIES 1: Grimmsnarl Control vs Miraidon Aggro (100 Matches)")
    summary1 = run_arena_series(
        agent_a_cls=MinimaxDefensiveAgent,
        agent_b_cls=GreedyAgent,
        deck_a=grimmsnarl,
        deck_b=miraidon,
        total_matches=100,
    )

    # Series 2: Mirror Match (Both pilot Miraidon Turbo Aggro) to isolate pure agent intelligence
    print("\n>>> SERIES 2: Mirror Match - Miraidon Aggro vs Miraidon Aggro (100 Matches)")
    summary2 = run_arena_series(
        agent_a_cls=MinimaxDefensiveAgent,
        agent_b_cls=GreedyAgent,
        deck_a=miraidon,
        deck_b=miraidon,
        total_matches=100,
    )

    print("\n================ FINAL VERIFICATION REPORT ================")
    print(f"Series 1 (Grimmsnarl vs Miraidon): Minimax Win Rate = {summary1['win_rate_a']:.1f}%")
    print(f"Series 2 (Miraidon Mirror Match):   Minimax Win Rate = {summary2['win_rate_a']:.1f}%")
    print("===========================================================")


if __name__ == "__main__":
    print("Running Unit Tests...")
    suite = unittest.TestLoader().loadTestsFromTestCase(TestPTCGEngine)
    runner = unittest.TextTestRunner(verbosity=2)
    test_result = runner.run(suite)

    if test_result.wasSuccessful():
        print("\nAll unit tests passed! Starting tournament verification...\n")
        run_tournament_verification()
    else:
        sys.exit(1)
