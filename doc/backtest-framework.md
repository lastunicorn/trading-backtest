# Backtest Framework
I want to build a small framework that is able to backtest a trading strategy.

## Domain
In the domain I want the historical data to be stored as pandas DataFrame objects.

**HistoricalData** (domain entity)

- data (DataFrame)
- timeframe (SampleSize)

Each record from the DataFrame represents a bar with the following columns:

**Bar**

- date + time (datetime)
- open price (float)
	- bid value
- high price (float)
	- bid value
- low price (float)
	- bid value
- close price (float)
	- bid value
- tick_volume (int)
	- The number of ticks per bar
	- optinal
- volume (int)
	- The traded volume
	- optional
- spread (float)
	- in pips
	- optional

The framework should be able to simulate positions.

**Position** (domain entity)

- open_dt (datetime)
- open_price (float)
- side (Side)
- sl (float)
	- price value
- tp (float)
	- price value
- close_price (float)
- close_dt (datetime)
- outcome (PositionOutcome)

**Side** (enum)

- "long"
- "short"

**PositionOutcome** (enum)

- "none"
- "stop-loss-hit"
- "take-profit-hit"
- "manual-close"
- "ambiguous"

## Trading Strategy

The `TradingStrategy` instance should receive a `HistoricalData` instance and generate a collection of `Position`.

`TradingStrategy` should be a base class so that it can be inherited and implement different strategies.

## Backtest

A `Backtest` class will receive both a `TradingStrategy` and a `HistoricalData` instances.

Will write into an output directory the results:

- File containing a collection of positions (open time and  price, close time and price, outcome, etc.)
- File containing statistics:
  - count of success positions
  - count of failed positions
  - success rate (in percentages)
  - etc.
