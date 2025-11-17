from dataclasses import dataclass
from typing import Callable

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from polymarket_bot.arbitrage import ArbitrageOpportunity
from polymarket_bot.trader import RiskAssessment


@dataclass
class ControlCallbacks:
    increase_threshold: Callable[[], float]
    decrease_threshold: Callable[[], float]
    increase_quote: Callable[[], float]
    decrease_quote: Callable[[], float]
    status_message: Callable[[], str]


class TelegramNotifier:
    _BOTTOM_BUTTONS = ReplyKeyboardMarkup(
        [
            ["⬆️ 阀值", "⬇️ 阀值"],
            ["⬆️ 下单金额", "⬇️ 下单金额"],
            ["📊 状态"],
        ],
        resize_keyboard=True,
    )

    def __init__(self, token: str, chat_id: str, controls: ControlCallbacks | None = None) -> None:
        self.token = token
        self.chat_id = chat_id
        self._application: Application | None = None
        self._callbacks: dict[str, tuple[ArbitrageOpportunity, Callable[[ArbitrageOpportunity], None]]] = {}
        self._controls = controls
        self._controls_prompted = False

    async def start(self) -> None:
        if self._application:
            return
        self._application = Application.builder().token(self.token).build()
        self._application.add_handler(CallbackQueryHandler(self._on_callback))
        self._application.add_handler(CommandHandler("start", self._on_start))
        self._application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._on_text))
        await self._application.initialize()
        await self._application.start()
        await self._application.updater.start_polling(allowed_updates=["callback_query", "message"])

    async def send_arbitrage_alert(
        self,
        opportunity: ArbitrageOpportunity,
        auto_execute: bool,
        on_execute: Callable[[ArbitrageOpportunity], None],
        risk: RiskAssessment | None = None,
    ) -> None:
        if not self._application:
            raise RuntimeError("Notifier not started")

        if self._controls and not self._controls_prompted:
            await self._application.bot.send_message(
                chat_id=self.chat_id,
                text="使用下方固定按钮调整套利阈值或下单金额。",
                reply_markup=self._BOTTOM_BUTTONS,
            )
            self._controls_prompted = True

        keyboard = [
            [
                InlineKeyboardButton("✅ Execute", callback_data=f"exec:{opportunity.market.id}"),
                InlineKeyboardButton("🚫 Ignore", callback_data=f"ignore:{opportunity.market.id}"),
            ]
        ]
        self._callbacks[opportunity.market.id] = (opportunity, on_execute)
        text = self._render_message(opportunity, auto_execute, risk)
        await self._application.bot.send_message(
            chat_id=self.chat_id,
            text=text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN,
        )
        if auto_execute:
            on_execute(opportunity)

    async def _on_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text(
            "Polymarket arbitrage bot online. You'll receive alerts here.",
            reply_markup=self._BOTTOM_BUTTONS,
        )

    async def _on_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message or not self._controls:
            return
        text = (update.message.text or "").strip()
        reply: str | None = None
        if text == "⬆️ 阀值":
            new_val = self._controls.increase_threshold()
            reply = f"新的套利阈值: {new_val:.4f}"
        elif text == "⬇️ 阀值":
            new_val = self._controls.decrease_threshold()
            reply = f"新的套利阈值: {new_val:.4f}"
        elif text == "⬆️ 下单金额":
            new_val = self._controls.increase_quote()
            reply = f"新的下单金额: {new_val:.2f} USDC"
        elif text == "⬇️ 下单金额":
            new_val = self._controls.decrease_quote()
            reply = f"新的下单金额: {new_val:.2f} USDC"
        elif text == "📊 状态":
            reply = self._controls.status_message()

        if reply:
            await update.message.reply_text(reply, reply_markup=self._BOTTOM_BUTTONS)

    async def _on_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.callback_query:
            return
        query = update.callback_query
        await query.answer()
        data = query.data or ""
        try:
            action, market_id = data.split(":", 1)
        except ValueError:
            return
        if action != "exec":
            await query.edit_message_text("Opportunity ignored.")
            return
        stored = self._callbacks.get(market_id)
        if stored:
            opportunity, handler = stored
            await query.edit_message_text("Executing trade...")
            handler(opportunity)

    def _render_message(
        self, opportunity: ArbitrageOpportunity, auto_execute: bool, risk: RiskAssessment | None
    ) -> str:
        yes_price = opportunity.yes_price
        no_price = opportunity.no_price
        price_sum = yes_price + no_price
        risk_block = ""
        if risk:
            balance_line = f"Balance: `{risk.balance:.4f}`" if risk.balance is not None else "Balance: `n/a`"
            risk_block = (
                f"\nFee: `{risk.fee:.4f}` | Gas: `{risk.gas:.4f}`\n"
                f"Total cost: `{risk.total_cost:.4f}` | {balance_line}"
            )
            if not risk.can_trade and risk.reason:
                risk_block += f"\n⚠️ {risk.reason}"
        return (
            f"*Arbitrage found!*\n"
            f"{opportunity.market.question}\n"
            f"YES ask: `{yes_price:.4f}` | NO ask: `{no_price:.4f}`\n"
            f"Sum: `{price_sum:.4f}` (edge `{opportunity.edge:.4f}`)\n"
            f"Mode: {'auto' if auto_execute else 'manual'}" + risk_block
        )
