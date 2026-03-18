# gxd_subagent_shim（重构版）

这是对原始 `subagent_shim.py` 的“拆分 + 风险隔离 + 可扩展”重构版本（仍然 **只依赖 Python 标准库**）。

## 兼容性

安装后通过命令行入口调用：

```bash
gxd-subagent-shim create "<PROMPT>" --backend=codex
gxd-subagent-shim resume "<PROMPT>" <thread_id> --backend=codex
```

usage:

```text
gxd_subagent_shim (create|resume) <prompt> [thread_id] [--backend=...] [--run-id=...]
```

默认行为保持：

- **stdout/stderr 原样透传**（codex JSONL 事件流会裁剪为关键信息）。
- 审计/产物写入是 **best-effort**：即使写入失败也不会阻断成功的 backend 调用。

## 安装

开发/本地调试建议使用 editable 安装：

```bash
python -m pip install -e .
# 或
pip install -e .
```

## 目录结构

```text
subagent_shim/
  pyproject.toml
  README.md
  MANIFEST.in
  scripts/
    release_zip.py            # 一键清理中间产物 + 导出源码 zip
  gxd_subagent_shim/
    cli.py                    # CLI 解析 + 主流程编排
    config.py                 # 环境变量/默认值/功能开关
    backend.py                # codex/claude 执行与 stdout 透传
    util/                     # 时间、git、锁、hash 等
    io/                       # JSON 提取/解析、thread_id/model/output 提取
    validation/               # 输入/输出校验（默认宽松，严格模式可开）
    postprocess/              # 输出精简（可选，失败自动回退）
    artifacts/                # 审计落盘（best-effort + staging）
  tests/
    test_json_extract.py
    test_run_id.py
    test_compact.py
```

## 功能开关（环境变量）

- `SUBAGENT_BACKEND`：默认 backend（`codex` 或 `claude`）。
- `SUBAGENT_ARTIFACTS_ROOT`：审计根目录，默认 `.artifacts/agent_runs`。
- `SUBAGENT_SAVE_RAW_IO`：是否保存 backend 的原始 stdout/stderr（默认 `1`）。
- `SUBAGENT_LEGACY_LOG`：是否写 `subagent.log`（默认 `1`）。

### 校验（可选）

- `SUBAGENT_VALIDATE_INPUT`：`0/1`，开启后会对输入 prompt 做更严格校验；失败会返回非 0 并在 stderr 输出原因。
- `SUBAGENT_VALIDATE_OUTPUT`：`0/1`，开启后会对 backend JSON 输出做校验（如必须能解析出 `thread_id`）。

### 输出精简（可选）

- `SUBAGENT_STDOUT_MODE`：`raw|compact`，默认 `raw`。
  - `raw`：完全透传 backend stdout。
  - `compact`：尝试精简 stdout（失败自动回退到 raw）。
- `SUBAGENT_COMPACT_PROFILE`：`auto|codex|claude|copilot`，默认 `auto`。

> 注意：即使 `compact`，审计仍会保存 raw stdout/stderr（若 `SUBAGENT_SAVE_RAW_IO=1`）。

## 运行测试

```bash
python -m unittest discover -s tests -p 'test_*.py' -q
```

## 发布与打包

### 版本号

`pyproject.toml` 里的 `[project].version` 建议遵循 PEP 440，例如 `2`、`2.0`、`2.0.0` 都是有效版本号；通常采用 `major.minor.patch`（三段）更便于管理与沟通。

### 构建 wheel/sdist（发布到 PyPI）

```bash
python -m pip install -U build
python -m build
ls dist/
```

### 一键清理中间产物并导出源码 zip

默认输出：`dist/<name>-<version>.zip`（从 `pyproject.toml` 读取）。

```bash
python scripts/release_zip.py --include-scripts
```

常用参数：

- `--include-tests`：将 `tests/` 一并打进 zip（运行时不需要）
- `--no-clean`：跳过清理
- `--keep-dist`：清理时保留已有 `dist/`
- `-o dist/custom.zip`：自定义输出路径

从 zip 安装（可选）：

```bash
unzip dist/<name>-<version>.zip
cd <name>-<version>
python -m pip install .
```
