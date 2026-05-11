"""
Hilo People — Module runner for verification_data bootstrap.

Slice:  P00-S02-T003 — Verification data loader and reset
Phase:  P00 Scaffold + Design System
Purpose: Allows `python -m app.verification_data` as an alias for
         `python -m app.verification_data.bootstrap`.
"""

import sys
from app.verification_data.bootstrap import main

sys.exit(main())
