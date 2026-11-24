"""Tests of the integration inside Home Assistant.

They need the packages in ``requirements_test.txt`` and run on Linux or macOS
(Home Assistant does not run on Windows)::

    pip install -r requirements_test.txt
    python -m pytest tests_ha

The protocol tests in ``tests/`` need no packages and run separately with
``python -m unittest discover -s tests -t .``.
"""
