"""create_agent: Part 2's MedNexaAgent when installed, otherwise the stub."""

from __future__ import annotations

import sys
import types

import pytest

import telephony.config as cfg_module
from telephony.agent_interface import StubAgent, create_agent


class FakeMedNexaAgent:
    def __init__(self, caller_phone: str, hospital_id: str) -> None:
        self.args = (caller_phone, hospital_id)


@pytest.fixture()
def fake_agent_package(monkeypatch: pytest.MonkeyPatch) -> None:
    module = types.ModuleType("agent")
    module.MedNexaAgent = FakeMedNexaAgent  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "agent", module)


def test_uses_mednexa_agent_when_installed(fake_agent_package: None) -> None:
    agent = create_agent("+919876543210", "hosp-1")
    assert isinstance(agent, FakeMedNexaAgent)
    assert agent.args == ("+919876543210", "hosp-1")


def test_falls_back_to_stub_when_not_installed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "agent", None)  # makes `import agent` fail
    assert isinstance(create_agent("+919876543210", "hosp-1"), StubAgent)


def test_stub_can_be_forced(fake_agent_package: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cfg_module.get_settings(), "use_stub_agent", True)
    assert isinstance(create_agent("+919876543210", "hosp-1"), StubAgent)
