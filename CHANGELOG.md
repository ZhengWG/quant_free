# 更新日志

## 2025-01-03

### 重大变更

- ✅ **后端迁移到Python**: 从Node.js/TypeScript迁移到Python/FastAPI
  - 使用FastAPI框架，自动生成API文档
  - 使用SQLAlchemy异步ORM
  - 使用Pydantic进行数据验证
  - 更好的量化交易生态支持

- ✅ **目录结构优化**: 
  - 删除旧的 `server/` (Node.js实现)
  - 将 `server_py/` 重命名为 `server/`
  - 统一项目结构

### 技术栈

**后端**:
- Python 3.10+
- FastAPI
- SQLAlchemy (异步)
- Pydantic
- Loguru

**前端**:
- TypeScript
- VSCode Extension API
- React (计划中)

### 功能

- ✅ 实时行情查询
- ✅ AI策略生成 (DeepSeek/OpenAI)
- ✅ 交易订单管理
- ✅ 持仓查询
- ✅ 账户信息查询
- ✅ WebSocket实时推送
- ✅ 自动API文档 (Swagger UI)

### 测试

- ✅ 所有API端点测试通过
- ✅ 数据库操作正常
- ✅ WebSocket连接正常

