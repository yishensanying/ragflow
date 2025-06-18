#!/usr/bin/env python3
"""
RAGFlow Session 问题修复验证脚本
验证所有关键组件是否正确配置
"""

import os
import sys
import json
import requests
import subprocess
from pathlib import Path

# 彩色输出
class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    ENDC = '\033[0m'

def print_status(message, status="INFO"):
    colors = {
        "SUCCESS": Colors.GREEN,
        "ERROR": Colors.RED,
        "WARNING": Colors.YELLOW,
        "INFO": Colors.BLUE
    }
    print(f"{colors.get(status, Colors.BLUE)}[{status}]{Colors.ENDC} {message}")

def check_file_exists(filepath, description):
    """检查文件是否存在"""
    if Path(filepath).exists():
        print_status(f"✓ {description}: {filepath}", "SUCCESS")
        return True
    else:
        print_status(f"✗ {description}: {filepath} - FILE NOT FOUND", "ERROR")
        return False

def check_file_content(filepath, search_text, description):
    """检查文件内容"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            if search_text in content:
                print_status(f"✓ {description}", "SUCCESS")
                return True
            else:
                print_status(f"✗ {description} - CONTENT NOT FOUND", "ERROR")
                return False
    except Exception as e:
        print_status(f"✗ {description} - ERROR: {e}", "ERROR")
        return False

def check_python_package(package_name):
    """检查Python包是否安装"""
    try:
        result = subprocess.run([sys.executable, "-c", f"import {package_name}"], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print_status(f"✓ Python package '{package_name}' is installed", "SUCCESS")
            return True
        else:
            print_status(f"✗ Python package '{package_name}' is NOT installed", "ERROR")
            return False
    except Exception as e:
        print_status(f"✗ Error checking package '{package_name}': {e}", "ERROR")
        return False

def check_environment_variable(var_name, default_value=None):
    """检查环境变量"""
    value = os.environ.get(var_name, default_value)
    if value:
        print_status(f"✓ Environment variable {var_name}={value}", "SUCCESS")
        return True
    else:
        print_status(f"✗ Environment variable {var_name} not set", "WARNING")
        return False

def test_session_health_endpoint(base_url="http://localhost:9380"):
    """测试session健康检查端点"""
    try:
        response = requests.get(f"{base_url}/v1/system/session/health", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print_status(f"✓ Session health endpoint accessible", "SUCCESS")
            print_status(f"  Session type: {data.get('data', {}).get('session_type', 'unknown')}", "INFO")
            return True
        else:
            print_status(f"✗ Session health endpoint returned {response.status_code}", "ERROR")
            return False
    except requests.exceptions.ConnectionError:
        print_status("✗ Cannot connect to RAGFlow server - server may not be running", "WARNING")
        return False
    except Exception as e:
        print_status(f"✗ Error testing session endpoint: {e}", "ERROR")
        return False

def main():
    print_status("🔍 RAGFlow Session 修复验证开始", "INFO")
    print("=" * 60)
    
    # 获取项目根目录
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    
    results = []
    
    # 1. 检查核心配置文件
    print_status("1. 检查配置文件", "INFO")
    results.append(check_file_exists(project_root / "conf/service_conf.yaml", "主配置文件"))
    results.append(check_file_exists(project_root / "docker/service_conf.yaml.template", "Docker配置模板"))
    results.append(check_file_content(project_root / "conf/service_conf.yaml", "secret_key:", "主配置文件包含secret_key"))
    results.append(check_file_content(project_root / "docker/service_conf.yaml.template", "secret_key:", "Docker模板包含secret_key"))
    
    # 2. 检查核心Python文件
    print_status("\n2. 检查核心代码文件", "INFO")
    results.append(check_file_exists(project_root / "api/apps/__init__.py", "Flask应用初始化文件"))
    results.append(check_file_content(project_root / "api/apps/__init__.py", "configure_session_storage", "Session配置函数"))
    results.append(check_file_content(project_root / "api/apps/__init__.py", "_configure_redis_session", "Redis session配置"))
    results.append(check_file_exists(project_root / "api/apps/system_app.py", "系统API文件"))
    results.append(check_file_content(project_root / "api/apps/system_app.py", "/session/health", "Session健康检查API"))
    
    # 3. 检查依赖
    print_status("\n3. 检查Python依赖", "INFO")
    results.append(check_file_exists(project_root / "pyproject.toml", "Python项目配置"))
    results.append(check_file_content(project_root / "pyproject.toml", "redis>=5.0.0", "pyproject.toml包含redis依赖"))
    results.append(check_python_package("redis"))
    results.append(check_python_package("flask_session"))
    results.append(check_python_package("valkey"))
    
    # 4. 检查Docker配置
    print_status("\n4. 检查Docker配置", "INFO")
    results.append(check_file_exists(project_root / "docker/docker-compose.yml", "Docker Compose配置"))
    results.append(check_file_content(project_root / "docker/docker-compose.yml", "SECRET_KEY", "Docker Compose包含SECRET_KEY"))
    results.append(check_file_content(project_root / "docker/docker-compose.yml", "RAGFLOW_SESSION_TYPE", "Docker Compose包含session配置"))
    
    # 5. 检查辅助文件
    print_status("\n5. 检查辅助文件", "INFO")
    results.append(check_file_exists(project_root / "scripts/check_session_health.sh", "Session健康检查脚本"))
    results.append(check_file_exists(project_root / "Session_Fix_README.md", "修复方案文档"))
    
    # 6. 检查环境变量（如果设置了的话）
    print_status("\n6. 检查环境变量（可选）", "INFO")
    check_environment_variable("SECRET_KEY")
    check_environment_variable("RAGFLOW_SESSION_TYPE")
    check_environment_variable("RAGFLOW_SESSION_TIMEOUT")
    
    # 7. 测试API端点（如果服务器运行中）
    print_status("\n7. 测试API端点（如果可用）", "INFO")
    test_session_health_endpoint()
    
    # 总结
    print("\n" + "=" * 60)
    success_count = sum(results)
    total_count = len(results)
    success_rate = success_count / total_count * 100
    
    if success_rate >= 90:
        print_status(f"🎉 验证完成: {success_count}/{total_count} 项检查通过 ({success_rate:.1f}%)", "SUCCESS")
        print_status("✅ Session修复方案已正确实施！", "SUCCESS")
    elif success_rate >= 70:
        print_status(f"⚠️ 验证完成: {success_count}/{total_count} 项检查通过 ({success_rate:.1f}%)", "WARNING")
        print_status("🔧 大部分组件已配置，但仍有一些问题需要解决", "WARNING")
    else:
        print_status(f"❌ 验证失败: {success_count}/{total_count} 项检查通过 ({success_rate:.1f}%)", "ERROR")
        print_status("🚨 Session修复方案存在重大问题，需要检查配置", "ERROR")
    
    print("\n📖 更多信息请查看：")
    print("   - Session_Fix_README.md")
    print("   - scripts/check_session_health.sh")
    print("   - API文档: /v1/system/session/health")
    
    return success_rate >= 90

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print_status("\n用户中断验证", "WARNING")
        sys.exit(1)
    except Exception as e:
        print_status(f"\n验证过程中出现错误: {e}", "ERROR")
        sys.exit(1) 