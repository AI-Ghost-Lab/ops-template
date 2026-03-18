# gxd-subagent-shim quick reference (Local-first)

本技能 **内置** 了一份可追溯的 subagent_shim，实现位于 `assets/`。为避免版本漂移、PATH 污染、以及“误调用全局 shim”，主控 **必须优先使用本技能目录里的 shim**。

## 1) ✅ 永远优先：技能自带 wrapper

路径：

- `assets/bin/gxd-subagent-shim`（会把 `PYTHONPATH` 指向 `assets/gxd-subagent-shim-0.2.3/` 然后执行 `python -m gxd_subagent_shim`）

用法：

```bash
<SKILL_ROOT>/assets/bin/gxd-subagent-shim create "<JSON>" --backend codex --run-id <RUN_ID> --task-id <TASK_ID> --step-id S1
<SKILL_ROOT>/assets/bin/gxd-subagent-shim resume "<JSON>" <thread_id> --backend codex --run-id <RUN_ID> --task-id <TASK_ID> --step-id S1
```

注意：

- `SKILL_ROOT` = `SKILL.md` 所在目录。
- 路径可能包含空格，务必整体引用。
- 传入 shim 的第一个参数必须是 **纯 JSON 字符串**（不要拼接其它文本）。

## 2) ✅ 兜底：直接跑技能内置源码（wrapper 不可执行时）

```bash
PYTHONPATH="<SKILL_ROOT>/assets/gxd-subagent-shim-0.2.3" \
  python -m gxd_subagent_shim create "<JSON>" --backend codex --run-id <RUN_ID> --task-id <TASK_ID> --step-id S1

PYTHONPATH="<SKILL_ROOT>/assets/gxd-subagent-shim-0.2.3" \
  python -m gxd_subagent_shim resume "<JSON>" <thread_id> --backend codex --run-id <RUN_ID> --task-id <TASK_ID> --step-id S1
```

## 3) ❌ 不推荐：PATH 上的全局 gxd-subagent-shim

只有在用户明确要求、或技能内置 shim 不可用时，才允许使用：

```bash
gxd-subagent-shim create "<JSON>" --backend codex --run-id <RUN_ID> --task-id <TASK_ID> --step-id S1
gxd-subagent-shim resume "<JSON>" <thread_id> --backend codex --run-id <RUN_ID> --task-id <TASK_ID> --step-id S1
```

## 4) 长任务注意事项（避免“假超时”）

- shim 本身可能长时间没有任何输出，这是正常的（取决于 backend 的输出）。
- 主控应遵守：**连续 ≥20 分钟 stdout+stderr 都无新增输出** 才允许判定超时。
- 若 runner 支持命令超时参数，建议设置为 ≥3600 秒。

## 5) 常用环境变量

- `SUBAGENT_BACKEND`（默认 backend）
- `SUBAGENT_ARTIFACTS_ROOT`（默认 `.artifacts/agent_runs`）
- `SUBAGENT_SAVE_RAW_IO`（默认 `1`）
- `SUBAGENT_STDOUT_MODE`（`raw|compact`，默认 `raw`）
