"""Use cases that wire `ports/` and `domain/` into a whole task.

Where a port knows a file format and `domain/` knows what the data should look
like, a module in here orchestrates the two end to end -- read the raw exports,
resample and merge them, write the result -- and hands back the numbers a CLI
reports. The I/O lives here so `domain/` can stay a pure, testable core.

    from application.resample_use_case import resample
"""
