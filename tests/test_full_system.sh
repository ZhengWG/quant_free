#!/bin/bash
# 完整系统测试脚本

set -e

echo "=========================================="
echo "🚀 QuantFree 完整系统测试"
echo "=========================================="
echo ""

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# 检查conda环境
echo "📦 检查环境..."
if command -v conda &> /dev/null; then
    source $(conda info --base)/etc/profile.d/conda.sh
    if ! conda env list | grep -q "quant_free"; then
        echo -e "${RED}❌ conda环境 quant_free 不存在${NC}"
        echo "请先运行: conda create -n quant_free python=3.10 -y"
        exit 1
    fi
    # 激活conda环境
    echo "🔧 激活conda环境..."
    conda activate quant_free
    PYTHON_CMD="python"
else
    echo -e "${YELLOW}⚠️  conda未找到，使用系统python3${NC}"
    PYTHON_CMD="python3"
fi

# 检查依赖
echo "📋 检查Python依赖..."
cd "$PROJECT_ROOT/server"
if ! $PYTHON_CMD -c "import fastapi, uvicorn, pydantic, loguru, sqlalchemy" 2>/dev/null; then
    echo -e "${YELLOW}⚠️  部分依赖缺失，正在安装...${NC}"
    pip install -q -r requirements.txt
fi

# 启动后端服务（后台）
echo "🚀 启动后端服务..."
$PYTHON_CMD main.py > /tmp/quant_free_server.log 2>&1 &
SERVER_PID=$!
echo "服务PID: $SERVER_PID"

# 等待服务启动
echo "⏳ 等待服务启动..."
for i in {1..10}; do
    if curl -s http://localhost:3000/health > /dev/null 2>&1; then
        echo -e "${GREEN}✓ 服务启动成功！${NC}"
        break
    fi
    if [ $i -eq 10 ]; then
        echo -e "${RED}❌ 服务启动超时${NC}"
        kill $SERVER_PID 2>/dev/null || true
        exit 1
    fi
    sleep 1
done

# 运行API测试
echo ""
echo "🧪 运行API测试..."
cd "$PROJECT_ROOT/tests/api"
$PYTHON_CMD test_api.py

# 测试订单创建
echo ""
echo "📝 测试订单创建..."
ORDER_RESPONSE=$(curl -s -X POST http://localhost:3000/api/v1/trade/order \
    -H "Content-Type: application/json" \
    -d '{"stock_code":"000001","stock_name":"平安银行","type":"BUY","order_type":"MARKET","quantity":100}')

if echo "$ORDER_RESPONSE" | grep -q '"success":true'; then
    echo -e "${GREEN}✓ 订单创建成功${NC}"
    ORDER_ID=$(echo "$ORDER_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['data']['id'])" 2>/dev/null)
    echo "订单ID: $ORDER_ID"
else
    echo -e "${RED}❌ 订单创建失败${NC}"
    echo "$ORDER_RESPONSE"
fi

# 测试VSCode插件编译
echo ""
echo "🔨 测试VSCode插件编译..."
cd "$PROJECT_ROOT/extension"
if [ -f "package.json" ]; then
    # 尝试使用nvm加载node和npm
    if [ -s "$HOME/.nvm/nvm.sh" ]; then
        export NVM_DIR="$HOME/.nvm"
        source "$NVM_DIR/nvm.sh"
        nvm use node 2>/dev/null || nvm use --lts 2>/dev/null || true
    fi
    
    if ! command -v npm &> /dev/null; then
        echo -e "${YELLOW}⚠️  npm未安装，跳过插件编译测试${NC}"
    else
        echo "Node版本: $(node --version)"
        echo "NPM版本: $(npm --version)"
        if [ ! -d "node_modules" ]; then
            echo "安装插件依赖..."
            npm install --silent
        fi
        echo "编译TypeScript..."
        if npm run compile 2>&1 | tee /tmp/compile.log | grep -q "error"; then
            echo -e "${RED}❌ 插件编译失败${NC}"
            cat /tmp/compile.log
        else
            echo -e "${GREEN}✓ 插件编译成功${NC}"
        fi
    fi
else
    echo -e "${YELLOW}⚠️  未找到extension/package.json${NC}"
fi

# 清理
echo ""
echo "🧹 清理..."
kill $SERVER_PID 2>/dev/null || true
echo -e "${GREEN}✓ 测试完成！${NC}"

