# Inventory Spec v0.1（世界模型规范）

目标：把“机器 / 服务 / 依赖 / 入口 / 风险”变成结构化信息，让 Agent 和人都能更快定位上下文。

原则：

- **Inventory 是权威来源**
- **Runbook 解释怎么做，Inventory 描述当前世界**
- **Wiki 是人类视图，尽量从 Inventory 派生**
- **Secrets 不入库**

---

## 1) Host 文件规范（`inventory/hosts/*.yaml`）

### 必填字段

- `host_id`
- `display_name`
- `environment`
- `access.ssh`
- `os`
- `roles`
- `network`
- `storage.mounts`
- `services`
- `risk_notes`

### 推荐补充字段

- `owner`
- `location`
- `dependencies`
- `secrets_refs`
- `last_verified`
- `links`

---

## 2) Service 文件规范（`inventory/services/*.yaml`）

### 必填字段

- `service_id`
- `type`
- `description`
- `runs_on`
- `interfaces`
- `data`
- `dependencies`
- `runbooks`
- `risk_level`

---

## 3) Router 规范（`inventory/router.yaml`）

每条规则建议包含：

- `id`
- `match.keywords`
- `match.negative_keywords`
- `scope.hosts`
- `scope.services`
- `recommended_runbooks`
- `prerequisites`
- `risk_level`
- `notes`

---

## 4) 执行后更新规则

当操作影响以下任一项时，必须同步更新 Inventory：

- SSH / 域名 / 入口
- 监听端口 / URL / 健康检查
- 数据目录 / 挂载点
- 服务状态 / 部署方式 / 依赖关系

---

## 5) Secrets 规则

允许写：

- secret 引用名
- 密码管理器条目
- 环境变量名
- 路径占位

禁止写：

- 明文密码
- 私钥
- Token
- Session 文件
