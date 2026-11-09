# Opening Range Break (ORB) - Break Entry

This file describes the ORB strategy that uses the Break Entry approach.

**Break Entry** is referring to the approach of choosing to open a transaction exactly in the moment when the price breaks above or below the range. As opposed to other approaches like Retest Entry when the transaction is started after the price comes back end retests the range.

## Rules

### 1) Opening Range (OR)

Define the New York Opening Range:

- 9:30 - 9:45 ET (15 min)

Draw horizontal lines for the max and min prices of this range.

**Note:** The size of the opening range (15 min) may be adapted for each symbol based on the results of the backtesting performed on that symbol.

### 2) Stop orders

Create two stop orders, one for each side (top and bottom) of the OR, where the price can break:

- **long order - at top (max) of the OR**
  - for the case when price breaks above the OR
- **short order - at bottom (min) of the OR**
  - for the case when price breaks below the OR

### 3) Stop Loss (SL)

For both of the stop orders set the SL to be the **middle of the OR**

### 4) Take Profit (TP)

Set the TP to be **2R** 

- This means that the TP (reward) is twice as big as the SL (risk)

## Additional rules

- Cancel stop orders after 11:30 ET
- One trade in each direction per day.
  - Open at most two trades per day.
  - There may be days with no transactions opened.
