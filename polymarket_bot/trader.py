from dataclasses import dataclass

from hexbytes import HexBytes
from py_clob_client.client import ClobClient
from py_clob_client.constants import POLYGON_CHAIN_NAME_FROM_ID
from py_clob_client.order_builder.constants import BUY
from py_clob_client.order_builder.order_builder import OrderBuilder
from py_clob_client.order_builder.types import OrderArgs

from polymarket_bot.arbitrage import ArbitrageOpportunity
from polymarket_bot.positions import PositionLedger


@dataclass
class TradeResult:
    ok: bool
    message: str
    order_ids: list[str]
    total_cost: float = 0.0
    balance: float | None = None


@dataclass
class RiskAssessment:
    total_cost: float
    fee: float
    gas: float
    balance: float | None
    can_trade: bool
    reason: str | None = None


class PolymarketTrader:
    def __init__(self, private_key: str, chain_id: int) -> None:
        chain_name = POLYGON_CHAIN_NAME_FROM_ID.get(chain_id)
        if not chain_name:
            raise ValueError(f"Unsupported chain id: {chain_id}")
        self.client = ClobClient(private_key=private_key, chain_id=chain_id)
        self.chain_name = chain_name
        self.positions = PositionLedger()

    def ensure_wallet(self) -> dict[str, str]:
        address = self.client.get_address().lower()
        return {"address": address, "chain": self.chain_name}

    def mark_settled(self, market_id: str, winning_outcome: str):
        """Record settlement information for a filled position."""
        return self.positions.mark_settled(market_id, winning_outcome)

    def assess_risk(
        self,
        opportunity: ArbitrageOpportunity,
        quote_size: float,
        taker_fee_bps: float,
        gas_fee_usd: float,
        min_balance_buffer: float,
    ) -> RiskAssessment:
        yes_cost = quote_size * opportunity.yes_price
        no_cost = quote_size * opportunity.no_price
        notional = yes_cost + no_cost
        fee = notional * taker_fee_bps / 10_000
        total_cost = notional + fee + gas_fee_usd

        balance = self._get_usdc_balance()
        balance_ok = balance is None or balance >= total_cost + min_balance_buffer
        reason = None if balance_ok else "Insufficient USDC balance"
        return RiskAssessment(total_cost=total_cost, fee=fee, gas=gas_fee_usd, balance=balance, can_trade=balance_ok, reason=reason)

    def place_balanced_orders(
        self,
        opportunity: ArbitrageOpportunity,
        quote_size: float,
        taker_fee_bps: float,
        gas_fee_usd: float,
        min_balance_buffer: float,
    ) -> TradeResult:
        risk = self.assess_risk(opportunity, quote_size, taker_fee_bps, gas_fee_usd, min_balance_buffer)
        if not risk.can_trade:
            return TradeResult(ok=False, message=risk.reason or "Risk check failed", order_ids=[], total_cost=risk.total_cost, balance=risk.balance)

        orders = []
        for outcome, price in (("YES", opportunity.yes_price), ("NO", opportunity.no_price)):
            if price <= 0:
                return TradeResult(ok=False, message=f"Invalid price for {outcome}", order_ids=[], total_cost=risk.total_cost, balance=risk.balance)
            order = self._build_order(market_id=opportunity.market.id, outcome=outcome, price=price, size=quote_size)
            orders.append(order)
        try:
            receipts = [self._post_order(order) for order in orders]
        except Exception as exc:  # noqa: BLE001
            return TradeResult(ok=False, message=str(exc), order_ids=[], total_cost=risk.total_cost, balance=risk.balance)
        order_ids = [receipt.get("order_id", "") for receipt in receipts]
        self.positions.record_purchase(
            market_id=opportunity.market.id,
            question=opportunity.market.question,
            yes_size=quote_size,
            no_size=quote_size,
            cost=risk.total_cost,
        )
        return TradeResult(ok=True, message="Orders posted", order_ids=order_ids, total_cost=risk.total_cost, balance=risk.balance)

    def _build_order(self, market_id: str, outcome: str, price: float, size: float) -> OrderArgs:
        builder = OrderBuilder(
            private_key=HexBytes(self.client.private_key),
            chain_id=self.client.chain_id,
            verifying_contract=self.client.verifying_contract,
        )
        return builder.build(
            market_id=market_id,
            price=price,
            size=size,
            side=BUY,
            outcome=outcome,
            token_id=self.client.get_usdc_token(),
        )

    def _post_order(self, order: OrderArgs) -> dict:
        # Use the official CLOB endpoint to submit signed orders
        return self.client.post_order(order)

    def _get_usdc_balance(self) -> float | None:
        token = self.client.get_usdc_token()
        getter = getattr(self.client, "get_balance", None)
        if callable(getter):
            try:
                return float(getter(token))
            except Exception:  # noqa: BLE001
                return None
        getter = getattr(self.client, "get_usdc_balance", None)
        if callable(getter):
            try:
                return float(getter())
            except Exception:  # noqa: BLE001
                return None
        return None
