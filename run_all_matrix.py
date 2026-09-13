"""Run a comprehensive matchup matrix across all agents and decks."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from engine.loader import load_card_database, load_sample_decks
from agents.random_agent import RandomAgent
from agents.greedy_agent import GreedyAgent
from agents.minimax_defensive_agent import MinimaxDefensiveAgent
from arena import run_arena_series


def main() -> None:
    card_db = load_card_database(PROJECT_ROOT / "data" / "card_database.json")
    decks = load_sample_decks(PROJECT_ROOT / "data" / "sample_decks.json", card_db)

    grimmsnarl = decks["grimmsnarl_control"][1]
    miraidon = decks["miraidon_aggro"][1]

    matchups = [
        # (Label, Agent A, Deck A, Agent B, Deck B)
        (
            "1. Minimax (Grimmsnarl) vs Random (Grimmsnarl)",
            MinimaxDefensiveAgent, grimmsnarl,
            RandomAgent, grimmsnarl,
        ),
        (
            "2. Greedy (Miraidon) vs Random (Miraidon)",
            GreedyAgent, miraidon,
            RandomAgent, miraidon,
        ),
        (
            "3. Minimax (Miraidon) vs Random (Miraidon)",
            MinimaxDefensiveAgent, miraidon,
            RandomAgent, miraidon,
        ),
        (
            "4. Minimax (Grimmsnarl) vs Greedy (Miraidon)",
            MinimaxDefensiveAgent, grimmsnarl,
            GreedyAgent, miraidon,
        ),
        (
            "5. Minimax (Miraidon) vs Greedy (Grimmsnarl)",
            MinimaxDefensiveAgent, miraidon,
            GreedyAgent, grimmsnarl,
        ),
        (
            "6. Minimax (Grimmsnarl) vs Greedy (Grimmsnarl) [Grimmsnarl Mirror]",
            MinimaxDefensiveAgent, grimmsnarl,
            GreedyAgent, grimmsnarl,
        ),
        (
            "7. Minimax (Miraidon) vs Greedy (Miraidon) [Miraidon Mirror]",
            MinimaxDefensiveAgent, miraidon,
            GreedyAgent, miraidon,
        ),
    ]

    print("================================================================")
    print("        PTCG COMPREHENSIVE MATCHUP MATRIX (100 Matches Each)    ")
    print("================================================================\n")

    summary_table = []

    for label, agent_a, deck_a, agent_b, deck_b in matchups:
        print(f"\n>>> Running: {label}...")
        res = run_arena_series(
            agent_a_cls=agent_a,
            agent_b_cls=agent_b,
            deck_a=deck_a,
            deck_b=deck_b,
            total_matches=100,
        )
        summary_table.append((
            label,
            f"{res['win_rate_a']:.1f}%",
            f"{res['win_rate_b']:.1f}%",
            f"{res['avg_turns']:.1f}",
            f"{res['total_time_sec']:.2f}s",
        ))

    print("\n\n================================================================")
    print("                     FINAL MATRIX SUMMARY                       ")
    print("================================================================")
    print(f"{'Matchup':<60} | {'Agent A Win':<11} | {'Agent B Win':<11} | {'Avg Turns':<10} | {'Time'}")
    print("-" * 105)
    for label, a_win, b_win, turns, t_sec in summary_table:
        print(f"{label:<60} | {a_win:<11} | {b_win:<11} | {turns:<10} | {t_sec}")
    print("================================================================\n")


if __name__ == "__main__":
    main()
