"""
Foundry Workshop Notebook Testing Framework

A modern, production-grade testing framework for validating Jupyter notebooks
that deploy Azure infrastructure.

Usage:
    python -m tests run                    # Run all notebooks
    python -m tests run --notebook NAME    # Run specific notebook
    python -m tests list                   # List available notebooks
    python -m tests cleanup                # Clean up Azure resources
"""

__version__ = "1.0.0"
