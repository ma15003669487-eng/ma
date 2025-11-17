from dataclasses import dataclass
import os

from dotenv import load_dotenv

load_dotenv()


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "y", "on"}


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


@dataclass
class BotConfig:
    polymarket_api: str = os.getenv("POLYMARKET_API", "https://gamma-api.polymarket.com")
    auto_trade: bool = _env_bool("AUTO_TRADE", False)
    arbitrage_threshold: float = _env_float("ARBITRAGE_THRESHOLD", 0.99)
    arbitrage_step: float = _env_float("ARBITRAGE_STEP", 0.01)
    telegram_token: str | None = os.getenv("TELEGRAM_TOKEN")
    telegram_chat_id: str | None = os.getenv("TELEGRAM_CHAT_ID")
    private_key: str | None = os.getenv("PRIVATE_KEY")
    chain_id: int = _env_int("CHAIN_ID", 137)
    quote_size: float = _env_float("QUOTE_SIZE", 20.0)
    quote_step: float = _env_float("QUOTE_STEP", 5.0)
    taker_fee_bps: float = _env_float("TAKER_FEE_BPS", 25)
    gas_fee_usd: float = _env_float("GAS_FEE_USD", 0.05)
    min_balance_buffer: float = _env_float("MIN_BALANCE_BUFFER", 5.0)
    auto_settle: bool = _env_bool("AUTO_SETTLE", False)

    def validate(self) -> None:
        if self.telegram_token is None or self.telegram_chat_id is None:
            raise ValueError("Telegram credentials (TELEGRAM_TOKEN, TELEGRAM_CHAT_ID) are required")
        if self.auto_trade and self.private_key is None:
            raise ValueError("PRIVATE_KEY is required when AUTO_TRADE is enabled")
