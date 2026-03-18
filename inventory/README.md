# Inventory（世界模型）

这里是仓库的 **Single Source of Truth**。

核心目标不是“堆更多文档”，而是让你或 Agent 能快速回答：

- 这项任务落在哪台机器？
- 涉及哪个服务？
- 应该参考哪篇 runbook？
- 风险和依赖是什么？

---

## 结构

- `hosts/`：每台机器一份 YAML
- `services/`：每个服务一份 YAML
- `router.yaml`：一句话目标 → 推荐上下文 / runbook

---

## 建议维护方式

1. 新增机器：复制 `hosts/_template.host.yaml`
2. 新增服务：复制 `services/_template.service.yaml`
3. 新增任务类型：更新 `router.yaml`
4. 每次执行后：同步更新 host / service 的状态、路径、端口和 `last_verified`

详细规范见：`SPEC.md`
