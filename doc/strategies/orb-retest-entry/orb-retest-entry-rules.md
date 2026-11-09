# Opening Range Break (ORB) - Retest Entry

This file describes the ORB strategy that uses the Retest Entry approach.

**Retest Entry** is referring to the approach of choosing to open a transaction after the price breaks the zone, come backs into the zone to retest it and then continues in the initial direction. This approach offers a more confidence that the price is indeed going in that direction, as opposed to other approaches like Break Entry when the transaction is started immediately as it breaks the zone.

## Rules

### 1) Opening Range (OR)

Define the New York Opening Range:

- 9:30 - 9:45 ET (15 min)

Draw horizontal lines for the max and min prices of this range.

**Note:** The size of the opening range (15 min) may be adapted for each symbol based on the results of the backtesting performed on that symbol.

### 2) Limit orders

When the price breaks the min or max of the OR, create a limit order at the middle of the OR. The new position should be opened only when the prices retests this level (the middle of the OR).

- **long limit order**
  - for the case when price breaks above the OR
- **short limit order**
  - for the case when price breaks below the OR

### 3) Stop Loss (SL)

For both of the limit orders set the SL to be the **the other side of the OR**

### 4) Take Profit (TP)

Set the TP to be **3R** 

- This means that the TP (reward) is three times as big as the SL (risk)

**Note:** The TP may be adapted for each symbol based on the results of the backtesting performed on that symbol.

## Additional rules

- Cancel limit orders after 11:30 ET
- Open at most one trade per day.
  - There may be days with no transactions opened.

## Symbols

Suggested to be used for Indexes from America.

- Ex: Nasdaq 100
