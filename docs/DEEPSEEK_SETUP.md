# DeepSeek API 配置指南

## 为什么选择 DeepSeek？

- ✅ **性价比高**：价格比OpenAI GPT-4便宜很多
- ✅ **国内访问稳定**：服务器在国内，访问速度快
- ✅ **性能优秀**：DeepSeek-V3模型性能接近GPT-4
- ✅ **API兼容**：完全兼容OpenAI API格式

## 获取 API Key

1. 访问 [DeepSeek 平台](https://platform.deepseek.com/)
2. 注册/登录账户
3. 进入控制台，创建API Key
4. 复制API Key备用

## 配置步骤

### 1. 设置环境变量

在 `server/.env` 文件中配置：

```bash
# 选择AI服务提供商
AI_PROVIDER=deepseek

# DeepSeek API配置
DEEPSEEK_API_KEY=sk-your-api-key-here
DEEPSEEK_MODEL=deepseek-chat
```

### 2. 可用的模型

- `deepseek-chat`：标准对话模型（推荐）
- `deepseek-reasoner`：思考模式，适合复杂分析

### 3. 验证配置

启动后端服务后，尝试生成策略：

```bash
cd server
npm run dev
```

在VSCode插件中测试策略生成功能，如果配置正确，应该能正常生成策略。

## API 使用说明

DeepSeek API 完全兼容 OpenAI API，所以代码中可以直接使用 OpenAI SDK：

```typescript
import OpenAI from 'openai';

const client = new OpenAI({
    apiKey: process.env.DEEPSEEK_API_KEY,
    baseURL: 'https://api.deepseek.com'  // DeepSeek的API地址
});
```

## 费用说明

DeepSeek 的定价非常实惠：
- 输入：约 ¥0.14 / 1M tokens
- 输出：约 ¥0.56 / 1M tokens

相比 OpenAI GPT-4 便宜很多，非常适合策略生成这种场景。

## 故障排查

### 问题1：API Key无效

- 检查API Key是否正确复制（不要有多余空格）
- 确认API Key是否已激活
- 查看服务器日志：`server/logs/error.log`

### 问题2：网络连接失败

- 检查网络连接
- 确认可以访问 `https://api.deepseek.com`
- 如果使用代理，检查代理配置

### 问题3：策略生成失败

- 检查环境变量是否正确设置
- 查看后端服务日志
- 确认 `AI_PROVIDER=deepseek` 已设置

## 参考链接

- [DeepSeek 官方文档](https://api-docs.deepseek.com/)
- [DeepSeek 平台](https://platform.deepseek.com/)
- [API 定价](https://platform.deepseek.com/pricing)

---

**提示**：如果遇到问题，可以查看 `server/logs/` 目录下的日志文件获取详细错误信息。

