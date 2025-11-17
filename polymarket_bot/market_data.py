from dataclasses import dataclass
from typing import Iterable

import requests


@dataclass
class OutcomeQuote:
    outcome: str
    best_bid: float | None
    best_ask: float | None


@dataclass
class Market:
    id: str
    question: str
    outcomes: list[OutcomeQuote]

    def yes_no_prices(self) -> tuple[float | None, float | None]:
        yes = None
        no = None
        for outcome in self.outcomes:
            normalized = outcome.outcome.lower()
            if normalized == "yes":
                yes = outcome.best_ask
            elif normalized == "no":
                no = outcome.best_ask
        return yes, no


class MarketDataClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def fetch_binary_markets(self) -> Iterable[Market]:
        url = f"{self.base_url}/markets?limit=1000&active=true"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        payload = response.json()
        for market_data in payload.get("markets", []):
            outcomes = market_data.get("outcomes") or []
            if len(outcomes) != 2:
                continue
            parsed_outcomes: list[OutcomeQuote] = []
            for outcome in outcomes:
                parsed_outcomes.append(
                    OutcomeQuote(
                        outcome=str(outcome.get("outcome") or outcome.get("name")),
                        best_bid=_safe_float(outcome.get("bestBid")),
                        best_ask=_safe_float(outcome.get("bestAsk")),
                    )
                )
            yield Market(
                id=str(market_data.get("id")),
                question=str(market_data.get("question")),
                outcomes=parsed_outcomes,
            )


def _safe_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
