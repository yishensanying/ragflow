#!/bin/bash

# RAGFlow Session Health Check Script
# 用于诊断多进程环境下的session配置问题

set -e

RAGFLOW_HOST=${RAGFLOW_HOST:-"localhost:9380"}
RAGFLOW_TOKEN=${RAGFLOW_TOKEN:-""}

echo "🔍 RAGFlow Session Health Check"
echo "=================================="
echo "Host: $RAGFLOW_HOST"
echo

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 打印彩色消息
print_status() {
    local status=$1
    local message=$2
    case $status in
        "ok")
            echo -e "${GREEN}✓${NC} $message"
            ;;
        "warning")
            echo -e "${YELLOW}⚠${NC} $message"
            ;;
        "error")
            echo -e "${RED}✗${NC} $message"
            ;;
        "info")
            echo -e "${BLUE}ℹ${NC} $message"
            ;;
    esac
}

# 检查依赖
check_dependencies() {
    echo "1. 检查依赖工具..."
    
    if ! command -v curl &> /dev/null; then
        print_status "error" "curl not found. Please install curl."
        exit 1
    fi
    
    if ! command -v jq &> /dev/null; then
        print_status "warning" "jq not found. JSON output will be raw."
        USE_JQ=false
    else
        USE_JQ=true
    fi
    
    print_status "ok" "Dependencies checked"
    echo
}

# 检查RAGFlow服务状态
check_ragflow_service() {
    echo "2. 检查RAGFlow服务状态..."
    
    if curl -s --max-time 10 "http://$RAGFLOW_HOST/v1/system/status" > /dev/null; then
        print_status "ok" "RAGFlow service is running"
    else
        print_status "error" "RAGFlow service is not accessible at http://$RAGFLOW_HOST"
        echo "   请检查："
        echo "   - RAGFlow容器是否正在运行"
        echo "   - 端口配置是否正确"
        echo "   - 防火墙设置"
        exit 1
    fi
    echo
}

# 检查Redis容器状态
check_redis_container() {
    echo "3. 检查Redis容器状态..."
    
    if docker ps | grep -q ragflow-redis; then
        print_status "ok" "Redis container is running"
        
        # 检查Redis连接
        if docker exec ragflow-redis redis-cli ping &> /dev/null; then
            print_status "ok" "Redis is responding to ping"
        else
            print_status "error" "Redis container exists but not responding"
        fi
    else
        print_status "warning" "Redis container not found or not running"
        echo "   这可能导致session存储降级到文件系统模式"
    fi
    echo
}

# 检查session配置
check_session_health() {
    echo "4. 检查Session配置..."
    
    if [ -z "$RAGFLOW_TOKEN" ]; then
        print_status "warning" "RAGFLOW_TOKEN not set, skipping detailed session check"
        echo "   设置token: export RAGFLOW_TOKEN=your_api_token"
        return
    fi
    
    # 调用session健康检查API
    local response
    response=$(curl -s -H "Authorization: Bearer $RAGFLOW_TOKEN" \
                   "http://$RAGFLOW_HOST/v1/system/session/health" || echo "")
    
    if [ -z "$response" ]; then
        print_status "error" "Failed to get session health status"
        return
    fi
    
    # 解析响应
    if [ "$USE_JQ" = true ]; then
        local session_type
        local redis_available
        local recommendations
        
        session_type=$(echo "$response" | jq -r '.data.session_type // "unknown"')
        redis_available=$(echo "$response" | jq -r '.data.redis_available // false')
        recommendations=$(echo "$response" | jq -c '.data.recommendations // []')
        
        print_status "info" "Session type: $session_type"
        
        if [ "$redis_available" = "true" ]; then
            print_status "ok" "Redis is available for session storage"
        else
            print_status "warning" "Redis is not available"
        fi
        
        if [ "$session_type" = "redis" ]; then
            print_status "ok" "Using Redis session storage (recommended)"
        elif [ "$session_type" = "filesystem" ]; then
            print_status "warning" "Using filesystem session storage"
            echo "   这可能在多进程环境下导致登录问题"
        fi
        
        # 检查redis包可用性
        local redis_package_available
        redis_package_available=$(echo "$response" | jq -r '.data.redis_package_available // false')
        if [ "$redis_package_available" = "false" ]; then
            print_status "warning" "redis package not installed"
            echo "   Flask-Session Redis support requires redis package"
        else
            local redis_version
            redis_version=$(echo "$response" | jq -r '.data.redis_package_version // "unknown"')
            print_status "ok" "redis package available (version: $redis_version)"
        fi
        
        # 检查SECRET_KEY配置
        local secret_key_configured
        secret_key_configured=$(echo "$response" | jq -r '.data.secret_key_configured // false')
        if [ "$secret_key_configured" = "true" ]; then
            local secret_key_length
            secret_key_length=$(echo "$response" | jq -r '.data.secret_key_length // 0')
            print_status "ok" "SECRET_KEY configured (length: $secret_key_length)"
        else
            print_status "error" "SECRET_KEY not configured"
            echo "   This will cause Flask session signing errors"
        fi
        
        # 显示建议
        local rec_count
        rec_count=$(echo "$recommendations" | jq 'length')
        if [ "$rec_count" -gt 0 ]; then
            echo "   建议："
            echo "$recommendations" | jq -r '.[] | "   - " + .message + " (" + .action + ")"'
        fi
    else
        print_status "info" "Session health response:"
        echo "$response" | python -m json.tool 2>/dev/null || echo "$response"
    fi
    echo
}

# 检查Gunicorn配置
check_gunicorn_config() {
    echo "5. 检查Gunicorn配置..."
    
    # 检查worker数量
    local worker_count
    worker_count=$(docker exec ragflow-server ps aux | grep -c "gunicorn.*worker" || echo "0")
    
    if [ "$worker_count" -gt 1 ]; then
        print_status "info" "Detected $worker_count gunicorn workers"
        print_status "warning" "多进程环境需要确保session正确配置"
    elif [ "$worker_count" -eq 1 ]; then
        print_status "ok" "Single worker detected (session issues less likely)"
    else
        print_status "warning" "Could not detect gunicorn workers"
    fi
    echo
}

# 输出总结和建议
print_summary() {
    echo "6. 总结和建议"
    echo "=============="
    
    print_status "info" "如果遇到登录问题，请按以下步骤排查："
    echo
    echo "   1. 确保Redis正常运行："
    echo "      docker logs ragflow-redis"
    echo "      docker restart ragflow-redis"
    echo
    echo "   2. 检查RAGFlow session配置："
    echo "      docker logs ragflow-server | grep -E '(Redis|session|✓|⚠️)'"
    echo
    echo "   3. 检查SECRET_KEY配置："
    echo "      在docker-compose.yml中确保设置："
    echo "      - SECRET_KEY=your-secret-key-here"
    echo
    echo "   4. 强制使用Redis session："
    echo "      在docker-compose.yml中设置："
    echo "      - RAGFLOW_SESSION_TYPE=redis"
    echo
    echo "   5. 重启RAGFlow服务："
    echo "      docker restart ragflow-server"
    echo
    echo "   5. 使用session健康检查API："
    echo "      curl -H \"Authorization: Bearer YOUR_TOKEN\" \\"
    echo "           http://$RAGFLOW_HOST/v1/system/session/health"
    echo
    print_status "info" "更多信息请参考：docs/performance_tuning.md"
}

# 主执行流程
main() {
    check_dependencies
    check_ragflow_service
    check_redis_container
    check_session_health
    check_gunicorn_config
    print_summary
}

# 帮助信息
show_help() {
    echo "Usage: $0 [OPTIONS]"
    echo
    echo "RAGFlow Session Health Check Script"
    echo
    echo "Options:"
    echo "  -h, --help          Show this help message"
    echo "  -H, --host HOST     RAGFlow host:port (default: localhost:9380)"
    echo "  -t, --token TOKEN   RAGFlow API token for detailed checks"
    echo
    echo "Environment variables:"
    echo "  RAGFLOW_HOST        RAGFlow host:port"
    echo "  RAGFLOW_TOKEN       RAGFlow API token"
    echo
    echo "Examples:"
    echo "  $0                                    # Basic check"
    echo "  $0 -H localhost:9380                 # Custom host"
    echo "  $0 -t your_api_token                 # With API token"
    echo "  RAGFLOW_TOKEN=token $0               # Using environment variable"
}

# 解析命令行参数
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        -H|--host)
            RAGFLOW_HOST="$2"
            shift 2
            ;;
        -t|--token)
            RAGFLOW_TOKEN="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# 执行主逻辑
main 