from __future__ import annotations

from skills.app import OpenOrFocusSkill
from skills.docs import CreateDocumentSkill, OpenDocsHomeSkill, VerifyDocumentSkill
from skills.im import SearchChatSkill, SendMessageSkill, SendTextSkill, VerifyMessageSkill
from skills.registry import SkillRegistry


def build_default_skill_registry() -> SkillRegistry:
    reg = SkillRegistry()
    reg.register(OpenOrFocusSkill())
    reg.register(SearchChatSkill())
    reg.register(SendTextSkill())
    reg.register(VerifyMessageSkill())
    reg.register(SendMessageSkill())
    reg.register(OpenDocsHomeSkill())
    reg.register(VerifyDocumentSkill())
    reg.register(CreateDocumentSkill())
    return reg


__all__ = ["build_default_skill_registry"]

