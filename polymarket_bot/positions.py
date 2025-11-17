from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable


@dataclass
class Position:
    market_id: str
    question: str
    yes_size: float = 0.0
    no_size: float = 0.0
    cost: float = 0.0
    settled: bool = False
    winning_outcome: str | None = None
    payout: float = 0.0

    def expected_settlement(self) -> float:
        """Return the guaranteed settlement given balanced YES/NO holdings."""
        return max(self.yes_size, self.no_size)


@dataclass
class PositionLedger:
    _positions: Dict[str, Position] = field(default_factory=dict)

    def record_purchase(self, market_id: str, question: str, yes_size: float, no_size: float, cost: float) -> Position:
        position = self._positions.get(market_id)
        if position is None:
            position = Position(market_id=market_id, question=question)
            self._positions[market_id] = position
        position.yes_size += yes_size
        position.no_size += no_size
        position.cost += cost
        return position

    def mark_settled(self, market_id: str, winning_outcome: str) -> Position | None:
        position = self._positions.get(market_id)
        if position is None:
            return None
        if position.settled:
            return position
        normalized = winning_outcome.lower()
        payout = position.yes_size if normalized == "yes" else position.no_size
        position.settled = True
        position.winning_outcome = winning_outcome
        position.payout = payout
        return position

    def open_positions(self) -> Iterable[Position]:
        return (pos for pos in self._positions.values() if not pos.settled)

    def unsettled_value(self) -> float:
        return sum(pos.expected_settlement() for pos in self.open_positions())

