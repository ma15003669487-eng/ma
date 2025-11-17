import asyncio
import logging
from polymarket_bot.arbitrage import find_arbitrage_opportunities
from polymarket_bot.config import BotConfig
from polymarket_bot.market_data import MarketDataClient
from polymarket_bot.telegram_notifier import ControlCallbacks, TelegramNotifier
from polymarket_bot.trader import PolymarketTrader

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


async def main() -> None:
    config = BotConfig()
    config.validate()

    market_client = MarketDataClient(config.polymarket_api)
    current_threshold = config.arbitrage_threshold
    current_quote_size = config.quote_size

    def _clamp_threshold(value: float) -> float:
        return max(0.5, min(1.0, value))

    def increase_threshold() -> float:
        nonlocal current_threshold
        current_threshold = _clamp_threshold(current_threshold + config.arbitrage_step)
        return current_threshold

    def decrease_threshold() -> float:
        nonlocal current_threshold
        current_threshold = _clamp_threshold(current_threshold - config.arbitrage_step)
        return current_threshold

    def increase_quote() -> float:
        nonlocal current_quote_size
        current_quote_size = max(config.quote_step, current_quote_size + config.quote_step)
        return current_quote_size

    def decrease_quote() -> float:
        nonlocal current_quote_size
        current_quote_size = max(config.quote_step, current_quote_size - config.quote_step)
        return current_quote_size

    def status_message() -> str:
        return (
            f"当前套利阈值: {current_threshold:.4f}\n"
            f"当前下单金额: {current_quote_size:.2f} USDC"
        )

    notifier = TelegramNotifier(
        config.telegram_token,
        config.telegram_chat_id,
        controls=ControlCallbacks(
            increase_threshold=increase_threshold,
            decrease_threshold=decrease_threshold,
            increase_quote=increase_quote,
            decrease_quote=decrease_quote,
            status_message=status_message,
        ),
    )

    trader: PolymarketTrader | None = None
    if config.private_key:
        trader = PolymarketTrader(private_key=config.private_key, chain_id=config.chain_id)
        wallet_info = trader.ensure_wallet()
        logger.info("Trading with wallet %s on %s", wallet_info["address"], wallet_info["chain"])
    else:
        logger.info("Running in alert-only mode; no PRIVATE_KEY provided")

    def execute_trade(opportunity):
        if not trader:
            logger.warning("Trade requested but no trader configured")
            return
        result = trader.place_balanced_orders(
            opportunity,
            quote_size=current_quote_size,
            taker_fee_bps=config.taker_fee_bps,
            gas_fee_usd=config.gas_fee_usd,
            min_balance_buffer=config.min_balance_buffer,
        )
        if result.ok:
            logger.info(
                "Orders submitted: %s (cost %.4f, balance %s)",
                ", ".join(result.order_ids),
                result.total_cost,
                result.balance,
            )
        else:
            logger.error("Trade failed: %s", result.message)

    await notifier.start()
    while True:
        try:
            markets = list(market_client.fetch_binary_markets())
            opportunities = find_arbitrage_opportunities(markets, threshold=current_threshold)
            for opportunity in opportunities:
                risk = (
                    trader.assess_risk(
                        opportunity,
                        quote_size=current_quote_size,
                        taker_fee_bps=config.taker_fee_bps,
                        gas_fee_usd=config.gas_fee_usd,
                        min_balance_buffer=config.min_balance_buffer,
                    )
                    if trader
                    else None
                )
                await notifier.send_arbitrage_alert(
                    opportunity=opportunity,
                    auto_execute=config.auto_trade,
                    on_execute=execute_trade,
                    risk=risk,
                )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Error while scanning markets: %s", exc)
        await asyncio.sleep(30)


if __name__ == "__main__":
    asyncio.run(main())
