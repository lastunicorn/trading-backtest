# Strategies

One folder per strategy in the `strategies/STRATEGIES` registry, `<name>/`. Its `<name>-implementation.md` is what the code does: the config name and class, the rules as implemented, the parameters and how to backtest it. A `<name>-rules.md` beside it, when there is one, is the strategy as it was originally written down, before it was implemented; the implementation page says where the code departs from it. How the backtest framework itself works is in [doc/backtest-framework](../backtest-framework/README.md); to add a strategy, see [Writing a new strategy](../backtest-framework/writing-a-strategy.md) and add its folder here.

- [Narrow Asia London Fade](narrow-asia-fade/narrow-asia-fade-implementation.md) (`narrow_asia_fade`): fade the London break of a narrow Asia range.
- [ORB — Break Entry](orb-break-entry/orb-break-entry-implementation.md) (`orb_break_entry`): stop entries at the New York 09:30–09:45 opening range, stop at its midpoint, 2R target. Original rules: [orb-break-entry-rules.md](orb-break-entry/orb-break-entry-rules.md).
- [RSI Divergence](rsi-divergence/rsi-divergence-implementation.md) (`rsi_divergence`): regular RSI divergences on M15.
- [Session Breakout](session-breakout/session-breakout-implementation.md) (`session_breakout`): breakout of the Tokyo/Asian session range, the rules of the removed `session_breakout_strategy.py`. Original rules: [session-breakout-rules.md](session-breakout/session-breakout-rules.md).
