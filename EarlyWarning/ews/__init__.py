"""Early warning system: Phase 1 data foundation.

Turns the collected datasets (PIHPS food prices and the BI SPIP payment
series) into one clean, validated, regularly spaced and log-transformed
table under ``EarlyWarning/data/``.  ``Dataset/`` is only ever read.

Pipeline, one module per step::

    inventory -> load -> calendar -> validate -> transform

Run it with ``python -m ews.run`` from the ``EarlyWarning`` folder.
"""
