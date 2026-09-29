#!/bin/bash
cd "$(dirname "$0")"
echo "🚀 启动智学领航个性化学习系统..."
echo ""
echo "🌐 浏览器访问: http://localhost:5000"
echo "   📝 测试账号: test / 123456"
echo ""
echo "按 Ctrl+C 停止服务器"
echo ""
python3 -m flask run --port=5000
