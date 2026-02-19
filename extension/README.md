# QuantFree 插件

VSCode/Cursor 前端，提供行情、策略、交易、选股等视图与命令。

## 主要命令

- **AI评价**：输入股票代码，获取 AI 策略评价（原「生成策略推荐」）
- **单股策略分析**：80/20 多策略回测，按评分 TopK + 未来收益预测
- **批量智能选股**：股票池内选股（原「智能选股回测」）

## 开发

```bash
npm install
npm run compile    # 或 npm run watch 监听编译
npm run package    # 打包 .vsix
```

调试：在编辑器中打开项目根目录，按 F5 启动 Extension Development Host，在新窗口中使用插件。

## 结构

- `src/extension.ts` 入口，注册命令与视图
- `src/views/` 行情、策略、交易、批量智能选股、单股策略分析等
- `src/services/` ApiClient、WebSocketClient、StorageService
- `src/types/`、`src/utils/`

