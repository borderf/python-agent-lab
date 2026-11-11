"""Explicitly selected contracts; their filenames avoid default collection.

Unimplemented learner code fails when requested. No blanket skip is used.
"""
import importlib
import re

import pytest


def pytest_addoption(parser):
    parser.addoption("--learner-module", default=None, help="Dotted path of YOUR implementation")
    parser.addoption("--through-step", type=int, default=20, help="DocPilot steps to collect (1..20)")


def pytest_collection_modifyitems(config, items):
    through = config.getoption("--through-step")
    if not 1 <= through <= 20:
        raise pytest.UsageError("--through-step must be in 1..20")
    retained, deselected = [], []
    for item in items:
        number = re.match(r"test_s(\d\d)_", item.name)
        (deselected if number and int(number[1]) > through else retained).append(item)
    items[:] = retained
    config.hook.pytest_deselected(items=deselected)


@pytest.fixture(scope="session")
def implementation(request):
    path = request.config.getoption("--learner-module")
    if not path:
        raise pytest.UsageError("Provide --learner-module=your.module; reference success is not learner completion")
    return importlib.import_module(path)
