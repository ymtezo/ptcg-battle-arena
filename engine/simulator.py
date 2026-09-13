"""PTCG Battle Simulator: Game setup, action execution, and state transitions."""

import random
from typing import List, Optional, Tuple, Dict, Any
from engine.card import Card, CardType, PokemonStage, Attack
from engine.gamestate import GameState, PlayerState, PokemonInstance
from engine.rules import Action, ActionType, check_attack_energy_cost


def setup_game(
    deck1_cards: List[Card],
    deck2_cards: List[Card],
    p1_name: str = "Player 1",
    p2_name: str = "Player 2",
    seed: Optional[int] = None,
) -> GameState:
    """Initialize a full PTCG match with shuffling, mulligan handling, and prize setup."""
    rng = random.Random(seed)

    def draw_starting_hand(deck_pool: List[Card]) -> Tuple[List[Card], List[Card], Card]:
        """Draw 7 cards ensuring at least 1 basic Pokemon exists."""
        deck = [c for c in deck_pool]
        while True:
            rng.shuffle(deck)
            hand = [deck.pop() for _ in range(7)]
            basic_candidates = [
                c for c in hand if c.card_type == CardType.POKEMON and c.stage == PokemonStage.BASIC
            ]
            if basic_candidates:
                active_card = basic_candidates[0]
                hand.remove(active_card)
                return deck, hand, active_card
            # Mulligan: return hand to deck and retry
            deck.extend(hand)

    # Setup Player 1
    d1, h1, active1_card = draw_starting_hand(deck1_cards)
    p1_active = PokemonInstance(card=active1_card, current_hp=active1_card.hp, turns_in_play=1)
    # Extra basics from hand to bench
    p1_bench: List[PokemonInstance] = []
    for c in list(h1):
        if c.card_type == CardType.POKEMON and c.stage == PokemonStage.BASIC and len(p1_bench) < 3:
            h1.remove(c)
            p1_bench.append(PokemonInstance(card=c, current_hp=c.hp, turns_in_play=1))

    # Setup 6 prize cards for Player 1
    p1_prizes = [d1.pop() for _ in range(6)]
    player1 = PlayerState(
        player_id=0,
        name=p1_name,
        deck=d1,
        hand=h1,
        prizes=p1_prizes,
        active_pokemon=p1_active,
        bench=p1_bench,
    )

    # Setup Player 2
    d2, h2, active2_card = draw_starting_hand(deck2_cards)
    p2_active = PokemonInstance(card=active2_card, current_hp=active2_card.hp, turns_in_play=1)
    p2_bench: List[PokemonInstance] = []
    for c in list(h2):
        if c.card_type == CardType.POKEMON and c.stage == PokemonStage.BASIC and len(p2_bench) < 3:
            h2.remove(c)
            p2_bench.append(PokemonInstance(card=c, current_hp=c.hp, turns_in_play=1))

    # Setup 6 prize cards for Player 2
    p2_prizes = [d2.pop() for _ in range(6)]
    player2 = PlayerState(
        player_id=1,
        name=p2_name,
        deck=d2,
        hand=h2,
        prizes=p2_prizes,
        active_pokemon=p2_active,
        bench=p2_bench,
    )

    # Player 1 turn 1 draw
    if player1.deck:
        player1.hand.append(player1.deck.pop())

    return GameState(
        turn_count=1,
        current_player_idx=0,
        players=[player1, player2],
        winner=None,
        game_over_reason=None,
        log=[f"Game started between {p1_name} and {p2_name}"],
    )


def apply_action(state: GameState, action: Action, rng: Optional[random.Random] = None) -> GameState:
    """Apply an action to the state and transition to the next state."""
    if state.is_game_over:
        return state

    if rng is None:
        rng = random.Random()

    player = state.current_player
    opp = state.opponent_player

    if action.action_type == ActionType.PLAY_BASIC:
        if 0 <= action.card_idx < len(player.hand):
            card = player.hand.pop(action.card_idx)
            player.bench.append(PokemonInstance(card=card, current_hp=card.hp, turns_in_play=0))
            state.log.append(f"P{player.player_id} played {card.name} to bench")

    elif action.action_type == ActionType.EVOLVE:
        if 0 <= action.card_idx < len(player.hand):
            evo_card = player.hand.pop(action.card_idx)
            target = player.active_pokemon if action.target_idx == -1 else player.bench[action.target_idx]
            damage = target.card.hp - target.current_hp
            target.card = evo_card
            target.current_hp = max(1, evo_card.hp - damage)
            target.evolved_this_turn = True
            state.log.append(f"P{player.player_id} evolved to {evo_card.name}")

    elif action.action_type == ActionType.ATTACH_ENERGY:
        if 0 <= action.card_idx < len(player.hand) and not player.energy_attached_this_turn:
            energy_card = player.hand.pop(action.card_idx)
            target = player.active_pokemon if action.target_idx == -1 else player.bench[action.target_idx]
            target.attach_energy(energy_card.energy_type or "COLORLESS")
            player.energy_attached_this_turn = True
            state.log.append(f"P{player.player_id} attached {energy_card.name} to {target.card.name}")

    elif action.action_type == ActionType.PLAY_ITEM:
        if 0 <= action.card_idx < len(player.hand):
            card = player.hand.pop(action.card_idx)
            player.discard_pile.append(card)

            if card.effect == "SEARCH_BASIC_TO_BENCH":
                basic_in_deck = [
                    (i, c) for i, c in enumerate(player.deck)
                    if c.card_type == CardType.POKEMON and c.stage == PokemonStage.BASIC
                ]
                if basic_in_deck and len(player.bench) < 5:
                    deck_idx, chosen_basic = basic_in_deck[0]
                    player.deck.pop(deck_idx)
                    player.bench.append(PokemonInstance(card=chosen_basic, current_hp=chosen_basic.hp, turns_in_play=0))
                    state.log.append(f"P{player.player_id} searched {chosen_basic.name} to bench via {card.name}")

            elif card.effect == "SEARCH_ANY_POKEMON":
                # Discard 2 cards from hand
                discards = [c for c in player.hand if c.card_type != CardType.POKEMON][:2]
                if len(discards) < 2:
                    discards = player.hand[:2]
                for d in discards:
                    if d in player.hand:
                        player.hand.remove(d)
                        player.discard_pile.append(d)
                poke_in_deck = [
                    (i, c) for i, c in enumerate(player.deck) if c.card_type == CardType.POKEMON
                ]
                if poke_in_deck:
                    deck_idx, chosen_poke = poke_in_deck[0]
                    player.deck.pop(deck_idx)
                    player.hand.append(chosen_poke)
                    state.log.append(f"P{player.player_id} searched {chosen_poke.name} to hand via {card.name}")

            elif card.effect == "SWITCH_ACTIVE_WITH_BENCH":
                if 0 <= action.target_idx < len(player.bench):
                    old_active = player.active_pokemon
                    player.active_pokemon = player.bench.pop(action.target_idx)
                    if old_active:
                        player.bench.append(old_active)
                    state.log.append(f"P{player.player_id} switched active with bench via {card.name}")

            elif card.effect == "EVOLVE_BASIC_TO_STAGE2":
                s2_idx = action.extra_args.get("s2_idx", -1)
                if 0 <= s2_idx < len(player.hand):
                    s2_card = player.hand.pop(s2_idx)
                    target = player.active_pokemon if action.target_idx == -1 else player.bench[action.target_idx]
                    damage = target.card.hp - target.current_hp
                    target.card = s2_card
                    target.current_hp = max(1, s2_card.hp - damage)
                    target.evolved_this_turn = True
                    state.log.append(f"P{player.player_id} rare-candied into {s2_card.name}")

    elif action.action_type == ActionType.PLAY_SUPPORTER:
        if 0 <= action.card_idx < len(player.hand) and not player.supporter_played_this_turn:
            card = player.hand.pop(action.card_idx)
            player.discard_pile.append(card)
            player.supporter_played_this_turn = True

            if card.effect == "DISCARD_AND_DRAW_7":
                player.discard_pile.extend(player.hand)
                player.hand.clear()
                draw_count = min(7, len(player.deck))
                for _ in range(draw_count):
                    player.hand.append(player.deck.pop())
                state.log.append(f"P{player.player_id} discarded hand and drew {draw_count} cards via {card.name}")

            elif card.effect == "HAND_TO_DECK_DRAW_PRIZES":
                player.deck.extend(player.hand)
                rng.shuffle(player.deck)
                player.hand.clear()
                draw_p = min(len(player.prizes), len(player.deck))
                for _ in range(draw_p):
                    player.hand.append(player.deck.pop())

                opp.deck.extend(opp.hand)
                rng.shuffle(opp.deck)
                opp.hand.clear()
                draw_o = min(len(opp.prizes), len(opp.deck))
                for _ in range(draw_o):
                    opp.hand.append(opp.deck.pop())
                state.log.append(f"P{player.player_id} played Iono: P{player.player_id} drew {draw_p}, P{opp.player_id} drew {draw_o}")

            elif card.effect == "SWITCH_OPPONENT_ACTIVE":
                if 0 <= action.target_idx < len(opp.bench):
                    old_active = opp.active_pokemon
                    opp.active_pokemon = opp.bench.pop(action.target_idx)
                    if old_active:
                        opp.bench.append(old_active)
                    state.log.append(f"P{player.player_id} gusted opponent {opp.active_pokemon.card.name} via {card.name}")

    elif action.action_type == ActionType.RETREAT:
        if (
            not player.retreated_this_turn
            and player.active_pokemon is not None
            and 0 <= action.target_idx < len(player.bench)
        ):
            player.active_pokemon.pay_retreat_cost()
            old_active = player.active_pokemon
            player.active_pokemon = player.bench.pop(action.target_idx)
            player.bench.append(old_active)
            player.retreated_this_turn = True
            state.log.append(f"P{player.player_id} retreated to {player.active_pokemon.card.name}")

    elif action.action_type == ActionType.ATTACK:
        if player.active_pokemon and 0 <= action.attack_idx < len(player.active_pokemon.card.attacks):
            attack = player.active_pokemon.card.attacks[action.attack_idx]
            raw_dmg = attack.damage

            # Weakness calculation (x2)
            if opp.active_pokemon and opp.active_pokemon.card.weakness == player.active_pokemon.card.pokemon_type:
                raw_dmg *= 2

            if opp.active_pokemon:
                opp.active_pokemon.take_damage(raw_dmg)
                state.log.append(
                    f"P{player.player_id} used {attack.name} for {raw_dmg} dmg on {opp.active_pokemon.card.name}"
                )

            # Bench damage
            if attack.bench_damage > 0 and opp.bench:
                for b in opp.bench:
                    b.take_damage(attack.bench_damage)
                state.log.append(
                    f"{attack.name} dealt {attack.bench_damage} spread dmg to opponent bench"
                )

            # Check Knockouts
            _resolve_knockouts(state)

            # Attack ends turn automatically
            _end_current_turn(state)
            return state

    elif action.action_type == ActionType.END_TURN:
        _end_current_turn(state)

    return state


def _resolve_knockouts(state: GameState) -> None:
    """Check both players' Pokemon for knockouts and award prize cards."""
    for p_idx in [0, 1]:
        player = state.players[p_idx]
        opp = state.players[1 - p_idx]

        # Check Active
        if player.active_pokemon and player.active_pokemon.is_knocked_out:
            ko_card = player.active_pokemon.card
            prizes_to_take = min(ko_card.prize_value, len(opp.prizes))
            for _ in range(prizes_to_take):
                opp.hand.append(opp.prizes.pop())
            player.discard_pile.append(ko_card)
            state.log.append(
                f"P{player.player_id}'s {ko_card.name} was KNOCKED OUT! P{opp.player_id} took {prizes_to_take} prize(s)."
            )

            # Promote next active from bench if available
            if player.bench:
                player.active_pokemon = player.bench.pop(0)
                state.log.append(f"P{player.player_id} promoted {player.active_pokemon.card.name} to active")
            else:
                player.active_pokemon = None

        # Check Bench
        surviving_bench: List[PokemonInstance] = []
        for b in player.bench:
            if b.is_knocked_out:
                prizes_to_take = min(b.card.prize_value, len(opp.prizes))
                for _ in range(prizes_to_take):
                    opp.hand.append(opp.prizes.pop())
                player.discard_pile.append(b.card)
                state.log.append(
                    f"P{player.player_id}'s bench {b.card.name} was KNOCKED OUT! P{opp.player_id} took {prizes_to_take} prize(s)."
                )
            else:
                surviving_bench.append(b)
        player.bench = surviving_bench

    # Win Condition Check: Prize depletion
    if len(state.players[0].prizes) == 0:
        state.winner = 0
        state.game_over_reason = "All 6 prizes taken by Player 1"
        return
    if len(state.players[1].prizes) == 0:
        state.winner = 1
        state.game_over_reason = "All 6 prizes taken by Player 2"
        return

    # Win Condition Check: No Pokemon left in play
    if state.players[0].total_pokemon_count == 0:
        state.winner = 1
        state.game_over_reason = "Player 1 has no Pokemon left in play (Bench out)"
        return
    if state.players[1].total_pokemon_count == 0:
        state.winner = 0
        state.game_over_reason = "Player 2 has no Pokemon left in play (Bench out)"
        return


def _end_current_turn(state: GameState) -> None:
    """Reset turn flags, advance turn counter, switch active player, and draw card."""
    cur_player = state.current_player
    cur_player.energy_attached_this_turn = False
    cur_player.supporter_played_this_turn = False
    cur_player.retreated_this_turn = False

    if cur_player.active_pokemon:
        cur_player.active_pokemon.evolved_this_turn = False
        cur_player.active_pokemon.turns_in_play += 1
    for b in cur_player.bench:
        b.evolved_this_turn = False
        b.turns_in_play += 1

    # Switch player
    state.current_player_idx = 1 - state.current_player_idx
    state.turn_count += 1
    next_player = state.current_player

    # Draw card for turn
    if len(next_player.deck) == 0:
        # Deck out loss
        state.winner = 1 - state.current_player_idx
        state.game_over_reason = f"P{next_player.player_id} decked out (Cannot draw card)"
        return

    drawn = next_player.deck.pop()
    next_player.hand.append(drawn)
