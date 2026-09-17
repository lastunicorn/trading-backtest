"""Use cases that wire `ports/` and `domain/` into a whole task.

Where a port knows a file format and `domain/` knows what the data should look
like, a module in here orchestrates the two end to end -- read the raw exports,
clean and merge them -- and hands back the numbers a CLI reports. The I/O lives
here so `domain/` can stay a pure, testable core.

    from application.build_clean_dataset_use_case import build_clean_dataset

`resample_csv.py` used to have its own use-case module here
(`resample_use_case.py`); since it was the module's only caller, that logic now
lives directly in the script.
"""
