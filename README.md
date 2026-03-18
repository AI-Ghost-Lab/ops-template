# Ops Repo Template（运维仓库模版）

这是一个**已经清理过实例信息**的运维仓库模版，适合拿来做：

- 多机器 / 多服务的运维资料库
- AI Agent 可读、可执行、可追溯的操作仓库
- runbook / handoff / design / inventory 的统一入口

这份模版刻意**不包含**以下内容：

- 真实主机、IP、域名、用户名、端口和路径
- 真实服务清单、现成部署配置、历史 run-record
- 原仓库的 Git 历史、执行日志、系统垃圾文件和压缩包噪音
- 任何 secrets / token / 私钥 / 明文密码

---

## 目录结构

- `AGENTS.md`：给 AI Agent 和人类的总入口
- `OPS_RULES.md`：执行协议（Plan → Approve → Execute → Verify → Document）
- `inventory/`：结构化世界模型（主机 / 服务 / 路由）
- `docs/`：runbook / run-record / handoff / design 模版
- `hosts/`：可落地配置目录与配置样板
- `wiki/`：人类视图
- `.artifacts/`：原始证据链目录（默认仅保留结构，不提交大日志）

---

## 快速开始

1. 先复制并填写：
   - `inventory/hosts/_template.host.yaml`
   - `inventory/services/_template.service.yaml`
2. 在 `inventory/router.yaml` 里补你的任务路由规则。
3. 从 `docs/templates/` 复制一份文档，开始写第一篇 runbook / handoff / design。
4. 把真正可部署的配置放到 `hosts/<host_id>/`。
5. 每次执行后，把证据落到 `.artifacts/agent_runs/<run_id>/`。

---

## 使用约定

- **Inventory 是权威来源（SSOT）**，机器和服务状态优先写到 `inventory/`。
- **文档写结论与步骤，原始证据放 `.artifacts/`**，避免把大日志直接塞进 Markdown。
- **严禁入库明文 secrets**，只允许写引用或占位符。
- **默认 `.gitignore` 会忽略 `.artifacts/agent_runs/`**，如果你想把证据也纳入版本控制，可以按需修改。

---

## 建议你第一步就做的事

- 把仓库名改成你自己的名字
- 添加第一台机器
- 添加第一个服务
- 写第一篇 runbook
- 删除你不需要的样板文件
