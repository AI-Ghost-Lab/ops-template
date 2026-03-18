# hosts/（可落地配置）

这里放**真正可部署**的配置文件，比如：

- `systemd` unit / drop-in
- `nginx` / `caddy` / `traefik` 配置
- `docker-compose.yml`
- 自定义启动脚本
- 某台机器的 README

建议结构：

```text
hosts/
  <host_id>/
    README.md
    systemd/
    nginx/
    docker-compose/
    scripts/
```

注意：

- 不要把 secrets 直接放进这里
- 可以把“可公开的模板配置”放这里，把敏感值放环境变量或外部 secret 管理
- 可先从 `hosts/_templates/` 复制样板
