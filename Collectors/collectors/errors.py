"""Failures a run should report rather than crash on."""

from __future__ import annotations


class SourceUnavailable(RuntimeError):
    """The source cannot be read from this runner right now.

    Distinct from a parse failure: it means "nothing to collect", not "the
    collector is wrong".  The runner prints it and carries on to the next
    source instead of failing the whole run.
    """


class SourceStale(RuntimeError):
    """The source is readable but has published nothing new for a long time.

    Reported as a warning, never as a failure -- OJK's public channel has been
    stuck since June 2025, and a health report that calls that a crash is
    wrong about where the problem is.
    """
