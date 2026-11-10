# `show_symbols`

A [CLI](README.md) of the [application blueprint](../README.md).

*Python: `show_symbols.py`.* Lists the known symbols. Use case: [ListSymbols](../use-cases/list-symbols.md).

```
show_symbols [--filter TEXT]
```

| Argument | Type | Default | Notes |
|---|---|---|---|
| `--filter` | `String` | none | only symbols whose ticker or name contains it (case-insensitive) |

Validation: none beyond the parser. No match: `ERROR: no symbol matches '{filter}'`, exit 1.

Output: a [`format_table`](shared-presentation.md#format_table) with the columns `TICKER`, `NAME` (left-aligned), `CATEGORY`, `PIP SIZE`, `TICK SIZE`, `DECIMALS`; pip and tick size are printed with the symbol's `price_decimals` places.
