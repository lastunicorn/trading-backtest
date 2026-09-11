"""Console presentation for CLI tools, plus the bounded-window helper behind it.

Not part of the numbered research pipeline and not `ports`/`domain`/
`application`/`tools` either -- this is display-only code: `BarWindow`
selects the bars a CLI wants to show and tracks display-only bookkeeping
(visible count, which columns have data), and `bar_window_view` turns one
into printed output. Versionless, freely editable, same as `tools/`.
"""
