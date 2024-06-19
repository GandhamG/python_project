from dataclasses import dataclass


@dataclass
class ScgS3FileConfig:
    aws_s3_bucket_name: str
    aws_s3_access_key: str
    aws_s3_secret_key: str
    aws_s3_file_overwrite: bool
    aws_s3_region_name: str
