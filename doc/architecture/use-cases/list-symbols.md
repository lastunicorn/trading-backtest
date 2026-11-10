# ListSymbols

A [use case](README.md) of the [application blueprint](../README.md).

## Input

| Field | Type | Default |
|---|---|---|
| `filter` | `String?` | `null` |

## Output

`List<Symbol>`: every symbol in `SYMBOLS`, sorted by ticker; with `filter`, only those whose ticker or name contains it (case-insensitive).

## Steps

1. Sort `SYMBOLS` by ticker.
2. Keep the matches, when filtering.
3. None left: `NO_MATCHING_SYMBOL`.

## Errors

| Code | Description |
|---|---|
| `NO_MATCHING_SYMBOL` | `no symbol matches '{filter}'`. |
