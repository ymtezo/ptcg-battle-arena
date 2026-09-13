"""PTCG Battle Arena: Tournament and match runner with fair turn balancing."""

import time
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Any, Type, Optional
from concurrent.futures import ProcessPoolExecutor, as_completed

from engine.card import Card
from engine.gamestate import GameState
from engine.rules import get_legal_actions, ActionType
from engine.simulator import setup_game, apply_action
from engine.loader import load_card_database, load_sample_decks
from agents.base import BaseAgent
from agents.random_agent import RandomAgent
from agents.greedy_agent import GreedyAgent
from agents.minimax_defensive_agent import MinimaxDefensiveAgent


@dataclass
class MatchResult:
    """Detailed summary of a single simulated match."""
    match_id: int
    winner_idx: int         # 0 or 1
    winner_name: str
    total_turns: int
    reason: str
    p1_name: str
    p2_name: str
    p1_prizes_remaining: int
    p2_prizes_remaining: int
    elapsed_ms: float
    log_sample: List[str] = field(default_factory=list)


def play_single_match(
    match_id: int,
    agent0_cls: Type[BaseAgent],
    agent1_cls: Type[BaseAgent],
    deck0: List[Card],
    deck1: List[Card],
    seed: int,
    max_turns: int = 60,
) -> MatchResult:
    """Simulate a single match between two agents to completion."""
    start_time = time.perf_counter()
    rng = random.Random(seed)

    agent0 = agent0_cls()
    agent1 = agent1_cls()
    agents = [agent0, agent1]

    state = setup_game(deck0, deck1, p1_name=agent0.name, p2_name=agent1.name, seed=seed)

    max_actions_per_turn = 25  # Guard against infinite action loops

    while not state.is_game_over and state.turn_count <= max_turns:
        current_agent = agents[state.current_player_idx]
        current_turn = state.turn_count
        action_count = 0

        while (
            not state.is_game_over
            and state.turn_count == current_turn
            and action_count < max_actions_per_turn
        ):
            legal_actions = get_legal_actions(state)
            if not legal_actions:
                break

            chosen_action = current_agent.choose_action(state, legal_actions)
            state = apply_action(state, chosen_action, rng=rng)
            action_count += 1

            # If agent ended turn or attacked, break inner loop
            if chosen_action.action_type in (ActionType.ATTACK, ActionType.END_TURN):
                break

        # If agent looped without ending turn, force end turn
        if state.turn_count == current_turn and not state.is_game_over:
            from engine.rules import Action
            state = apply_action(state, Action(action_type=ActionType.END_TURN), rng=rng)

    elapsed_ms = (time.perf_counter() - start_time) * 1000.0

    # Adjudication if max turns exceeded
    if not state.is_game_over:
        # Tie-breaker: whoever has fewer prize cards remaining wins
        p1_prizes = len(state.players[0].prizes)
        p2_prizes = len(state.players[1].prizes)
        if p1_prizes < p2_prizes:
            winner = 0
            reason = f"Max turns ({max_turns}) reached: P0 had fewer prizes ({p1_prizes} vs {p2_prizes})"
        elif p2_prizes < p1_prizes:
            winner = 1
            reason = f"Max turns ({max_turns}) reached: P1 had fewer prizes ({p2_prizes} vs {p1_prizes})"
        else:
            winner = 0  # Default to player 0
            reason = f"Max turns ({max_turns}) reached: Draw adjudicated"
    else:
        winner = state.winner if state.winner is not None else 0
        reason = state.game_over_reason or "Unknown"

    winner_name = agents[winner].name

    return MatchResult(
        match_id=match_id,
        winner_idx=winner,
        winner_name=winner_name,
        total_turns=state.turn_count,
        reason=reason,
        p1_name=agents[0].name,
        p2_name=agents[1].name,
        p1_prizes_remaining=len(state.players[0].prizes),
        p2_prizes_remaining=len(state.players[1].prizes),
        elapsed_ms=elapsed_ms,
        log_sample=state.log[-5:] if state.log else [],
    )


def run_arena_series(
    agent_a_cls: Type[BaseAgent],
    agent_b_cls: Type[BaseAgent],
    deck_a: List[Card],
    deck_b: List[Card],
    total_matches: int = 100,
) -> Dict[str, Any]:
    """
    Run a balanced series of matches with 50% first-turn parity.
    Half of the games: Agent A is Player 0 (Goes first).
    Half of the games: Agent B is Player 0 (Goes first).
    """
    half = total_matches // 2
    results: List[MatchResult] = []

    print(f"==================================================")
    print(f" PTCG BATTLE ARENA: {agent_a_cls.__name__} vs {agent_b_cls.__name__}")
    print(f" Total Matches: {total_matches} (50 as First, 50 as Second)")
    print(f"==================================================")

    start_series = time.perf_counter()

    # Part 1: Agent A is P0, Agent B is P1
    for i in range(half):
        res = play_single_match(
            match_id=i + 1,
            agent0_cls=agent_a_cls,
            agent1_cls=agent_b_cls,
            deck0=deck_a,
            deck1=deck_b,
            seed=1000 + i,
        )
        results.append(res)

    # Part 2: Agent B is P0, Agent A is P1 (Swapped seats for fairness)
    for i in range(half, total_matches):
        res = play_single_match(
            match_id=i + 1,
            agent0_cls=agent_b_cls,
            agent1_cls=agent_a_cls,
            deck0=deck_b,
            deck1=deck_a,
            seed=2000 + i,
        )
        results.append(res)

    total_time = time.perf_counter() - start_series

    # Aggregate Statistics
    a_name = agent_a_cls().name
    b_name = agent_b_cls().name

    a_wins = 0
    b_wins = 0
    a_wins_as_first = 0
    a_wins_as_second = 0
    total_turns = 0
    win_reasons: Dict[str, int] = {}

    for res in results:
        total_turns += res.total_turns
        key = res.reason.split(":")[0]
        win_reasons[key] = win_reasons.get(key, 0) + 1

        if res.winner_name == a_name:
            a_wins += 1
            if res.match_id <= half:
                a_wins_as_first += 1
            else:
                a_wins_as_second += 1
        else:
            b_wins += 1

    win_rate_a = (a_wins / total_matches) * 100.0
    win_rate_b = (b_wins / total_matches) * 100.0
    avg_turns = total_turns / total_matches
    ms_per_game = (total_time / total_matches) * 1000.0

    print("\n---------------- MATCH RESULTS SUMMARY ----------------")
    print(f"{a_name} Wins: {a_wins} / {total_matches} ({win_rate_a:.1f}%)")
    print(f"  - As First Turn (P0): {a_wins_as_first} / {half} ({(a_wins_as_first / half) * 100.0:.1f}%)")
    print(f"  - As Second Turn (P1): {a_wins_as_second} / {half} ({(a_wins_as_second / half) * 100.0:.1f}%)")
    print(f"{b_name} Wins: {b_wins} / {total_matches} ({win_rate_b:.1f}%)")
    print(f"Average Turns per Game: {avg_turns:.1f}")
    print(f"Total Simulation Time: {total_time:.2f}s ({ms_per_game:.1f} ms/game)")
    print(f"Win Reason Breakdown:")
    for reason, count in win_reasons.items():
        print(f"  - {reason}: {count} games")
    print("------------------------------------------------------\n")

    return {
        "agent_a": a_name,
        "agent_b": b_name,
        "total_matches": total_matches,
        "a_wins": a_wins,
        "b_wins": b_wins,
        "win_rate_a": win_rate_a,
        "win_rate_b": win_rate_b,
        "avg_turns": avg_turns,
        "total_time_sec": total_time,
        "ms_per_game": ms_per_game,
        "win_reasons": win_reasons,
    }


if __name__ == "__main__":
    base_dir = Path(__file__).parent
    card_db = load_card_database(base_dir / "data" / "card_database.json")
    decks = load_sample_decks(base_dir / "data" / "sample_decks.json", card_db)

    grimmsnarl_deck = decks["grimmsnarl_control"][1]
    miraidon_deck = decks["miraidon_aggro"][1]

    # Run Tournament: MinimaxDefensiveAgent vs GreedyAgent (100 matches)
    summary = run_arena_series(
        agent_a_cls=MinimaxDefensiveAgent,
        agent_b_cls=GreedyAgent,
        deck_a=grimmsnarl_deck,
        deck_b=miraidon_deck,
        total_matches=100,
    )
