# <主题>（Runbook v1）

> 目的：让这项操作可复现、可验收、可回滚。  
> 适用范围：`<host_id>` / `<service_id>` / `<环境>`

## 1. 背景与目标

- 背景：
- 当前问题：
- 目标：
  1.
  2.
  3.

## 2. 范围

- Host：
- Service：
- 会改动的文件：
- 会影响的端口 / 进程 / 挂载 / 数据目录：

## 3. 前置条件

- 
- 
- 

## 4. 风险等级

- 风险等级：`L0 | L1 | L2 | L3 | L4`
- 风险说明：
- 是否需要明确审批：

## 5. 实施步骤

### Step 0：预检查

```bash
# 在这里写预检查命令
```

验收要点：

- 
- 

### Step 1：执行变更

```bash
# 在这里写核心变更命令
```

验收要点：

- 
- 

### Step 2：重载 / 重启 / 生效

```bash
# 在这里写 reload / restart / rollout 命令
```

验收要点：

- 
- 

## 6. 验收方案

```bash
# 在这里写统一验收命令
```

验收标准：

- 
- 

## 7. 回滚方案

```bash
# 在这里写回滚命令
```

回滚后验证：

- 
- 

## 8. 证据位置

- `.artifacts/agent_runs/<run_id>/index.md`
- 关键日志：
  - 
  - 

## 9. 变更后需要同步更新的内容

- `inventory/hosts/<host_id>.yaml`
- `inventory/services/<service_id>.yaml`
- `inventory/router.yaml`（如需要）
- 其他：

---

## Run Record（可选：直接追加在 runbook 底部）

- Run ID：
- 时间：
- 目标：
- 做了什么：
  - 
  - 
- 改了什么：
  - 
  - 
- 验收结果：
- Artifacts：
