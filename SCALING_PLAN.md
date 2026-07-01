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

## AI 链路扩容（Deepseek 高并发）

用户系统上线后，AI 是最贵、也最容易过载的一条链路。问题**不在"共用一个 Deepseek client"**（`httpx.AsyncClient` 本身就是连接池，共享是正确做法），而在两点：并发到底卡在哪一层、以及多实例下的全局协调。

### 4 层瓶颈（实际上限 = 最低的那层）

```
请求 → [1] 单进程单核 CPU（JSON 序列化 / SSE 流 / tool loop 都挤一个核）
        → [2] httpx 连接池（默认 max_connections=100 / keepalive=20，当前未显式设置）
          → [3] PriorityGate（AI_MAX_CONCURRENCY，默认 8）
            → [4] Deepseek 账号 RPM/TPM + 上游延迟  ← 真正的天花板，不可控
```

隐蔽耦合：[3] 的 chat tool-call 要查 PG，和 chart/monitor **抢同一个 asyncpg pool** ——
AI 高并发会吃光 PG 池，反过来拖垮整个 app（连看图都卡）。

### 致命问题：in-process gate 多实例失效

`ai/priority_gate.py` 的 `PriorityGate` 是**进程内**的。水平扩容后，和 asyncpg pool 同构地失控：

```
3 实例 × AI_MAX_CONCURRENCY=8 = 全局 24 并发  ← 失去全局上限，可能压垮 Deepseek/PG
优先级只在单实例内有效            ← 实例A的 premium 不会优先于实例B的 anon
```

与「N 实例 × pool=40」是完全相同的问题：局部控制在多实例下失控。

### 提高 AI_MAX_CONCURRENCY 有用吗

**它是安全阀，不是吞吐放大器。** Deepseek 的实际吞吐不会因为放更多请求进去而变大；调高只是把"等待"从本地队列挪到下游（429 / httpx 池 / PG 池 / CPU）。

- 撞到最低瓶颈**之前**：调高 → 更多用户同时不排队 ✅
- 撞到之后：调高 → 更多 in-flight → 更多内存 + 更多 429（retry backoff 把延迟转嫁用户）+ 更长尾延迟 ❌
- 正确做法：测 Deepseek 调用 p50/p95 延迟 + 账号 RPM/TPM，把 gate 设在最低瓶颈略下方，并同步调大 httpx `Limits`。

### 分层解决方案

**短期（单实例即可）**
- gate 上限对齐真实瓶颈；同步设置 httpx `Limits(max_connections=...)`。
- 加**背压**：等待队列过深时，base/anon 直接返回「系统繁忙，稍后再试」，premium 仍放行——而非无限等待。给 `acquire` 加超时 + 最大队列深度。

**中期（多实例必须，复用规划中的 Redis）**
- gate 换成 **Redis 分布式限流**（distributed semaphore / token bucket）：全局并发上限 + 跨实例优先级。与 WebSocket Pub/Sub 共用同一套 Redis 基础设施。
- **多 Deepseek API key 轮询池**，聚合提高上游吞吐上限。
- screener / report 等**非流式**调用走任务队列（Arq / Celery + Redis），与 chat 的流式路径解耦；chat 保持 request-scoped。

**长期**
- 独立 **AI gateway 服务**：所有实例调它，集中并发控制 + 优先级 + 限流 + 多 provider fallback + 缓存。
- AI 的 tool-call PG 负载隔离（读副本 / 独立 pool），避免 AI 高峰拖垮主 app。
- 缓存：相同 NL screener query → 相同 SQL，可缓存。

### AI 链路分阶段（沿用相同阶段划分）

| 阶段 | 用户规模 | 行动 | 优先级 |
|------|---------|------|-------|
| 现在 | 0–500 | 进程内 `PriorityGate`（premium > base > anon）+ `AI_MAX_CONCURRENCY=8`（已完成）| ✅ Done |
| 上线前 | 500–2000 | gate 上限对齐瓶颈 + 显式设 httpx `Limits` + 背压（队列满即返回繁忙）| 🔴 必须 |
| 规模化 | 2000+ | Redis 分布式 gate（全局限流 + 跨实例优先级）+ 多 API key 轮询 + 非流式走任务队列 | 🟡 中期 |
| 大规模 | 10000+ | 独立 AI gateway（限流 / fallback / 缓存）+ tool-call PG 读写分离 | 🟢 长期 |

### Redis 分布式 gate 快速实现参考

中期把进程内 gate 换成 Redis 协调（思路）：

```
# 全局并发上限 + 跨实例优先级
acquire(priority):
    if INCR ai:active <= MAX:                       # 原子占用一个全局槽
        return
    DECR ai:active
    ZADD ai:waiters score={priority}:{ts}           # 入队，premium 分数最低（最先出队）
    等待 Pub/Sub 唤醒：当 active < MAX 且自己是 ZSET 最小分 → 占槽并出队

release():
    DECR ai:active
    PUBLISH ai:slot_freed                           # 唤醒等待者重试，避免空转轮询
```

要点：`ai:active` 计数器是**全局**上限（替代 N×cap）；ZSET 分数 = 优先级在前、时间戳在后 → 跨实例严格优先 + 同级 FIFO；release 用 Pub/Sub 唤醒等待者。

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
