# MinerU API集成修复计划

## 问题诊断
1. **API接口变更**: 从单个任务接口升级到批量接口
2. **认证机制**: 需要使用.env中的MINERU_API_KEY进行Bearer Token认证
3. **参数结构**: 新增model_version等参数，支持pipeline和vlm两种模型
4. **响应格式**: 批量接口返回batch_id而非task_id，需要使用批量查询接口

## 实施步骤

### 第一阶段：API适配层重构（使用.env配置）
1. **创建MinerU API客户端类**
   - 从.env读取MINERU_API_KEY、MINERU_API_URL等配置
   - 封装认证逻辑（Bearer Token）
   - 实现单个和批量任务创建接口
   - 实现任务状态查询接口
   - 添加错误处理和重试机制

2. **更新请求参数结构**
   - 添加model_version参数（默认pipeline）
   - 支持language、enable_formula、enable_table等可选参数
   - 保持向后兼容性

3. **更新响应处理逻辑**
   - 批量接口返回batch_id的处理
   - 实现批量结果查询
   - 保持与现有文档处理流程的兼容

### 第二阶段：测试脚本更新
1. **修改test_mineru_loaders.py**
   - 更新API调用方式，使用批量接口
   - 从.env读取API配置
   - 更新错误处理逻辑
   - 保持测试覆盖率

2. **添加配置管理**
   - 使用现有的.env配置（MINERU_API_KEY、MINERU_API_URL等）
   - 支持环境变量和配置文件两种配置方式
   - 添加API密钥管理

### 第三阶段：功能增强
1. **批量处理优化**
   - 实现目录级批量提交
   - 添加进度跟踪
   - 优化错误恢复机制

2. **结果处理改进**
   - 支持zip文件下载和解压
   - 完善extracted_dir验证
   - 添加结果缓存机制

### 第四阶段：文档和测试
1. **更新文档**
   - API使用说明
   - 配置指南
   - 故障排除指南

2. **完善测试**
   - 单元测试覆盖
   - 集成测试验证
   - 错误场景测试

## 技术实现细节

### API客户端设计
```python
class MinerUAPIClient:
    def __init__(self, config: MinerUConfig):
        self.config = config
        self.token = config.mineru_api_key
        self.base_url = config.mineru_api_url
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        })
    
    def create_single_task(self, file_url: str, **kwargs) -> str:
        # 实现单个任务创建
    
    def create_batch_tasks(self, file_urls: list, **kwargs) -> str:
        # 实现批量任务创建
    
    def get_task_status(self, task_id: str) -> dict:
        # 实现任务状态查询
    
    def get_batch_status(self, batch_id: str) -> dict:
        # 实现批量状态查询
```

### 配置管理（使用.env）
```python
class MinerUConfig:
    def __init__(self):
        self.api_key = os.getenv("MINERU_API_KEY")
        self.api_url = os.getenv("MINERU_API_URL", "https://mineru.net/api/v4")
        self.model_version = os.getenv("MINERU_MODEL_VERSION", "pipeline")
        self.timeout = int(os.getenv("MINERU_TIMEOUT", "300"))
        self.max_retries = int(os.getenv("MINERU_MAX_RETRIES", "3"))
```

### 批量处理流程
```python
async def process_batch_files(file_paths: list) -> dict:
    # 1. 创建批量任务
    batch_id = await client.create_batch_tasks(file_urls)
    
    # 2. 轮询任务状态
    while not all_completed:
        status = await client.get_batch_status(batch_id)
        # 3. 处理完成的文件
        # 4. 下载zip文件并解压
        # 5. 验证extracted_dir
```

## 风险评估与缓解
1. **API变更风险**: 保持向后兼容，支持新旧两种模式
2. **认证失败**: 添加详细的错误提示和重试机制
3. **性能影响**: 批量处理优化，避免重复请求
4. **向后兼容**: 保持现有接口不变，仅内部实现更新

## 验收标准
1. ✅ T026A-MinerU测试通过
2. ✅ T026-MinerU测试通过  
3. ✅ T027测试通过
4. ✅ 批量处理功能正常
5. ✅ 错误处理完善
6. ✅ 文档完整
7. ✅ 使用.env配置文件中的MINERU_API_KEY
8. ✅ 支持批量接口和单个接口两种模式