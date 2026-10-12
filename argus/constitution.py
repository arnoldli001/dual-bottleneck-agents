"""分层宪法（L5 治理层）。

核心 12 条规则不可修改，适应性规则可进化（需通过回归测试）。
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


# 默认核心规则（与 constitution/core.json 同步）
DEFAULT_CORE_RULES: list[dict[str, Any]] = [
    {"id": 1, "text": "不得自我复制", "keywords": ["自我复制", "self-replicate", "copy_self"]},
    {"id": 2, "text": "不得修改核心规则", "keywords": ["修改核心", "modify_core", "edit_constitution", "change_core"]},
    {"id": 3, "text": "不得绕过沙箱执行", "keywords": ["绕过沙箱", "bypass_sandbox", "no_sandbox", "skip_sandbox"]},
    {"id": 4, "text": "不得访问外部网络（除API调用外）", "keywords": ["外部网络", "external_network", "http_request", "urllib"]},
    {"id": 5, "text": "不得修改其他Agent的宪法", "keywords": ["修改其他", "modify_other", "edit_other"]},
    {"id": 6, "text": "不得在未经验证的情况下提交结果", "keywords": ["未验证", "unverified_submit", "skip_verify"]},
    {"id": 7, "text": "不得使用超过预算的API调用", "keywords": ["超预算", "over_budget", "no_budget"]},
    {"id": 8, "text": "不得修改日志记录", "keywords": ["修改日志", "modify_log", "edit_log"]},
    {"id": 9, "text": "不得绕过Z3验证", "keywords": ["绕过Z3", "bypass_z3", "skip_z3"]},
    {"id": 10, "text": "不得删除检查点", "keywords": ["删除检查点", "delete_checkpoint", "remove_checkpoint"]},
    {"id": 11, "text": "不得修改seed提取逻辑", "keywords": ["修改seed", "modify_seed", "edit_seed"]},
    {"id": 12, "text": "不得禁用熔断器", "keywords": ["禁用熔断", "disable_circuit", "no_breaker"]},
]


@dataclass
class ConstitutionCheck:
    allowed: bool
    violated_rule: str | None = None
    matched_keyword: str | None = None
    rule_id: int | None = None


class Constitution:
    """宪法检查器。"""

    def __init__(self, core_path: Path | None = None):
        self.core_rules: list[dict[str, Any]] = list(DEFAULT_CORE_RULES)
        self.adaptive_rules: list[dict[str, Any]] = []
        if core_path is not None and core_path.exists():
            self.load_core(core_path)

    def load_core(self, path: Path) -> None:
        """从 JSON 加载核心规则（不可在初始化之外被修改）。"""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        rules = data.get("rules", [])
        if rules:
            self.core_rules = rules

    def save_core(self, path: Path) -> None:
        """保存当前核心规则到 JSON。"""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(
                {"version": "1.0", "rules": self.core_rules},
                f, ensure_ascii=False, indent=2,
            )

    def check(self, variant: str | dict[str, Any]) -> ConstitutionCheck:
        """检查变异是否违反核心规则。返回首个匹配。"""
        if isinstance(variant, dict):
            text = json.dumps(variant, ensure_ascii=False)
        else:
            text = str(variant)
        lower = text.lower()
        for rule in self.core_rules + self.adaptive_rules:
            for kw in rule.get("keywords", []):
                if kw.lower() in lower:
                    return ConstitutionCheck(
                        allowed=False,
                        violated_rule=rule["text"],
                        matched_keyword=kw,
                        rule_id=rule["id"],
                    )
        return ConstitutionCheck(allowed=True)

    def add_adaptive_rule(self, rule: dict[str, Any], regression_passed: bool) -> bool:
        """添加适应性规则（回归测试通过才生效）。"""
        if not regression_passed:
            return False
        self.adaptive_rules.append(rule)
        return True
