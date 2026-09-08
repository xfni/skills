#!/usr/bin/env python3
"""
PreToolUse Hook：拦截 .ai/plans/ 文件的写入。
检查 Plan 内容是否包含评审状态标记或跳过声明。
stdin: Claude Code 传入的 JSON（结构为 {"tool_name":..., "tool_input":{...}}）
exit 0: 放行
exit 1: 阻断
"""
import json
import sys

data = json.load(sys.stdin)
tool_input = data.get("tool_input", {})
file_path = tool_input.get("file_path", "")
content = tool_input.get("content", "")

# 只检查 .ai/plans/ 下的 markdown 文件
if ".ai/plans/" not in file_path or not file_path.endswith(".md"):
    sys.exit(0)

has_reviewed = "评审状态" in content and "已通过" in content
has_skip_notice = "跳过了 Spec 评审" in content

if has_reviewed or has_skip_notice:
    sys.exit(0)

print("❌ [spec-review-gate] 计划文件缺少必要标记。")
print()
print("高风险 Spec（并发/生命周期/共享状态）须满足以下之一：")
print("  ① 已完成评审 → Plan 文件含「评审状态：已通过」")
print("  ② 明确跳过   → Plan 文件含「⚠️ 本计划跳过了 Spec 评审」")
print()
print("请调用 spec-review-gate skill 完成门禁流程后重试。")
sys.exit(1)
