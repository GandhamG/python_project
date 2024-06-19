import logging

from django.conf import settings
from storages.backends.s3boto3 import S3Boto3Storage


class EOrderingS3Storage(S3Boto3Storage):
    def __init__(self, *args, **kwargs):
        try:
            self.bucket_name = settings.AWS_STORAGE_BUCKET_NAME
            self.secret_key = settings.AWS_SECRET_ACCESS_KEY
            self.access_key = settings.AWS_ACCESS_KEY_ID
            self.region_name = settings.AWS_S3_REGION_NAME
            self.file_overwrite = settings.AWS_S3_FILE_OVERWRITE
        except Exception:
            logging.info("Please setup scg.s3_file plugin")

        super().__init__(*args, **kwargs)
