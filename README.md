# Pokemon TCG Battle Arena & Game-Theoretic Simulation

High-performance, lightweight local Pokemon Trading Card Game (PTCG) battle simulation engine and game-theoretic AI agents designed for the Kaggle **The Pokémon Company - PTCG AI Battle Challenge Strategy** competition.

## Key Features

1. **Deterministic Fast Engine**: Pure Python, zero-external-dependency rule engine enforcing official PTCG mechanics:
   - Setup, mulligan, and 6-prize distribution.
   - First-turn player restrictions (no attacks or supporters on Turn 1 P0).
   - Energy attachment per turn, energy cost matching (colored + colorless).
   - Evolutions (Stage 1, Stage 2, and Rare Candy item evolution).
   - Knockout resolution, 2-prize ex/V mechanics, bench-out win condition, and deck-out detection.
2. **Game-Theoretic Defensive Agent (`MinimaxDefensiveAgent`)**:
   - **Worst-Case Threat Modeling**: Predicts opponent's maximum incoming strike next turn.
   - **Energy Preservation**: Avoids wasting energy on doomed active Pokemon; channels resources to bench counters.
   - **Emergency Retreat / Switching**: Protects vulnerable Pokemon to deny easy prize card trades.
   - **Targeted Disruption**: Uses Boss's Orders to pull and eliminate emerging opponent threats before they strike.
3. **Turn-Fair Battle Arena (`arena.py`)**:
   - Matches agents in series with 50% first-turn parity (50 as Player 0, 50 as Player 1).
   - Detailed statistics: Win rates, average turn count, game-over breakdown, and execution latency.

## Directory Structure

```
D:\ptcg-battle-arena/
├── data/
│   ├── card_database.json        # Card definitions (Pokemon, items, supporters, energy)
│   └── sample_decks.json         # 60-card tournament deck recipes
├── engine/
│   ├── card.py                   # Card, Attack, and enum models
│   ├── gamestate.py              # GameState, PlayerState, and PokemonInstance
│   ├── rules.py                  # Legal action generator and validation
│   ├── simulator.py              # Turn transitions, attacks, knockouts
│   └── loader.py                 # JSON database & deck loaders
├── agents/
│   ├── base.py                   # BaseAgent abstract class
│   ├── random_agent.py           # Random exploration baseline
│   ├── greedy_agent.py           # Immediate maximum-damage baseline
│   └── minimax_defensive_agent.py# Regret-minimizing game-theoretic agent
├── arena.py                      # Multi-match tournament runner
├── verify_arena.py               # Unit tests & verification suite
└── README.md                     # Documentation
```

## Quick Start

### 1. Run Unit Tests and 100-Match Verification
```bash
python verify_arena.py
```

### 2. Run Custom Tournament
```bash
python arena.py
```
