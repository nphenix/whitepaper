# Arq 异步任务队列

基于 [Arq](https://arq-docs.helpmanual.io/) 和 Redis 的异步任务队列系统，提供高性能的任务执行和管理功能。

## 功能特性

- ✅ **异步任务执行** - 基于 asyncio 的高性能任务处理
- ✅ **任务重试机制** - 支持指数退避重试策略
- ✅ **优先级队列** - 支持多级任务优先级
- ✅ **健康检查** - 自动监控系统和任务健康状态
- ✅ **性能监控** - 内置 Prometheus 指标和统计
- ✅ **优雅关闭** - 支持信号处理和优雅关闭
- ✅ **分布式支持** - 支持多个 Worker 实例
- ✅ **任务追踪** - 完整的任务生命周期追踪

## 快速开始

### 1. 配置 Redis

确保 Redis 服务正在运行：

```bash
# 使用 Docker
docker run -d --name redis -p 6379:6379 redis:7-alpine

# 或使用本地安装
redis-server
```

### 2. 环境变量配置

在 `.env` 文件中添加 Redis 配置：

```env
# Redis 配置
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=1
REDIS_PASSWORD=

# Arq 配置
ARQ_QUEUE_NAME=whitepaper_tasks
ARQ_MAX_JOBS=100
ARQ_JOB_TIMEOUT=3600
```

### 3. 定义任务

```python
from src.infrastructure.tasks import task, TaskPriority

@task(
    name="process_document",
    description="Process uploaded document",
    timeout=300,
    max_retries=3,
    priority=TaskPriority.NORMAL
)
async def process_document(document_id: str, options: dict = None):
    """处理文档"""
    # 文档处理逻辑
    await asyncio.sleep(2)  # 模拟处理时间
    
    return {
        "document_id": document_id,
        "status": "processed",
        "processed_at": datetime.now().isoformat()
    }
```

或使用类继承：

```python
from src.infrastructure.tasks import BaseTask, TaskContext

class DocumentProcessingTask(BaseTask):
    def __init__(self):
        super().__init__(
            name="process_document_class",
            description="Process document using class",
            timeout=300,
            max_retries=3
        )
    
    async def execute(self, context: TaskContext, document_id: str, **kwargs):
        # 文档处理逻辑
        return {"document_id": document_id, "status": "processed"}
```

### 4. 注册任务

```python
from src.infrastructure.tasks import get_task_registry

# 注册任务
registry = get_task_registry()
registry.register_task(process_document)
registry.register_task(DocumentProcessingTask())
```

### 5. 启动 Worker

```bash
# 直接运行
python -m src.infrastructure.tasks.worker

# 或在代码中启动
from src.infrastructure.tasks import run_worker

async def main():
    await run_worker()

if __name__ == "__main__":
    asyncio.run(main())
```

### 6. 提交任务

```python
from src.infrastructure.tasks import task_client

async def submit_tasks():
    async with task_client() as client:
        # 提交单个任务
        task_id = await client.submit_task(
            "process_document",
            "doc_123",
            options={"format": "pdf"}
        )
        print(f"Task submitted: {task_id}")
        
        # 等待任务完成
        result = await client.get_task_result(task_id, wait=True, timeout=60)
        print(f"Task result: {result}")

# 运行
asyncio.run(submit_tasks())
```

## 高级用法

### 任务优先级

```python
# 提交高优先级任务
await client.submit_task(
    "urgent_task",
    priority=TaskPriority.HIGH,
    delay=0  # 立即执行
)

# 提交批量任务
await client.submit_task(
    "batch_task",
    priority=TaskPriority.BULK,
    delay=300  # 5分钟后执行
)
```

### 任务状态查询

```python
# 查询任务状态
status = await client.get_task_status(task_id)
print(f"Task status: {status['status']}")

# 查询队列信息
queue_info = await client.get_queue_info()
print(f"Queue length: {queue_info['queue_length']}")
```

### 监控和统计

```python
from src.infrastructure.tasks import get_monitor

# 启动监控
monitor = get_monitor()
await monitor.start()

# 获取统计信息
summary = monitor.get_summary()
print(f"Total tasks: {summary['tasks']['total']}")
print(f"Success rate: {summary['tasks']['success_rate']:.2%}")

# 获取 Prometheus 指标
metrics = await monitor.export_prometheus_metrics()
print(metrics)
```

## 配置选项

### 基础配置

| 选项 | 默认值 | 说明 |
|------|--------|------|
| `redis_host` | localhost | Redis 主机 |
| `redis_port` | 6379 | Redis 端口 |
| `redis_db` | 1 | Redis 数据库 |
| `redis_password` | None | Redis 密码 |
| `queue_name` | whitepaper_tasks | 队列名称 |
| `max_jobs` | 100 | 最大任务数 |
| `job_timeout` | 3600 | 任务超时时间（秒） |

### 重试配置

| 选项 | 默认值 | 说明 |
|------|--------|------|
| `max_retries` | 3 | 最大重试次数 |
| `retry_delay` | 60 | 重试延迟（秒） |
| `retry_backoff` | 2.0 | 退避倍数 |
| `max_retry_delay` | 3600 | 最大重试延迟（秒） |

### 监控配置

| 选项 | 默认值 | 说明 |
|------|--------|------|
| `monitoring_enabled` | true | 是否启用监控 |
| `metrics_interval` | 60 | 指标收集间隔（秒） |
| `prometheus_enabled` | false | 是否启用 Prometheus |
| `prometheus_port` | 9090 | Prometheus 端口 |

## 最佳实践

### 1. 任务设计

- **幂等性**：确保任务可以安全重试
- **原子性**：避免部分更新状态
- **错误处理**：提供清晰的错误信息
- **超时设置**：设置合理的超时时间

### 2. 资源管理

```python
class ResourceIntensiveTask(BaseTask):
    async def execute(self, context: TaskContext):
        # 使用上下文管理器管理资源
        async with resource_manager() as resource:
            # 执行任务
            result = await process_with_resource(resource)
            return result
```

### 3. 批量处理

```python
@task
async def batch_process_items(item_ids: List[str]):
    """批量处理项目"""
    # 分批处理，避免内存溢出
    batch_size = 100
    results = []
    
    for i in range(0, len(item_ids), batch_size):
        batch = item_ids[i:i + batch_size]
        batch_results = await process_batch(batch)
        results.extend(batch_results)
    
    return results
```

### 4. 监控集成

```python
# 在任务中记录指标
@task
async def monitored_task(data):
    start_time = time.time()
    
    try:
        result = await process_data(data)
        
        # 记录成功指标
        monitor = get_monitor()
        monitor.record_task_success("monitored_task", time.time() - start_time)
        
        return result
        
    except Exception as e:
        # 记录失败指标
        monitor = get_monitor()
        monitor.record_task_failure("monitored_task")
        raise
```

## 故障排查

### 常见问题

1. **Redis 连接失败**
   ```bash
   # 检查 Redis 是否运行
   redis-cli ping
   
   # 检查网络连接
   telnet localhost 6379
   ```

2. **任务堆积**
   ```python
   # 检查队列状态
   queue_info = await client.get_queue_info()
   print(f"Queue length: {queue_info['queue_length']}")
   
   # 增加并发数
   settings.queue.max_concurrent_jobs = 20
   ```

3. **任务超时**
   ```python
   # 增加超时时间
   await client.submit_task("slow_task", timeout=1800)  # 30分钟
   
   # 或检查任务性能
   metrics = monitor.get_task_metrics("slow_task")
   print(f"Avg duration: {metrics['avg_duration']}s")
   ```

### 日志配置

```python
import logging

# 启用详细日志
logging.getLogger("arq.worker").setLevel(logging.DEBUG)
logging.getLogger("src.infrastructure.tasks").setLevel(logging.DEBUG)
```

## 性能优化

### 1. 连接池配置

```python
# 增加 Redis 连接数
settings.redis_max_connections = 50
settings.redis_socket_timeout = 10
```

### 2. 任务批处理

```python
# 批量提交任务
task_ids = []
for item in items:
    task_id = await client.submit_task("process_item", item.id)
    task_ids.append(task_id)

# 批量等待结果
results = await asyncio.gather(*[
    client.get_task_result(task_id, wait=True)
    for task_id in task_ids
])
```

### 3. 内存管理

```python
# 定期清理过期结果
async def cleanup_task():
    async with task_client() as client:
        while True:
            cleaned = await client.cleanup_expired_results()
            logger.info(f"Cleaned {cleaned} expired results")
            await asyncio.sleep(3600)  # 每小时清理一次
```

## API 参考

详细的 API 文档请参考：

- [WorkerSettings](worker.py) - Worker 配置
- [TaskClient](client.py) - 任务客户端
- [TaskMonitor](monitoring.py) - 监控器
- [BaseTask](tasks.py) - 任务基类

## 许可证

MIT License