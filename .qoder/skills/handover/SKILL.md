---
name: handover
description: Maintain the project work-item ledger in HANDOVER.md — move items from TODO to COMPLETE when done, add new TODO items when new requirements appear, delete items when a feature is dropped, and keep a resumable session context in memo.md. Use when starting or ending a work session, when the user says "handover", "交接", "开始干活", "收工", or when a work item finishes, a new requirement surfaces, or a feature is removed.
license: MIT
metadata:
  version: "1.0.0"
  project: KnowEverything
---

# Handover Ledger

Keep `HANDOVER.md` (work items) and `memo.md` (memory) truthful, so the next person — or the next session of you — can pick up cold without asking what happened.

## Why this exists

Two failure modes are worth preventing, and both have bitten this project:

1. **Stale ledgers.** An item is finished but still sits in TODO. The next session redoes it, or worse, "fixes" code that was already correct and breaks it.
2. **Requirements that evaporate.** A feature gets dropped, but its work item lingers forever, so nobody can tell what is actually left to build.

The ledger is only useful if it reflects reality at all times. That means updating it at the moment of the change, not at the end of the day.

## The three rules

1. **One item lives in exactly one place.** Completing an item means *removing* it from TODO and *appending* a row to COMPLETE with a date and an evidence pointer. Never leave a checked-off box in TODO.
2. **A new requirement during development is a new TODO item.** Do not fold it into an existing item — that hides scope growth. If the new requirement changes an item you are mid-way through, revise that item's text and say so in `memo.md`.
3. **A removed feature means a deleted work item.** Delete it, and record why in `memo.md` under 决策记录, so the deletion is not mistaken for forgotten work.

## Session start

1. Read `rule.md` — check the active red lines against whatever you are about to do. Empty list is a valid state; still read it.
2. Read `HANDOVER.md` — pick the top item in IN PROGRESS if one exists, else promote one TODO item and move it to IN PROGRESS.
3. Read `memo.md` 当前状态快照 and 踩坑记录 — this is where environment facts live that cost real time to rediscover.
4. State in one line what you picked and what you will do.

Promoting an item to IN PROGRESS matters: it is the mutual-exclusion marker for parallel sessions.

## Item completion

Work items follow the TDD ratchet in `docs/superpowers/specs/*-design.md` §8. Before you touch the ledger:

1. The new test was written first and observed failing.
2. `pytest -q` is green.
3. `python scripts/validate.py --all` is green (this is the single authority for quality gates — if it does not exist yet, say so rather than implying you ran it).
4. `memo.md` 测试日志 has the command, the real output, and the verdict.

Only then:

5. Delete the item from TODO / IN PROGRESS.
6. Append to COMPLETE: `| YYYY-MM-DD | W-NN | what was done | evidence pointer |`.
7. The evidence pointer must be something a person can open — a file path, a test name, a command. "Done" is not evidence.

If any of steps 1–4 failed, the item stays in IN PROGRESS. Do not mark work complete on an unverified claim.

## Session end

1. Update `memo.md` 当前状态快照: phase, what exists now, what to do next, open questions.
2. Append anything you learned about the environment that was not obvious from reading code — network reachability, CLI permission quirks, telemetry fields that lie. These cost minutes to hours to rediscover.
3. Note where you stopped mid-file, including the specific function or line, so resuming is not guesswork.
4. Leave exactly one item in IN PROGRESS if you stopped mid-flight; move it back to TODO if you finished it.

## Output shape

Keep the ledger diff small and factual. A typical completion entry:

```
| 2026-09-19 | W-14 | validate.py 十条质量闸门 + --all 全站扫描 | tests/test_validate.py::test_gate_<n> 全绿 |
```

And a removal:

```
TODO: delete W-22 (导出 PDF)
memo.md 决策记录: D-08 砍掉 PDF 导出 —— 纯静态 HTML 已满足离线需求，引入 wkhtmltopdf 会破坏"零外部依赖"约束
```

## What this skill is not

It is not a task-tracking system with assignments, sprints, or dependencies. If `openspec` is in use (it is, in this project — see `openspec/changes/`), OpenSpec owns *what the system should do* and this ledger owns *what is left to build*. Update both when both apply; do not let them contradict each other.
