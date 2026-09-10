"""Minimal asyncio support for the repository's focused test environment.

The runtime checker installs bare pytest rather than the project's optional test
dependencies. When pytest-asyncio is present this hook is unused; otherwise it
provides the small marker/call behavior needed by the async tests.
"""

import asyncio
import inspect

import pytest


def pytest_configure(config):
    config.addinivalue_line("markers", "asyncio: run an async test function")


@pytest.hookimpl(tryfirst=True)
def pytest_pyfunc_call(pyfuncitem):
    if "asyncio" not in pyfuncitem.keywords or not inspect.iscoroutinefunction(pyfuncitem.obj):
        return None
    arguments = {name: pyfuncitem.funcargs[name] for name in pyfuncitem._fixtureinfo.argnames}
    asyncio.run(pyfuncitem.obj(**arguments))
    return True
