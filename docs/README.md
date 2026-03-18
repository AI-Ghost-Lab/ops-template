# Docs（Runbooks / Run Records / Handoff / Design）

这里放“能让别人继续做”的文档，而不是只记录结果。

---

## 建议放什么

- **runbook**：标准步骤、风险、验收、回滚
- **run-record**：某一次真实执行的记录
- **handoff**：交接背景、当前状态、下一步
- **design**：设计决策、权衡和替代方案

---

## 现成模版

- `templates/runbook.template.md`
- `templates/run-record.template.md`
- `templates/handoff.template.md`
- `templates/design.template.md`

---

## 建议命名

- `001.<topic>-runbook-v1.md`
- `002.<topic>-handoff-v1.md`
- `003.<topic>-design-v1.md`
- `004.<topic>-run-record-<run_id>.md`

> 你也可以把 run-record 直接追加到对应 runbook 末尾，不一定要拆成单独文件。

---

## 写文档时的原则

- 写清楚 **目标 / 范围 / 风险 / 步骤 / 验收 / 回滚**
- 文档写结论和关键步骤，原始日志放 `.artifacts/`
- 不要把 secrets 放进文档
- 不要写“只对当时那台机器成立”的隐式前提而不标注
