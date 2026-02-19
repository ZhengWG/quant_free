# QuantFree 插件

VSCode/Cursor 前端，提供行情、策略、交易、选股、预测等视图与命令。

## 开发

```bash
npm install
npm run compile    # 或 npm run watch 监听编译
npm run package    # 打包 .vsix
```

调试：在编辑器中打开项目根目录，按 F5 启动 Extension Development Host，在新窗口中使用插件。

## 结构

- `src/extension.ts` 入口，注册命令与视图
- `src/views/` 行情、策略、交易、智能选股、预测、策略测试等
- `src/services/` ApiClient、WebSocketClient、StorageService
- `src/types/`、`src/utils/`

