"""
COBOL Moderniser -- Autonomous migration of legacy COBOL to modern Python.

A 5-agent pipeline that reads legacy COBOL programs, extracts business rules,
generates comprehensive test suites, writes idiomatic Python, and validates
behavioural equivalence to the penny.

Usage:
    import cobol_moderniser
    print(cobol_moderniser.__version__)

CLI:
    cobol-moderniser migrate input.cbl --target python --output ./output
"""

__version__ = "0.1.0"
__author__ = "Kannan Swamy"
__license__ = "MIT"
