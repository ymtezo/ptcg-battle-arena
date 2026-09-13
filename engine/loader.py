"""Helper functions to load card database and deck recipes from JSON."""

import json
from pathlib import Path
from typing import Dict, List, Tuple
from engine.card import Card


def load_card_database(db_path: Path) -> Dict[str, Card]:
    """Load cards from card_database.json and index by ID."""
    with open(db_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    cards: Dict[str, Card] = {}
    for c_data in data.get("cards", []):
        card = Card.from_dict(c_data)
        cards[card.id] = card
    return cards


def load_sample_decks(
    decks_path: Path, card_db: Dict[str, Card]
) -> Dict[str, Tuple[str, List[Card]]]:
    """
    Load sample decks from sample_decks.json.
    Returns mapping: deck_key -> (deck_name, list_of_60_cards)
    """
    with open(decks_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    decks: Dict[str, Tuple[str, List[Card]]] = {}
    for key, deck_info in data.get("decks", {}).items():
        name = deck_info.get("name", key)
        deck_cards: List[Card] = []
        for item in deck_info.get("cards", []):
            card_id = item["id"]
            count = item.get("count", 1)
            if card_id not in card_db:
                raise ValueError(f"Unknown card ID '{card_id}' in deck '{key}'")
            card_template = card_db[card_id]
            for _ in range(count):
                # Append copies of card
                deck_cards.append(card_template)
        decks[key] = (name, deck_cards)

    return decks
