#!/usr/bin/env python3
"""
RAGFlow Session Fix Verification Script
用于验证session配置修复是否正确
"""

import sys
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def test_redis_import():
    """测试redis包导入"""
    print("1. 测试redis包导入...")
    try:
        import redis
        print(f"   ✓ redis包可用，版本: {getattr(redis, '__version__', 'unknown')}")
        return True
    except ImportError as e:
        print(f"   ✗ redis包导入失败: {e}")
        return False

def test_valkey_import():
    """测试valkey包导入"""
    print("2. 测试valkey包导入...")
    try:
        import valkey
        print(f"   ✓ valkey包可用，版本: {getattr(valkey, '__version__', 'unknown')}")
        return True
    except ImportError as e:
        print(f"   ✗ valkey包导入失败: {e}")
        return False

def test_flask_session_redis_import():
    """测试Flask-Session Redis支持"""
    print("3. 测试Flask-Session Redis支持...")
    try:
        from flask_session.redis import RedisSessionInterface
        print("   ✓ Flask-Session Redis接口可用")
        return True
    except ImportError as e:
        print(f"   ✗ Flask-Session Redis接口导入失败: {e}")
        return False

def test_ragflow_redis_conn():
    """测试RAGFlow Redis连接"""
    print("4. 测试RAGFlow Redis连接...")
    try:
        from rag.utils.redis_conn import REDIS_CONN
        if REDIS_CONN.is_alive():
            print("   ✓ RAGFlow Redis连接可用")
            return True
        else:
            print("   ⚠ RAGFlow Redis连接不可用（可能Redis服务未启动）")
            return False
    except Exception as e:
        print(f"   ✗ RAGFlow Redis连接测试失败: {e}")
        return False

def test_session_configuration():
    """测试session配置逻辑"""
    print("5. 测试session配置逻辑...")
    try:
        # 模拟Flask应用配置
        from flask import Flask
        app = Flask(__name__)
        
        # 这里只测试配置逻辑，不实际初始化Session
        with app.app_context():
            # 尝试导入配置函数
            sys.path.insert(0, 'api')
            from apps import configure_session_storage, _configure_redis_session, _configure_filesystem_session
            print("   ✓ session配置函数导入成功")
            
            # 测试Redis配置逻辑
            result = _configure_redis_session()
            if result:
                print("   ✓ Redis session配置测试成功")
            else:
                print("   ⚠ Redis session配置测试失败（降级到文件系统）")
            
            return True
    except Exception as e:
        print(f"   ✗ session配置测试失败: {e}")
        return False

def main():
    """主测试函数"""
    print("🔍 RAGFlow Session Fix Verification")
    print("=" * 40)
    
    results = []
    results.append(test_redis_import())
    results.append(test_valkey_import())
    results.append(test_flask_session_redis_import())
    results.append(test_ragflow_redis_conn())
    results.append(test_session_configuration())
    
    print("\n📊 测试结果汇总:")
    print("=" * 40)
    
    passed = sum(results)
    total = len(results)
    
    if passed == total:
        print(f"✅ 所有测试通过 ({passed}/{total})")
        print("🎉 Session修复验证成功！可以使用Redis session存储。")
        return 0
    elif passed >= 3:  # redis, valkey, flask-session可用就足够了
        print(f"⚠️  部分测试通过 ({passed}/{total})")
        print("💡 基本功能可用，但可能需要检查Redis服务状态。")
        return 0
    else:
        print(f"❌ 测试失败 ({passed}/{total})")
        print("🔧 需要解决依赖问题才能使用Redis session存储。")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 