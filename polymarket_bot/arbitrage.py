from dataclasses import dataclass
from typing import Iterable

from polymarket_bot.market_data import Market


@dataclass
class ArbitrageOpportunity:
    market: Market
    yes_price: float
    no_price: float
    edge: float


def find_arbitrage_opportunities(markets: Iterable[Market], threshold: float = 1.0) -> list[ArbitrageOpportunity]:
    opportunities: list[ArbitrageOpportunity] = []
    for market in markets:
        yes_price, no_price = market.yes_no_prices()
        if yes_price is None or no_price is None:
            continue
        price_sum = yes_price + no_price
        if price_sum < threshold:
            opportunities.append(
                ArbitrageOpportunity(
                    market=market,
                    yes_price=yes_price,
                    no_price=no_price,
                    edge=threshold - price_sum,
                )
            )
    return sorted(opportunities, key=lambda opp: opp.edge, reverse=True)
