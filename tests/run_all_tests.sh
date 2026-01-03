#!/bin/bash
# 运行所有测试的便捷脚本

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "=========================================="
echo "🧪 QuantFree 测试套件"
echo "=========================================="
echo ""

# 激活conda环境
if command -v conda &> /dev/null; then
    source $(conda info --base)/etc/profile.d/conda.sh
    conda activate quant_free
else
    echo "⚠️  conda未找到，尝试直接使用python3"
fi

# 检查服务是否运行
if ! curl -s http://localhost:3000/health > /dev/null 2>&1; then
    echo "⚠️  后端服务未运行，正在启动..."
    cd "$PROJECT_ROOT/server"
    python3 main.py > /tmp/quant_free_test.log 2>&1 &
    SERVER_PID=$!
    echo "服务PID: $SERVER_PID"
    
    # 等待服务启动
    for i in {1..10}; do
        if curl -s http://localhost:3000/health > /dev/null 2>&1; then
            echo "✓ 服务启动成功"
            break
        fi
        sleep 1
    done
else
    echo "✓ 后端服务已运行"
    SERVER_PID=""
fi

# 运行API测试
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "1. API功能测试"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
cd "$PROJECT_ROOT/tests/api"
python3 test_api.py

# 运行WebSocket测试
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "2. WebSocket集成测试"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
cd "$PROJECT_ROOT/tests/integration"
python3 test_websocket.py

# 清理
if [ ! -z "$SERVER_PID" ]; then
    echo ""
    echo "🧹 清理..."
    kill $SERVER_PID 2>/dev/null || true
fi

echo ""
echo "=========================================="
echo "✅ 所有测试完成！"
echo "=========================================="

