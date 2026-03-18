> 本文件是给 **AI Agent** 和 **人类操作者** 的总入口。  
> 建议阅读顺序：`OPS_RULES.md` → `inventory/` → `docs/` → `hosts/` → `.artifacts/`

全局入口：

- 执行协议：[`OPS_RULES.md`](OPS_RULES.md)
- Inventory 说明：[`inventory/README.md`](inventory/README.md)
- Inventory 规范：[`inventory/SPEC.md`](inventory/SPEC.md)
- Host 模版：[`inventory/hosts/_template.host.yaml`](inventory/hosts/_template.host.yaml)
- Service 模版：[`inventory/services/_template.service.yaml`](inventory/services/_template.service.yaml)
- 路由表：[`inventory/router.yaml`](inventory/router.yaml)
- 文档入口：[`docs/README.md`](docs/README.md)
- 可落地配置入口：[`hosts/README.md`](hosts/README.md)
- 证据链入口：[`.artifacts/README.md`](.artifacts/README.md)

---

## Agent 工作方式（建议默认）

1. 先用 `inventory/router.yaml` 做路由。
2. 再根据 `inventory/hosts/*.yaml` 和 `inventory/services/*.yaml` 建立上下文。
3. 执行前必须输出 **PLAN**，说明：
   - 目标
   - 范围
   - 风险等级
   - 变更清单
   - 回滚方案
   - 验收方案
   - 证据输出位置
4. 获得批准后再执行。
5. 执行完成后必须：
   - 更新 runbook / run-record
   - 更新 inventory
   - 保存 artifacts

---

## 新仓库初始化建议

当这是一个刚创建的模版仓库时，优先完成以下动作：

1. 新增第一台主机：复制 `inventory/hosts/_template.host.yaml`
2. 新增第一个服务：复制 `inventory/services/_template.service.yaml`
3. 新增第一条路由：编辑 `inventory/router.yaml`
4. 新增第一篇 runbook：从 `docs/templates/runbook.template.md` 复制
5. 放入第一份可部署配置：放到 `hosts/<host_id>/`

---

## 红线

- 不要把私钥、Token、密码、会话文件直接入库。
- 不要把大体量日志直接写进文档正文。
- 不要只改文档不改 inventory。
- 不要在没有 PLAN / 验收 / 回滚说明的情况下做高风险变更。
