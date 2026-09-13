"""Empirical verification of Iono (ナンジャモ) appearance and play rates."""

import sys
from pathlib import Path
import random

PROJECT_ROOT = Path(__file__).parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from engine.loader import load_card_database, load_sample_decks
from engine.simulator import setup_game, apply_action
from engine.rules import get_legal_actions, ActionType, Action
from agents.minimax_defensive_agent import MinimaxDefensiveAgent
from agents.greedy_agent import GreedyAgent


def audit_iono_frequency(num_matches: int = 200) -> None:
    card_db = load_card_database(PROJECT_ROOT / "data" / "card_database.json")
    decks = load_sample_decks(PROJECT_ROOT / "data" / "sample_decks.json", card_db)

    deck_grim = decks["grimmsnarl_control"][1]
    deck_mir = decks["miraidon_aggro"][1]

    # Metrics for Player 0 (MinimaxDefensiveAgent with Grimmsnarl deck)
    games_with_iono_in_starting_hand = 0
    games_where_iono_entered_hand = 0
    games_where_iono_was_played = 0
    total_iono_plays = 0
    all_4_in_prizes_count = 0

    for i in range(num_matches):
        seed = 5000 + i
        rng = random.Random(seed)

        agent0 = MinimaxDefensiveAgent()
        agent1 = GreedyAgent()
        agents = [agent0, agent1]

        state = setup_game(deck_grim, deck_mir, p1_name=agent0.name, p2_name=agent1.name, seed=seed)
        p0 = state.players[0]

        # 1. Check opening hand
        p0_hand_card_ids = [c.id for c in p0.hand]
        if "trainer-iono" in p0_hand_card_ids:
            games_with_iono_in_starting_hand += 1

        # 2. Check prizes
        p0_prize_card_ids = [c.id for c in p0.prizes]
        if p0_prize_card_ids.count("trainer-iono") == 4:
            all_4_in_prizes_count += 1

        saw_iono = "trainer-iono" in p0_hand_card_ids
        played_iono_this_game = False

        max_turns = 60
        max_actions = 25

        while not state.is_game_over and state.turn_count <= max_turns:
            cur_turn = state.turn_count
            act_count = 0

            # Check if P0 ever gets Iono into hand during the match
            if state.current_player_idx == 0:
                if any(c.id == "trainer-iono" for c in state.players[0].hand):
                    saw_iono = True

            while not state.is_game_over and state.turn_count == cur_turn and act_count < max_actions:
                legal = get_legal_actions(state)
                if not legal:
                    break
                action = agents[state.current_player_idx].choose_action(state, legal)

                # Check if P0 played Iono
                if state.current_player_idx == 0 and action.action_type == ActionType.PLAY_SUPPORTER:
                    if action.card_idx < len(state.players[0].hand):
                        c = state.players[0].hand[action.card_idx]
                        if c.id == "trainer-iono":
                            played_iono_this_game = True
                            total_iono_plays += 1

                state = apply_action(state, action, rng=rng)
                act_count += 1
                if action.action_type in (ActionType.ATTACK, ActionType.END_TURN):
                    break

            if state.turn_count == cur_turn and not state.is_game_over:
                state = apply_action(state, Action(action_type=ActionType.END_TURN), rng=rng)

        if saw_iono:
            games_where_iono_entered_hand += 1
        if played_iono_this_game:
            games_where_iono_was_played += 1

    print(f"=== EMPIRICAL AUDIT REPORT (Total {num_matches} Matches) ===")
    print(f"Games with Iono in Opening Hand (7 cards): {games_with_iono_in_starting_hand} ({games_with_iono_in_starting_hand / num_matches * 100:.1f}%)")
    print(f"Games where Iono entered hand (Drawn into hand): {games_where_iono_entered_hand} ({games_where_iono_entered_hand / num_matches * 100:.1f}%)")
    print(f"Games where Iono was actually PLAYED by Minimax: {games_where_iono_was_played} ({games_where_iono_was_played / num_matches * 100:.1f}%)")
    print(f"Games where Iono entered hand but was NOT played: {games_where_iono_entered_hand - games_where_iono_was_played} ({(games_where_iono_entered_hand - games_where_iono_was_played) / num_matches * 100:.1f}%)")
    print(f"Games where Iono was NEVER drawn: {num_matches - games_where_iono_entered_hand} ({(num_matches - games_where_iono_entered_hand) / num_matches * 100:.1f}%)")
    print(f"Total Iono Casts across all games: {total_iono_plays} times (avg {total_iono_plays / num_matches:.2f}/game)")
    print(f"Games where all 4 Ionos were locked in prizes: {all_4_in_prizes_count} ({all_4_in_prizes_count / num_matches * 100:.2f}%)")


if __name__ == "__main__":
    audit_iono_frequency(200)
