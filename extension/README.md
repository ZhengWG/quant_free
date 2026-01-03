# QuantFree Extension

VSCode插件前端部分

## 开发

```bash
# 安装依赖
npm install

# 编译
npm run compile

# 监听模式（自动编译）
npm run watch

# 打包插件
npm run package
```

## 调试

1. 在VSCode中打开此目录
2. 按 `F5` 启动调试
3. 会打开一个新的VSCode窗口（Extension Development Host）
4. 在新窗口中测试插件功能

## 项目结构

- `src/extension.ts` - 插件入口
- `src/commands/` - 命令处理
- `src/views/` - UI视图
- `src/services/` - 前端服务
- `src/types/` - 类型定义
- `src/utils/` - 工具函数

