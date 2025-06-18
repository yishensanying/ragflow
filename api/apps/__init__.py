#
#  Copyright 2024 The InfiniFlow Authors. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#
import os
import sys
import logging
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from flask import Blueprint, Flask
from werkzeug.wrappers.request import Request
from flask_cors import CORS
from flasgger import Swagger
from itsdangerous.url_safe import URLSafeTimedSerializer as Serializer

from api.db import StatusEnum
from api.db.db_models import close_connection
from api.db.services import UserService
from api.utils import CustomJSONEncoder, commands
from api.utils import current_timestamp

from flask_session import Session
from flask_login import LoginManager
from api import settings
from api.utils.api_utils import server_error_response
from api.constants import API_VERSION

__all__ = ["app"]

Request.json = property(lambda self: self.get_json(force=True, silent=True))

app = Flask(__name__)

# Add this at the beginning of your file to configure Swagger UI
swagger_config = {
    "headers": [],
    "specs": [
        {
            "endpoint": "apispec",
            "route": "/apispec.json",
            "rule_filter": lambda rule: True,  # Include all endpoints
            "model_filter": lambda tag: True,  # Include all models
        }
    ],
    "static_url_path": "/flasgger_static",
    "swagger_ui": True,
    "specs_route": "/apidocs/",
}

swagger = Swagger(
    app,
    config=swagger_config,
    template={
        "swagger": "2.0",
        "info": {
            "title": "RAGFlow API",
            "description": "",
            "version": "1.0.0",
        },
        "securityDefinitions": {
            "ApiKeyAuth": {"type": "apiKey", "name": "Authorization", "in": "header"}
        },
    },
)

CORS(app, supports_credentials=True, max_age=2592000)
app.url_map.strict_slashes = False
app.json_encoder = CustomJSONEncoder
app.errorhandler(Exception)(server_error_response)

## convince for dev and debug
# app.config["LOGIN_DISABLED"] = True

# 配置Flask session使用Redis存储以解决多进程session共享问题
def configure_session_storage():
    """配置session存储方式，优先使用Redis以确保多进程环境下的session共享"""

    # 基础配置
    app.config["SESSION_PERMANENT"] = False
    # 直接读取SECRET_KEY配置，不依赖settings.SECRET_KEY（避免初始化顺序问题）
    from api.utils import get_base_config
    from datetime import date
    secret_key = get_base_config("ragflow", {}).get("secret_key", str(date.today()))
    app.config["SECRET_KEY"] = secret_key

    # 优先级：环境变量 > Redis自动检测 > 文件系统降级
    session_type = os.environ.get("RAGFLOW_SESSION_TYPE", "auto").lower()

    if session_type == "filesystem":
        # 强制使用文件系统存储
        _configure_filesystem_session()
        return

    # 尝试使用Redis存储
    if session_type in ["auto", "redis"]:
        if _configure_redis_session():
            return
        elif session_type == "redis":
            # 强制要求Redis但Redis不可用时，抛出异常
            raise RuntimeError("Redis session storage required but Redis is not available")

    # 降级到文件系统存储
    _configure_filesystem_session()

def _configure_redis_session():
    """配置Redis session存储"""
    try:
        # 首先检查是否可以导入redis包（Flask-Session的Redis支持需要）
        try:
            import redis
            logging.debug("redis package is available for Flask-Session")
        except ImportError:
            raise Exception("redis package not available - Flask-Session Redis support requires 'redis' package")

        from rag.utils.redis_conn import REDIS_CONN

        # 检查RAGFlow的Redis连接
        if not REDIS_CONN.is_alive():
            raise Exception("RAGFlow Redis connection not available")

        # 测试Redis连接
        REDIS_CONN.REDIS.ping()

        # 创建Flask-Session兼容的Redis连接
        # 注意：RAGFlow使用valkey，但Flask-Session需要redis包兼容的连接
        redis_config = REDIS_CONN.config
        flask_redis = redis.StrictRedis(
            host=redis_config["host"].split(":")[0],
            port=int(redis_config.get("host", ":6379").split(":")[1]),
            db=int(redis_config.get("db", 1)),
            password=redis_config.get("password"),
            decode_responses=False,  # 修复Valkey兼容性：不自动解码responses，让Flask-Session处理序列化
        )

        # 测试Flask-Session兼容的连接
        flask_redis.ping()

        # 配置Redis session，优化Valkey兼容性
        app.config["SESSION_TYPE"] = "redis"
        app.config["SESSION_REDIS"] = flask_redis
        app.config["SESSION_KEY_PREFIX"] = "ragflow:session:"
        app.config["SESSION_USE_SIGNER"] = True
        app.config["SESSION_COOKIE_SECURE"] = False  # 开发环境设为False
        app.config["SESSION_COOKIE_HTTPONLY"] = True
        app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

        # Valkey兼容性优化：确保正确的序列化格式
        # Flask-Session默认使用pickle序列化，这与Valkey完全兼容
        app.config["SESSION_SERIALIZATION_FORMAT"] = "json"  # 使用JSON格式，更稳定的兼容性

        # session过期时间配置
        session_timeout = int(os.environ.get("RAGFLOW_SESSION_TIMEOUT", str(7 * 24 * 3600)))  # 默认7天
        app.config["SESSION_REDIS_EXPIRATION_TIME"] = session_timeout
        app.config["PERMANENT_SESSION_LIFETIME"] = session_timeout

        # 记录成功配置
        logging.info(f"✓ Redis session storage configured successfully (timeout: {session_timeout}s)")
        logging.info(f"✓ Redis connection: {redis_config.get('host', 'unknown')}")
        logging.info("✓ Using redis package for Flask-Session compatibility")
        logging.info("✓ Valkey compatibility optimizations applied: decode_responses=False, JSON serialization")
        return True

    except Exception as e:
        logging.warning(f"Failed to configure Redis session storage: {e}")
        if "redis package not available" in str(e):
            logging.warning("💡 To use Redis sessions, install: pip install redis")
            logging.warning("💡 Or add 'redis' to your Python dependencies")
        return False

def _configure_filesystem_session():
    """配置文件系统session存储（降级方案）"""
    app.config["SESSION_TYPE"] = "filesystem"
    # 确保session目录存在且所有进程可访问
    session_dir = os.environ.get("RAGFLOW_SESSION_DIR", "/tmp/ragflow_sessions")
    app.config["SESSION_FILE_DIR"] = session_dir
    app.config["SESSION_FILE_THRESHOLD"] = 500  # 最大session文件数
    app.config["SESSION_FILE_MODE"] = 0o600  # 安全的文件权限

    # 创建session目录
    try:
        os.makedirs(session_dir, mode=0o755, exist_ok=True)
    except Exception as e:
        logging.error(f"Failed to create session directory {session_dir}: {e}")

    # 发出警告
    logging.warning("⚠️  Using filesystem session storage - may cause login issues in multi-process environment")
    logging.warning(f"⚠️  Session directory: {session_dir}")
    logging.warning("💡 Recommendation: Ensure Redis is available for production deployment")

# 执行session配置
configure_session_storage()

app.config["MAX_CONTENT_LENGTH"] = int(
    os.environ.get("MAX_CONTENT_LENGTH", 1024 * 1024 * 1024)
)

Session(app)
login_manager = LoginManager()
login_manager.init_app(app)

# 添加增强的session管理中间件
@app.before_request
def enhanced_session_management():
    """增强的session管理，确保多进程环境下的session一致性和健康状态"""
    from flask import session, request, g

    # 跳过静态文件和非API请求
    if (not request.endpoint or 
        request.endpoint.startswith('static') or
        not any(path in request.path for path in ['/v1/', '/api/'])):
        return

    # 记录请求处理的worker进程信息
    current_worker_pid = os.getpid()
    g.worker_pid = current_worker_pid

    # 检查session健康状态
    _check_session_health(session, current_worker_pid)

    # 为session添加跟踪信息（仅在调试模式或Redis不可用时）
    if app.config.get("SESSION_TYPE") == "filesystem" or logging.getLogger().isEnabledFor(logging.DEBUG):
        _add_session_tracking_info(session, current_worker_pid)

def _check_session_health(session, current_worker_pid):
    """检查session健康状态"""
    try:
        # 检查session是否可读写
        test_key = f"_health_check_{current_worker_pid}"
        session[test_key] = current_timestamp()

        # 清理测试数据
        session.pop(test_key, None)

    except Exception as e:
        # session读写异常，记录错误
        logging.error(f"Session health check failed on worker {current_worker_pid}: {e}")

        # 如果是Redis session，尝试重新连接
        if app.config.get("SESSION_TYPE") == "redis":
            _attempt_redis_recovery()

def _add_session_tracking_info(session, current_worker_pid):
    """为session添加跟踪信息，用于调试和监控"""
    try:
        # 记录当前worker信息
        if 'ragflow_worker_id' not in session:
            session['ragflow_worker_id'] = current_worker_pid
            session['ragflow_session_created'] = current_timestamp()
            session['ragflow_request_count'] = 0
            logging.debug(f"New session created on worker {current_worker_pid}")

        # 更新请求计数
        session['ragflow_request_count'] = session.get('ragflow_request_count', 0) + 1
        session['ragflow_last_accessed'] = current_timestamp()

        # 检测worker切换（仅在文件系统模式下有意义）
        previous_worker = session.get('ragflow_worker_id')
        if previous_worker != current_worker_pid:
            logging.info(f"Session migrated: worker {previous_worker} → {current_worker_pid} "
                        f"(requests: {session.get('ragflow_request_count', 0)})")
            session['ragflow_worker_id'] = current_worker_pid

    except Exception as e:
        # 跟踪信息添加失败，不应影响正常业务
        logging.debug(f"Failed to add session tracking info: {e}")

def _attempt_redis_recovery():
    """尝试恢复Redis连接"""
    try:
        from rag.utils.redis_conn import REDIS_CONN
        if REDIS_CONN.REDIS:
            REDIS_CONN.REDIS.ping()
            logging.info("Redis session storage recovered")
        else:
            logging.warning("Redis session storage still unavailable")
    except Exception as e:
        logging.warning(f"Redis recovery attempt failed: {e}")

# 添加session清理任务
@app.after_request
def session_cleanup(response):
    """请求结束后的session清理工作"""
    from flask import session

    # 只在文件系统模式下进行清理
    if app.config.get("SESSION_TYPE") == "filesystem":
        try:
            # 清理过期的跟踪信息
            tracking_keys = [k for k in session.keys() if k.startswith('ragflow_')]
            if len(tracking_keys) > 10:  # 防止跟踪信息过多
                for key in tracking_keys[:-5]:  # 只保留最新的5个
                    session.pop(key, None)
        except Exception:
            pass  # 清理失败不影响响应

    return response

commands.register_commands(app)


def search_pages_path(pages_dir):
    app_path_list = [
        path for path in pages_dir.glob("*_app.py") if not path.name.startswith(".")
    ]
    api_path_list = [
        path for path in pages_dir.glob("*sdk/*.py") if not path.name.startswith(".")
    ]
    app_path_list.extend(api_path_list)
    return app_path_list


def register_page(page_path):
    path = f"{page_path}"

    page_name = page_path.stem.removesuffix("_app")
    module_name = ".".join(
        page_path.parts[page_path.parts.index("api"): -1] + (page_name,)
    )

    spec = spec_from_file_location(module_name, page_path)
    page = module_from_spec(spec)
    page.app = app
    page.manager = Blueprint(page_name, module_name)
    sys.modules[module_name] = page
    spec.loader.exec_module(page)
    page_name = getattr(page, "page_name", page_name)
    sdk_path = "\\sdk\\" if sys.platform.startswith("win") else "/sdk/"
    url_prefix = (
        f"/api/{API_VERSION}" if sdk_path in path else f"/{API_VERSION}/{page_name}"
    )

    app.register_blueprint(page.manager, url_prefix=url_prefix)
    return url_prefix


pages_dir = [
    Path(__file__).parent,
    Path(__file__).parent.parent / "api" / "apps",
    Path(__file__).parent.parent / "api" / "apps" / "sdk",
]

client_urls_prefix = [
    register_page(path) for dir in pages_dir for path in search_pages_path(dir)
]


@login_manager.request_loader
def load_user(web_request):
    # 直接读取SECRET_KEY配置，确保一致性
    from api.utils import get_base_config
    from datetime import date
    secret_key = get_base_config("ragflow", {}).get("secret_key", str(date.today()))
    jwt = Serializer(secret_key=secret_key)
    authorization = web_request.headers.get("Authorization")
    if authorization:
        try:
            access_token = str(jwt.loads(authorization))

            if not access_token or not access_token.strip():
                logging.warning("Authentication attempt with empty access token")
                return None

            # Access tokens should be UUIDs (32 hex characters)
            if len(access_token.strip()) < 32:
                logging.warning(f"Authentication attempt with invalid token format: {len(access_token)} chars")
                return None

            user = UserService.query(
                access_token=access_token, status=StatusEnum.VALID.value
            )
            if user:
                if not user[0].access_token or not user[0].access_token.strip():
                    logging.warning(f"User {user[0].email} has empty access_token in database")
                    return None
                return user[0]
            else:
                return None
        except Exception as e:
            logging.warning(f"load_user got exception {e}")
            return None
    else:
        return None


@app.teardown_request
def _db_close(exc):
    close_connection()
