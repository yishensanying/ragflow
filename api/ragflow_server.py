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

# from beartype import BeartypeConf
# from beartype.claw import beartype_all  # <-- you didn't sign up for this
# beartype_all(conf=BeartypeConf(violation_type=UserWarning))    # <-- emit warnings from all code

from api.utils.log_utils import initRootLogger
from plugin import GlobalPluginManager
initRootLogger("ragflow_server")

import logging
import os
import signal
import sys
import time
import traceback
import threading
import uuid
import multiprocessing

from api import settings
from api.apps import app
from api.db.runtime_config import RuntimeConfig
from api.db.services.document_service import DocumentService
from api import utils

from api.db.db_models import init_database_tables as init_web_db
from api.db.init_data import init_web_data
from api.versions import get_ragflow_version
from api.utils import show_configs
from rag.settings import print_rag_settings
from rag.utils.redis_conn import RedisDistributedLock

stop_event = threading.Event()

RAGFLOW_DEBUGPY_LISTEN = int(os.environ.get('RAGFLOW_DEBUGPY_LISTEN', "0"))

def update_progress():
    lock_value = str(uuid.uuid4())
    redis_lock = RedisDistributedLock("update_progress", lock_value=lock_value, timeout=60)
    logging.info(f"update_progress lock_value: {lock_value}")
    while not stop_event.is_set():
        try:
            if redis_lock.acquire():
                DocumentService.update_progress()
                redis_lock.release()
            stop_event.wait(6)
        except Exception:
            logging.exception("update_progress exception")
        finally:
            redis_lock.release()

def signal_handler(sig, frame):
    logging.info("Received interrupt signal, shutting down...")
    stop_event.set()
    time.sleep(1)
    sys.exit(0)

def init_app():
    logging.info(r"""
        ____   ___    ______ ______ __               
       / __ \ /   |  / ____// ____// /____  _      __
      / /_/ // /| | / / __ / /_   / // __ \| | /| / /
     / _, _// ___ |/ /_/ // __/  / // /_/ /| |/ |/ / 
    /_/ |_|/_/  |_|\____//_/    /_/ \____/ |__/|__/                             

    """)
    logging.info(
        f'RAGFlow version: {get_ragflow_version()}'
    )
    logging.info(
        f'project base: {utils.file_utils.get_project_base_directory()}'
    )
    show_configs()
    settings.init_settings()
    print_rag_settings()

    if RAGFLOW_DEBUGPY_LISTEN > 0:
        logging.info(f"debugpy listen on {RAGFLOW_DEBUGPY_LISTEN}")
        import debugpy
        debugpy.listen(("0.0.0.0", RAGFLOW_DEBUGPY_LISTEN))

    # init db
    init_web_db()
    init_web_data()
    # init runtime config
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--version", default=False, help="RAGFlow version", action="store_true"
    )
    parser.add_argument(
        "--debug", default=False, help="debug mode", action="store_true"
    )
    args = parser.parse_args()
    if args.version:
        print(get_ragflow_version())
        sys.exit(0)

    RuntimeConfig.DEBUG = args.debug
    if RuntimeConfig.DEBUG:
        logging.info("run on debug mode")

    RuntimeConfig.init_env()
    RuntimeConfig.init_config(JOB_SERVER_HOST=settings.HOST_IP, HTTP_PORT=settings.HOST_PORT)

    GlobalPluginManager.load_plugins()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    def delayed_start_update_progress():
        logging.info("Starting update_progress thread (delayed)")
        t = threading.Thread(target=update_progress, daemon=True)
        t.start()

    if RuntimeConfig.DEBUG:
        if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
            threading.Timer(1.0, delayed_start_update_progress).start()
    else:
        threading.Timer(1.0, delayed_start_update_progress).start()

    return app

# 初始化应用实例
app = init_app()

# 这部分是为了直接使用python命令运行时可以使用内置服务器进行开发调试
if __name__ == '__main__':
    # 如果在开发环境中使用debug模式，使用werkzeug的开发服务器
    if RuntimeConfig.DEBUG:
        try:
            from werkzeug.serving import run_simple
            logging.info("RAGFlow HTTP server starting in debug mode...")
            logging.info("RAGFlow HTTP server starting in run_simple...")
            run_simple(
                hostname=settings.HOST_IP,
                port=settings.HOST_PORT,
                application=app,
                threaded=True,
                use_reloader=True,
                use_debugger=True,
            )
        except Exception:
            traceback.print_exc()
            stop_event.set()
            time.sleep(1)
            os.kill(os.getpid(), signal.SIGKILL)
    else:
        # 在生产环境使用gunicorn
        try:
            logging.info("RAGFlow HTTP server starting in gunicorn...")
            import gunicorn.app.base

            class StandaloneApplication(gunicorn.app.base.BaseApplication):
                def __init__(self, app, options=None):
                    self.options = options or {}
                    self.application = app
                    super().__init__()

                def load_config(self):
                    for key, value in self.options.items():
                        if key in self.cfg.settings and value is not None:
                            self.cfg.set(key.lower(), value)

                def load(self):
                    return self.application

            # 从环境变量读取gunicorn配置，提供合理的默认值
            workers = int(os.environ.get('GUNICORN_WORKERS', 
                          min(multiprocessing.cpu_count() * 2 + 1, 16)))

            # gunicorn配置
            options = {
                'bind': f"{settings.HOST_IP}:{settings.HOST_PORT}",
                'workers': workers,
                'worker_class': os.environ.get('GUNICORN_WORKER_CLASS', 'sync'),
                'worker_connections': int(os.environ.get('GUNICORN_WORKER_CONNECTIONS', '1000')),
                'timeout': int(os.environ.get('GUNICORN_TIMEOUT', '300')),
                'keepalive': int(os.environ.get('GUNICORN_KEEPALIVE', '5')),
                'preload_app': os.environ.get('GUNICORN_PRELOAD_APP', 'true').lower() == 'true',
                'accesslog': os.environ.get('GUNICORN_ACCESS_LOG', '-'),
                'errorlog': os.environ.get('GUNICORN_ERROR_LOG', '-'),
                'loglevel': os.environ.get('GUNICORN_LOG_LEVEL', 'info'),
                'max_requests': int(os.environ.get('GUNICORN_MAX_REQUESTS', '1000')),
                'max_requests_jitter': int(os.environ.get('GUNICORN_MAX_REQUESTS_JITTER', '100')),
                'worker_tmp_dir': '/dev/shm',
            }

            logging.info(f"RAGFlow HTTP server starting with gunicorn (workers: {workers})...")
            StandaloneApplication(app, options).run()
        except Exception:
            traceback.print_exc()
            stop_event.set()
            time.sleep(1)
            os.kill(os.getpid(), signal.SIGKILL)
