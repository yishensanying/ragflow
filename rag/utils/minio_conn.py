#
#  Copyright 2025 The InfiniFlow Authors. All Rights Reserved.
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

import logging
import time
from minio import Minio
from minio.error import S3Error
from io import BytesIO
from rag import settings
from rag.utils import singleton


@singleton
class RAGFlowMinio:
    def __init__(self):
        self.conn = None
        self.__open__()

    def __open__(self):
        try:
            if self.conn:
                self.__close__()
        except Exception:
            pass

        try:
            self.conn = Minio(settings.MINIO["host"],
                              access_key=settings.MINIO["user"],
                              secret_key=settings.MINIO["password"],
                              secure=False
                              )
        except Exception:
            logging.exception(
                "Fail to connect %s " % settings.MINIO["host"])

    def __close__(self):
        del self.conn
        self.conn = None

    def health(self):
        bucket, fnm, binary = "txtxtxtxt1", "txtxtxtxt1", b"_t@@@1"
        if not self.conn.bucket_exists(bucket):
            self.conn.make_bucket(bucket)
        r = self.conn.put_object(bucket, fnm,
                                 BytesIO(binary),
                                 len(binary)
                                 )
        return r

    def put(self, bucket, fnm, binary):
        for _ in range(3):
            try:
                if not self.conn.bucket_exists(bucket):
                    self.conn.make_bucket(bucket)

                r = self.conn.put_object(bucket, fnm,
                                         BytesIO(binary),
                                         len(binary)
                                         )
                return r
            except Exception:
                logging.exception(f"Fail to put {bucket}/{fnm}:")
                self.__open__()
                time.sleep(1)

    def rm(self, bucket, fnm):
        try:
            self.conn.remove_object(bucket, fnm)
        except Exception:
            logging.exception(f"Fail to remove {bucket}/{fnm}:")

    def get(self, bucket, filename):
        for i in range(3):
            try:
                # 检查存储桶是否存在，如果不存在则创建
                if not self.conn.bucket_exists(bucket):
                    logging.warning(f"Bucket {bucket} does not exist, creating it...")
                    self.conn.make_bucket(bucket)
                
                r = self.conn.get_object(bucket, filename)
                return r.read()
            except S3Error as e:
                if e.code == "NoSuchBucket":
                    logging.warning(f"Bucket {bucket} does not exist, attempt {i+1}/3")
                    if i < 2:  # 不是最后一次重试
                        try:
                            self.conn.make_bucket(bucket)
                            continue
                        except Exception:
                            logging.exception(f"Failed to create bucket {bucket}")
                elif e.code == "NoSuchKey":
                    logging.warning(f"File {filename} not found in bucket {bucket}")
                    return None
                logging.exception(f"S3Error in get {bucket}/{filename}: {e}")
                if i < 2:  # 不是最后一次重试
                    self.__open__()
                    time.sleep(1)
            except Exception:
                logging.exception(f"Fail to get {bucket}/{filename}")
                if i < 2:  # 不是最后一次重试
                    self.__open__()
                    time.sleep(1)
        return None

    def obj_exist(self, bucket, filename):
        try:
            if not self.conn.bucket_exists(bucket):
                return False
            if self.conn.stat_object(bucket, filename):
                return True
            else:
                return False
        except S3Error as e:
            if e.code in ["NoSuchKey", "NoSuchBucket", "ResourceNotFound"]:
                return False
        except Exception:
            logging.exception(f"obj_exist {bucket}/{filename} got exception")
            return False

    def get_presigned_url(self, bucket, fnm, expires):
        for _ in range(10):
            try:
                return self.conn.get_presigned_url("GET", bucket, fnm, expires)
            except Exception:
                logging.exception(f"Fail to get_presigned {bucket}/{fnm}:")
                self.__open__()
                time.sleep(1)
        return

    def remove_bucket(self, bucket):
        try:
            if self.conn.bucket_exists(bucket):
                objects_to_delete = self.conn.list_objects(bucket, recursive=True)
                for obj in objects_to_delete:
                    self.conn.remove_object(bucket, obj.object_name)
                self.conn.remove_bucket(bucket)
        except Exception:
            logging.exception(f"Fail to remove bucket {bucket}")

