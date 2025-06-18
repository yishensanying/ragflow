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
#  limitations under the License
#
import logging
import os
from datetime import datetime
import json
import time

from flask_login import login_required, current_user
from flask import session, current_app

from api.db.db_models import APIToken
from api.db.services.api_service import APITokenService
from api.db.services.knowledgebase_service import KnowledgebaseService
from api.db.services.user_service import UserTenantService
from api import settings
from api.utils import current_timestamp, datetime_format
from api.utils.api_utils import (
    get_json_result,
    get_data_error_result,
    server_error_response,
    generate_confirmation_token,
)
from api.versions import get_ragflow_version
from rag.utils.storage_factory import STORAGE_IMPL, STORAGE_IMPL_TYPE
from timeit import default_timer as timer

from rag.utils.redis_conn import REDIS_CONN

@manager.route("/version", methods=["GET"])  # noqa: F821
@login_required
def version():
    """
    Get the current version of the application.
    ---
    tags:
      - System
    security:
      - ApiKeyAuth: []
    responses:
      200:
        description: Version retrieved successfully.
        schema:
          type: object
          properties:
            version:
              type: string
              description: Version number.
    """
    return get_json_result(data=get_ragflow_version())


@manager.route("/status", methods=["GET"])  # noqa: F821
@login_required
def status():
    """
    Get the system status.
    ---
    tags:
      - System
    security:
      - ApiKeyAuth: []
    responses:
      200:
        description: System is operational.
        schema:
          type: object
          properties:
            es:
              type: object
              description: Elasticsearch status.
            storage:
              type: object
              description: Storage status.
            database:
              type: object
              description: Database status.
      503:
        description: Service unavailable.
        schema:
          type: object
          properties:
            error:
              type: string
              description: Error message.
    """
    res = {}
    st = timer()
    try:
        res["doc_engine"] = settings.docStoreConn.health()
        res["doc_engine"]["elapsed"] = "{:.1f}".format((timer() - st) * 1000.0)
    except Exception as e:
        res["doc_engine"] = {
            "type": "unknown",
            "status": "red",
            "elapsed": "{:.1f}".format((timer() - st) * 1000.0),
            "error": str(e),
        }

    st = timer()
    try:
        STORAGE_IMPL.health()
        res["storage"] = {
            "storage": STORAGE_IMPL_TYPE.lower(),
            "status": "green",
            "elapsed": "{:.1f}".format((timer() - st) * 1000.0),
        }
    except Exception as e:
        res["storage"] = {
            "storage": STORAGE_IMPL_TYPE.lower(),
            "status": "red",
            "elapsed": "{:.1f}".format((timer() - st) * 1000.0),
            "error": str(e),
        }

    st = timer()
    try:
        KnowledgebaseService.get_by_id("x")
        res["database"] = {
            "database": settings.DATABASE_TYPE.lower(),
            "status": "green",
            "elapsed": "{:.1f}".format((timer() - st) * 1000.0),
        }
    except Exception as e:
        res["database"] = {
            "database": settings.DATABASE_TYPE.lower(),
            "status": "red",
            "elapsed": "{:.1f}".format((timer() - st) * 1000.0),
            "error": str(e),
        }

    st = timer()
    try:
        if not REDIS_CONN.health():
            raise Exception("Lost connection!")
        res["redis"] = {
            "status": "green",
            "elapsed": "{:.1f}".format((timer() - st) * 1000.0),
        }
    except Exception as e:
        res["redis"] = {
            "status": "red",
            "elapsed": "{:.1f}".format((timer() - st) * 1000.0),
            "error": str(e),
        }

    task_executor_heartbeats = {}
    try:
        task_executors = REDIS_CONN.smembers("TASKEXE")
        now = datetime.now().timestamp()
        for task_executor_id in task_executors:
            heartbeats = REDIS_CONN.zrangebyscore(task_executor_id, now - 60*30, now)
            heartbeats = [json.loads(heartbeat) for heartbeat in heartbeats]
            task_executor_heartbeats[task_executor_id] = heartbeats
    except Exception:
        logging.exception("get task executor heartbeats failed!")
    res["task_executor_heartbeats"] = task_executor_heartbeats

    return get_json_result(data=res)


@manager.route("/new_token", methods=["POST"])  # noqa: F821
@login_required
def new_token():
    """
    Generate a new API token.
    ---
    tags:
      - API Tokens
    security:
      - ApiKeyAuth: []
    parameters:
      - in: query
        name: name
        type: string
        required: false
        description: Name of the token.
    responses:
      200:
        description: Token generated successfully.
        schema:
          type: object
          properties:
            token:
              type: string
              description: The generated API token.
    """
    try:
        tenants = UserTenantService.query(user_id=current_user.id)
        if not tenants:
            return get_data_error_result(message="Tenant not found!")

        tenant_id = [tenant for tenant in tenants if tenant.role == 'owner'][0].tenant_id
        obj = {
            "tenant_id": tenant_id,
            "token": generate_confirmation_token(tenant_id),
            "beta": generate_confirmation_token(generate_confirmation_token(tenant_id)).replace("ragflow-", "")[:32],
            "create_time": current_timestamp(),
            "create_date": datetime_format(datetime.now()),
            "update_time": None,
            "update_date": None,
        }

        if not APITokenService.save(**obj):
            return get_data_error_result(message="Fail to new a dialog!")

        return get_json_result(data=obj)
    except Exception as e:
        return server_error_response(e)


@manager.route("/token_list", methods=["GET"])  # noqa: F821
@login_required
def token_list():
    """
    List all API tokens for the current user.
    ---
    tags:
      - API Tokens
    security:
      - ApiKeyAuth: []
    responses:
      200:
        description: List of API tokens.
        schema:
          type: object
          properties:
            tokens:
              type: array
              items:
                type: object
                properties:
                  token:
                    type: string
                    description: The API token.
                  name:
                    type: string
                    description: Name of the token.
                  create_time:
                    type: string
                    description: Token creation time.
    """
    try:
        tenants = UserTenantService.query(user_id=current_user.id)
        if not tenants:
            return get_data_error_result(message="Tenant not found!")

        tenant_id = [tenant for tenant in tenants if tenant.role == 'owner'][0].tenant_id
        objs = APITokenService.query(tenant_id=tenant_id)
        objs = [o.to_dict() for o in objs]
        for o in objs:
            if not o["beta"]:
                o["beta"] = generate_confirmation_token(generate_confirmation_token(tenants[0].tenant_id)).replace("ragflow-", "")[:32]
                APITokenService.filter_update([APIToken.tenant_id == tenant_id, APIToken.token == o["token"]], o)
        return get_json_result(data=objs)
    except Exception as e:
        return server_error_response(e)


@manager.route("/token/<token>", methods=["DELETE"])  # noqa: F821
@login_required
def rm(token):
    """
    Remove an API token.
    ---
    tags:
      - API Tokens
    security:
      - ApiKeyAuth: []
    parameters:
      - in: path
        name: token
        type: string
        required: true
        description: The API token to remove.
    responses:
      200:
        description: Token removed successfully.
        schema:
          type: object
          properties:
            success:
              type: boolean
              description: Deletion status.
    """
    APITokenService.filter_delete(
        [APIToken.tenant_id == current_user.id, APIToken.token == token]
    )
    return get_json_result(data=True)


@manager.route('/config', methods=['GET'])  # noqa: F821
def get_config():
    """
    Get system configuration.
    ---
    tags:
        - System
    responses:
        200:
            description: Return system configuration
            schema:
                type: object
                properties:
                    registerEnable:
                        type: integer 0 means disabled, 1 means enabled
                        description: Whether user registration is enabled
    """
    return get_json_result(data={
        "registerEnabled": settings.REGISTER_ENABLED
    })


@manager.route("/session/health", methods=["GET"])  # noqa: F821
@login_required
def session_health():
    """
    检查session配置和健康状态
    ---
    tags:
      - System
    security:
      - ApiKeyAuth: []
    responses:
      200:
        description: Session health status retrieved successfully.
        schema:
          type: object
          properties:
            session_type:
              type: string
              description: Current session storage type (redis/filesystem).
            redis_available:
              type: boolean
              description: Whether Redis is available.
            session_config:
              type: object
              description: Current session configuration details.
            worker_info:
              type: object
              description: Current worker process information.
    """
    health_info = {
        "session_type": current_app.config.get("SESSION_TYPE", "unknown"),
        "session_config": {},
        "worker_info": {
            "worker_pid": os.getpid(),
            "session_id": session.get("ragflow_worker_id", "N/A"),
            "session_created": session.get("ragflow_session_created", "N/A"),
            "request_count": session.get("ragflow_request_count", 0),
            "last_accessed": session.get("ragflow_last_accessed", "N/A")
        },
        "redis_info": {},
        "recommendations": []
    }

    # 检查Redis状态
    try:
        if REDIS_CONN.is_alive():
            REDIS_CONN.REDIS.ping()
            health_info["redis_available"] = True
            health_info["redis_info"] = {
                "status": "connected",
                "host": REDIS_CONN.config.get("host", "unknown"),
                "db": REDIS_CONN.config.get("db", "unknown")
            }
        else:
            health_info["redis_available"] = False
            health_info["redis_info"] = {"status": "not_connected"}
    except Exception as e:
        health_info["redis_available"] = False
        health_info["redis_info"] = {"status": "error", "error": str(e)}

    # 检查redis包可用性（Flask-Session需要）
    try:
        import redis
        health_info["redis_package_available"] = True
        health_info["redis_package_version"] = getattr(redis, "__version__", "unknown")
    except ImportError:
        health_info["redis_package_available"] = False
        health_info["redis_package_version"] = "not_installed"

    # 检查SECRET_KEY配置
    secret_key = current_app.config.get('SECRET_KEY')
    health_info["secret_key_configured"] = bool(secret_key and secret_key != 'NOT_SET')
    health_info["secret_key_length"] = len(secret_key) if secret_key else 0

    # 收集session配置信息
    session_type = health_info["session_type"]
    if session_type == "redis":
        health_info["session_config"] = {
            "key_prefix": current_app.config.get("SESSION_KEY_PREFIX", ""),
            "expiration_time": current_app.config.get("SESSION_REDIS_EXPIRATION_TIME", ""),
            "use_signer": current_app.config.get("SESSION_USE_SIGNER", False)
        }
    elif session_type == "filesystem":
        health_info["session_config"] = {
            "file_dir": current_app.config.get("SESSION_FILE_DIR", ""),
            "file_threshold": current_app.config.get("SESSION_FILE_THRESHOLD", ""),
            "file_mode": current_app.config.get("SESSION_FILE_MODE", "")
        }

    # 生成建议
    if session_type == "filesystem":
        health_info["recommendations"].append({
            "level": "warning",
            "message": "Using filesystem session storage may cause login issues in multi-process environment",
            "action": "Consider enabling Redis for session storage"
        })

    if not health_info.get("redis_package_available", False):
        health_info["recommendations"].append({
            "level": "warning",
            "message": "redis package not installed - Flask-Session Redis support unavailable",
            "action": "Install redis package: pip install redis"
        })

    if not health_info["redis_available"] and session_type == "redis":
        health_info["recommendations"].append({
            "level": "error", 
            "message": "Redis is configured but not available",
            "action": "Check Redis service status and connection"
        })

    if health_info["redis_available"] and health_info.get("redis_package_available", False) and session_type == "filesystem":
        health_info["recommendations"].append({
            "level": "info",
            "message": "Redis is available but filesystem sessions are being used", 
            "action": "Set RAGFLOW_SESSION_TYPE=redis to use Redis for better reliability"
        })

    if not health_info["secret_key_configured"]:
        health_info["recommendations"].append({
            "level": "error",
            "message": "SECRET_KEY is not configured or invalid",
            "action": "Set SECRET_KEY environment variable in docker-compose.yml"
        })
    elif health_info["secret_key_length"] < 16:
        health_info["recommendations"].append({
            "level": "warning",
            "message": "SECRET_KEY is too short (recommended: at least 16 characters)",
            "action": "Use a longer, more secure SECRET_KEY"
        })

    # 添加测试session读写
    try:
        test_key = f"health_test_{int(time.time())}"
        session[test_key] = "test_value"
        if session.get(test_key) == "test_value":
            health_info["session_read_write"] = "ok"
            session.pop(test_key, None)
        else:
            health_info["session_read_write"] = "failed"
    except Exception as e:
        health_info["session_read_write"] = f"error: {str(e)}"

    return get_json_result(data=health_info)
