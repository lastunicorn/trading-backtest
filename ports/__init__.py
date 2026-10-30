"""Reusable I/O building blocks: the code that knows file formats.

A port knows a file format and nothing else -- it parses one record into one
typed object and stops. What the data then becomes (cleaned, deduplicated,
resampled) is `domain/`'s job.
"""
