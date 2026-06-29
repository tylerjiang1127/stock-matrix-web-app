# Production Scaling Plan

## Current Architecture Limits

Single backend process with asyncpg pool:

```
单个后端进程
  └─ asyncpg pool: max_size=40
       └─ PG: max_connections=200

理论并发：
  40 connections ÷ ~3 DB queries/request = ~13 requests in parallel
  ~200ms avg query time → ~65 requests/second throughput
```

早期用户量够用，但水平扩容时会出问题。

---

## 水平扩容的致命问题

多实例部署时连接数直接炸：

```
3 实例 × max_size=40 = 120 connections  ← 安全
5 实例 × max_size=40 = 200 connections  ← 到 PG 上限，崩溃
10 实例 × max_size=40 = 400 connections ← 超限，全部报 too many clients
```

---

## 三个必须解决的问题

### 1. PgBouncer（上线前必须做）

在 app 和 PG 之间加连接代理：

```
多个后端实例 → PgBouncer (transaction mode) → PG
  实例1: pool 40             ↓ 复用            max_connections=200
  实例2: pool 40      → 实际只占 ~20 个 PG 连接
  实例3: pool 40
```

Transaction pooling 模式：每个 DB 查询执行完就把 PG 连接还回去，500 个 app 连接可以映射到 50 个 PG 连接。

**实现成本极低**：docker-compose 加一个 pgbouncer container，backend 连接地址指向它，其他代码完全不用改。

### 2. yfinance 集中化（中期必须换）

现在的问题：
- yfinance 是非官方 API，无 SLA，Yahoo 随时可以封禁
- 多实例时每个实例独立拉数据：10 实例 × 5 支股票 × 4次/min = 200 yfinance请求/分钟

**正确做法**：
- 集中一个 worker 进程拉 live quotes，写入 Redis
- 所有后端实例从 Redis 读，不直接调 yfinance
- 或中期换 Polygon.io / Alpaca 等有正式 SLA 的数据源

### 3. WebSocket 跨实例广播

现在 WebSocket 连接绑定在具体实例上，多实例时：
- 用户连接到实例 A，live quote 更新在实例 B → 用户收不到推送

**解决方案**：Redis Pub/Sub 做跨实例广播，每个实例订阅 Redis channel，收到消息后推给本实例上的 WebSocket 连接。

---

## 分阶段行动计划

| 阶段 | 用户规模 | 行动 | 优先级 |
|------|---------|------|-------|
| 现在 | 0–500 | asyncpg max_size=40，max_inactive=60s（已完成）| ✅ Done |
| 上线前 | 500–2000 | 加 PgBouncer，PG max_connections 提到 500 | 🔴 必须 |
| 规模化 | 2000+ | Redis 集中 live quotes + WebSocket Pub/Sub + 多实例 | 🟡 中期 |
| 大规模 | 10000+ | 换商业数据源，读写分离 PG replica，CDN 静态资源 | 🟢 长期 |

---

## PgBouncer 快速实现参考

`docker-compose.yml` 加：

```yaml
pgbouncer:
  image: bitnami/pgbouncer:latest
  environment:
    POSTGRESQL_HOST: postgres
    POSTGRESQL_PORT: 5432
    POSTGRESQL_DATABASE: stockmatrix
    POSTGRESQL_USERNAME: ${POSTGRES_USER}
    POSTGRESQL_PASSWORD: ${POSTGRES_PASSWORD}
    PGBOUNCER_POOL_MODE: transaction
    PGBOUNCER_MAX_CLIENT_CONN: 1000
    PGBOUNCER_DEFAULT_POOL_SIZE: 50
  ports:
    - "5433:5432"
```

`backend/.env` 改为连接 pgbouncer 端口（5433），代码零改动。

---

## 当前已有的缓解措施

- asyncpg pool `max_inactive_connection_lifetime=60`：idle 连接 60s 后自动回收
- 两阶段 chart 加载：Phase 1 只拉 1 年数据，减少单次查询时间
- 前端并行请求：chart + live-quote 同时发，减少用户等待时间
