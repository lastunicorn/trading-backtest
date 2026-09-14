# Tokyo Session Breakout Strategy

This is a strategy proposed by Arty (The Moving Average)

## Description

### Step 1: Define Tokyo session high (H) and low (L)

- H = highest price from the Tokyo session (including wicks)
- L = lowest price from the Tokyo session (including wicks)

**Note:**

- Tokyo session is between 00:00 and 09:00 UTC.

**Cancel Condition:**

- If [H, L] interval > 30 p => cancel any action. Wait for the next day.

### Step 2: Open transaction when H or L is broken

Wait until price breaks H or L:

- If price goes above H => Open long transaction
- If price goes below L => Open short transaction

### Step 3: Stop Loss (SL)

- Set SL to be the middle of the [H, L] interval.

### Step 4: Risk to Reword

- Set TP so that RR is 1:2

## Additional Rules

### Force close transaction at 09:00 UTC (next day)

- Whan you do the analysis for the current day (09:00 UTC), close any existing transaction from yesterday.

### Two transaction per day

- Both transactions short and long may be opened for the same day if the price goes in one direction, breaking one of the limits (H or L) and then decides to go in the oposite direction, breaking the other. This is acceptable.

### Cancel if conditions not met

- If no limit (H or L) are brken until 00:00 UTC => give up.