"""Game-Theoretic Minimax / Regret-Minimization Defensive Agent for Pokemon TCG.

Focuses on minimizing worst-case damage, preserving energy tempo,
preventing easy prize trades, avoiding bench-out losses, and maximizing board value.
"""

from typing import List, Optional, Tuple
from agents.base import BaseAgent
from engine.card import Card, CardType, PokemonStage, Attack
from engine.gamestate import GameState, PlayerState, PokemonInstance
from engine.rules import Action, ActionType, check_attack_energy_cost, get_legal_actions


class MinimaxDefensiveAgent(BaseAgent):
    """
    Advanced Game-Theoretic Agent (Minimax Regret & Board State Optimization).

    Key Refinements:
    1. Zero Bench-Out Risk: Always play basics and search cards to maintain >= 2 bench.
    2. Stage 2 Priority: Prioritize Rare Candy -> Stage 2 evolution to maximize tanking HP (330 HP).
    3. Lethal Gusting: Only use Boss's Orders when our active is fully charged and can confirm a KO on the pulled target.
    4. Strategic Iono Timing: Play Iono when opponent has fewer prizes to induce severe hand starvation.
    5. Energy Tempo: Ensure active has enough energy to strike; divert surplus energy to prepare bench reserve.
    """

    def __init__(self, name: str = "MinimaxDefensiveAgent") -> None:
        super().__init__(name)

    def choose_action(self, state: GameState, legal_actions: List[Action]) -> Action:
        """Evaluate legal moves and choose the optimal decision."""
        if not legal_actions:
            return Action(action_type=ActionType.END_TURN)

        player = state.current_player
        opp = state.opponent_player

        if len(legal_actions) == 1:
            return legal_actions[0]

        opp_max_threat, opp_threat_source = self._estimate_opponent_max_threat(opp, player.active_pokemon)

        # ---------------------------------------------------------
        # PHASE 1: BENCH INTEGRITY (Eliminate Bench-out Defeat)
        # ---------------------------------------------------------
        basics = [a for a in legal_actions if a.action_type == ActionType.PLAY_BASIC]
        if basics:
            return basics[0]

        if len(player.bench) <= 1:
            search_items = [
                a for a in legal_actions
                if a.action_type == ActionType.PLAY_ITEM
                and a.card_idx < len(player.hand)
                and player.hand[a.card_idx].effect in ("SEARCH_BASIC_TO_BENCH", "SEARCH_ANY_POKEMON")
            ]
            if search_items:
                return search_items[0]

            draw_supporters = [
                a for a in legal_actions
                if a.action_type == ActionType.PLAY_SUPPORTER
                and a.card_idx < len(player.hand)
                and player.hand[a.card_idx].effect in ("DISCARD_AND_DRAW_7", "HAND_TO_DECK_DRAW_PRIZES")
            ]
            if draw_supporters:
                return draw_supporters[0]

        # ---------------------------------------------------------
        # PHASE 2: EVOLUTION (Prioritize Stage 2 / High HP Tanks)
        # ---------------------------------------------------------
        rare_candies = [
            a for a in legal_actions
            if a.action_type == ActionType.PLAY_ITEM and "s2_idx" in a.extra_args
        ]
        if rare_candies:
            return rare_candies[0]

        evolutions = [a for a in legal_actions if a.action_type == ActionType.EVOLVE]
        if evolutions:
            # Prioritize active evolution first, then highest HP
            active_evos = [a for a in evolutions if a.target_idx == -1]
            if active_evos:
                return active_evos[0]
            return evolutions[0]

        # ---------------------------------------------------------
        # PHASE 3: LETHAL DISRUPTION (Boss's Orders)
        # Only pull if our active can attack AND score a guaranteed KO
        # ---------------------------------------------------------
        boss_actions = [
            a for a in legal_actions
            if a.action_type == ActionType.PLAY_SUPPORTER
            and a.card_idx < len(player.hand)
            and player.hand[a.card_idx].effect == "SWITCH_OPPONENT_ACTIVE"
        ]
        if boss_actions and self._can_active_attack(player.active_pokemon):
            lethal_boss = self._find_lethal_boss_target(state, boss_actions)
            if lethal_boss:
                return lethal_boss

        # ---------------------------------------------------------
        # PHASE 4: SMART ENERGY ATTACHMENT
        # ---------------------------------------------------------
        attaches = [a for a in legal_actions if a.action_type == ActionType.ATTACH_ENERGY]
        if attaches and not player.energy_attached_this_turn:
            return self._choose_smart_energy_attach(state, attaches, opp_max_threat)

        # ---------------------------------------------------------
        # PHASE 5: TACTICAL SWITCH / RETREAT (Preserve Doomed High-Value Pokemon)
        # ---------------------------------------------------------
        if player.active_pokemon and opp_max_threat > 0:
            active_is_doomed = player.active_pokemon.current_hp <= opp_max_threat
            # Only retreat if active cannot attack this turn anyway and bench has a strong tank
            if active_is_doomed and not self._can_active_attack(player.active_pokemon) and player.bench:
                switches = [
                    a for a in legal_actions
                    if a.action_type == ActionType.PLAY_ITEM
                    and a.card_idx < len(player.hand)
                    and player.hand[a.card_idx].effect == "SWITCH_ACTIVE_WITH_BENCH"
                ]
                if switches:
                    best_switch = self._pick_highest_hp_bench_target(player, switches)
                    if best_switch:
                        return best_switch

                retreats = [a for a in legal_actions if a.action_type == ActionType.RETREAT]
                if retreats and len(player.active_pokemon.attached_energies) <= 1:
                    best_retreat = self._pick_highest_hp_bench_target(player, retreats)
                    if best_retreat:
                        return best_retreat

        # ---------------------------------------------------------
        # PHASE 6: SUPPORTERS & CARD DRAW
        # ---------------------------------------------------------
        supporters = [a for a in legal_actions if a.action_type == ActionType.PLAY_SUPPORTER]
        if supporters and not player.supporter_played_this_turn:
            # If opponent has fewer prizes, play Iono to disrupt their hand!
            iono_actions = [
                a for a in supporters
                if a.card_idx < len(player.hand) and player.hand[a.card_idx].effect == "HAND_TO_DECK_DRAW_PRIZES"
            ]
            if iono_actions and len(opp.prizes) <= 3:
                return iono_actions[0]

            # Otherwise play Research or other supporter
            return supporters[0]

        # ---------------------------------------------------------
        # PHASE 7: ITEMS
        # ---------------------------------------------------------
        items = [a for a in legal_actions if a.action_type == ActionType.PLAY_ITEM]
        if items:
            return items[0]

        # ---------------------------------------------------------
        # PHASE 8: ATTACK (Final Action of the Turn)
        # ---------------------------------------------------------
        attacks = [a for a in legal_actions if a.action_type == ActionType.ATTACK]
        if attacks and player.active_pokemon:
            best_atk = None
            best_score = -999999.0
            for a in attacks:
                score = self._evaluate_attack_action(state, a)
                if score > best_score:
                    best_score = score
                    best_atk = a
            if best_atk:
                return best_atk

        # Pass turn if no other valuable moves
        return Action(action_type=ActionType.END_TURN)

    def _can_active_attack(self, active: Optional[PokemonInstance]) -> bool:
        """Check if active Pokemon can perform at least one attack right now."""
        if not active:
            return False
        return any(
            check_attack_energy_cost(active.attached_energies, atk.energy_cost)
            for atk in active.card.attacks
        )

    def _find_lethal_boss_target(
        self, state: GameState, boss_actions: List[Action]
    ) -> Optional[Action]:
        """Find an opponent bench target that our active can knock out this exact turn."""
        player = state.current_player
        opp = state.opponent_player
        if not player.active_pokemon:
            return None

        my_active = player.active_pokemon
        for act in boss_actions:
            if 0 <= act.target_idx < len(opp.bench):
                target = opp.bench[act.target_idx]
                for atk in my_active.card.attacks:
                    if check_attack_energy_cost(my_active.attached_energies, atk.energy_cost):
                        dmg = atk.damage
                        if target.card.weakness == my_active.card.pokemon_type:
                            dmg *= 2
                        if dmg >= target.current_hp:
                            return act
        return None

    def _estimate_opponent_max_threat(
        self, opp: PlayerState, my_active: Optional[PokemonInstance]
    ) -> Tuple[int, Optional[PokemonInstance]]:
        """Calculate the maximum potential damage opponent can deal next turn."""
        if not opp.active_pokemon or not my_active:
            return 0, None

        threats: List[Tuple[int, PokemonInstance]] = []
        active_dmg = self._calc_max_attack_damage(
            opp.active_pokemon, my_active, virtual_extra_energies=1
        )
        threats.append((active_dmg, opp.active_pokemon))

        for b in opp.bench:
            b_dmg = self._calc_max_attack_damage(b, my_active, virtual_extra_energies=1)
            threats.append((b_dmg, b))

        threats.sort(key=lambda x: x[0], reverse=True)
        return threats[0] if threats else (0, None)

    def _calc_max_attack_damage(
        self, attacker: PokemonInstance, defender: PokemonInstance, virtual_extra_energies: int = 0
    ) -> int:
        """Calculate maximum damage an attacker can inflict on defender."""
        max_d = 0
        available_energies = list(attacker.attached_energies)
        for _ in range(virtual_extra_energies):
            available_energies.append("COLORLESS")

        for atk in attacker.card.attacks:
            if check_attack_energy_cost(available_energies, atk.energy_cost):
                dmg = atk.damage
                if defender.card.weakness == attacker.card.pokemon_type:
                    dmg *= 2
                if dmg > max_d:
                    max_d = dmg
        return max_d

    def _choose_smart_energy_attach(
        self, state: GameState, attaches: List[Action], opp_max_threat: int
    ) -> Action:
        """
        Game-Theoretic Energy Allocation:
        1. If active can attack by attaching 1 more energy, attach to active.
        2. If active already has enough energy to use its best attack, divert energy to bench tank!
        3. If active is doomed to die next turn, divert energy to bench tank.
        4. Otherwise attach to active.
        """
        player = state.current_player
        active = player.active_pokemon
        active_attaches = [a for a in attaches if a.target_idx == -1]
        bench_attaches = [a for a in attaches if a.target_idx >= 0]

        if not active:
            return attaches[0]

        # Check if active already has enough energy for its most expensive attack
        max_cost_needed = max([len(atk.energy_cost) for atk in active.card.attacks], default=1)
        active_is_saturated = len(active.attached_energies) >= max_cost_needed

        active_is_doomed = active.current_hp <= opp_max_threat and opp_max_threat > 0

        # If saturated or doomed, divert to bench
        if (active_is_saturated or active_is_doomed) and bench_attaches:
            # Sort bench by highest HP / evolved stage
            best_bench_act = None
            max_val = -1
            for b_act in bench_attaches:
                poke = player.bench[b_act.target_idx]
                val = poke.current_hp + (100 if poke.card.stage == PokemonStage.STAGE_2 else 0)
                if val > max_val:
                    max_val = val
                    best_bench_act = b_act
            if best_bench_act:
                return best_bench_act

        if active_attaches:
            return active_attaches[0]

        return attaches[0]

    def _pick_highest_hp_bench_target(
        self, player: PlayerState, actions: List[Action]
    ) -> Optional[Action]:
        """Select bench Pokemon with highest HP to absorb incoming hits."""
        best_act = None
        max_hp = -1
        for a in actions:
            if 0 <= a.target_idx < len(player.bench):
                b_hp = player.bench[a.target_idx].current_hp
                if b_hp > max_hp:
                    max_hp = b_hp
                    best_act = a
        return best_act

    def _evaluate_attack_action(self, state: GameState, action: Action) -> float:
        """Evaluate attack action utility."""
        player = state.current_player
        opp = state.opponent_player
        if not player.active_pokemon or not opp.active_pokemon:
            return 0.0

        attack = player.active_pokemon.card.attacks[action.attack_idx]
        dmg = attack.damage
        if opp.active_pokemon.card.weakness == player.active_pokemon.card.pokemon_type:
            dmg *= 2

        score = dmg * 1.0 + attack.bench_damage * 1.5
        if dmg >= opp.active_pokemon.current_hp:
            score += 500.0 * opp.active_pokemon.card.prize_value
            if len(opp.prizes) <= opp.active_pokemon.card.prize_value:
                score += 10000.0

        return score
