
#!/usr/bin/env python3
"""Download books and upload them to a public S3 bucket."""

import logging
import os
import sys
import time
import json
import boto3
import requests
from botocore.exceptions import ClientError

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

s3 = boto3.client("s3", region_name="us-east-1")


def parse_args():
    """Read the three command line arguments."""
    if len(sys.argv) != 4:
        log.error("Usage: stage_books.py LIST INDEX BUCKET")
        sys.exit(1)
    return sys.argv[1], sys.argv[2], sys.argv[3]


def download_books(list_file, dest_dir):
    """Download books from Project Gutenberg."""
    os.makedirs(dest_dir, exist_ok=True)
    paths = []

    try:
        with open(list_file) as f:
            urls = f.readlines()
    except OSError as e:
        log.error(f"Error reading book list: {e}")
        return paths

    for url in urls:
        url = url.strip()
        if not url:
            continue

        name = url.split("/")[-1]
        path = os.path.join(dest_dir, name)

        if os.path.exists(path):
            paths.append(path)
            continue

        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            with open(path, "wb") as f:
                f.write(response.content)
            paths.append(path)
            log.info(f"Downloaded {name}")
        except (requests.RequestException, OSError) as e:
            log.error(f"Error downloading {name}: {e}")

        time.sleep(1)

    return paths


def create_bucket(bucket):
    """Create a bucket if it does not already exist."""
    try:
        s3.head_bucket(Bucket=bucket)
        log.info(f"Bucket already exists: {bucket}")
        return True
    except ClientError as e:
        if e.response["ResponseMetadata"]["HTTPStatusCode"] != 404:
            log.error(f"Error checking bucket: {e}")
            return False

    try:
        s3.create_bucket(Bucket=bucket)
        log.info(f"Created bucket: {bucket}")
        return True
    except ClientError as e:
        log.error(f"Error creating bucket: {e}")
        return False


def make_public(bucket):
    """Make the bucket publicly readable."""
    try:
        s3.put_public_access_block(
            Bucket=bucket,
            PublicAccessBlockConfiguration={
                "BlockPublicAcls": False,
                "IgnorePublicAcls": False,
                "BlockPublicPolicy": False,
                "RestrictPublicBuckets": False
            }
        )

        policy = {
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Principal": "*",
                "Action": "s3:GetObject",
                "Resource": f"arn:aws:s3:::{bucket}/*"
            }]
        }

        s3.put_bucket_policy(Bucket=bucket, Policy=json.dumps(policy))
        log.info(f"Made bucket public: {bucket}")
        return True
    except ClientError as e:
        log.error(f"Error making bucket public: {e}")
        return False


def upload_files(bucket, file_paths):
    """Upload the books to S3."""
    count = 0
    for path in file_paths:
        try:
            with open(path, "rb") as f:
                s3.put_object(
                    Bucket=bucket,
                    Key=os.path.basename(path),
                    Body=f,
                    ContentType="text/plain; charset=utf-8"
                )
            count += 1
            log.info(f"Uploaded {path}")
        except (ClientError, OSError) as e:
            log.error(f"Error uploading {path}: {e}")

    return count


def upload_index(bucket, index_path):
    """Upload the HTML index page."""
    try:
        with open(index_path, "rb") as f:
            s3.put_object(
                Bucket=bucket,
                Key="index.html",
                Body=f,
                ContentType="text/html"
            )
        log.info("Uploaded index.html")
        return True
    except FileNotFoundError:
        log.error(f"File not found: {index_path}")
        return False
    except (ClientError, OSError) as e:
        log.error(f"Error uploading index: {e}")
        return False


def main():
    """Run all the steps."""
    list_file, index_path, bucket = parse_args()

    books = download_books(list_file, "books")
    if not books:
        sys.exit(1)

    if not create_bucket(bucket):
        sys.exit(1)

    if not make_public(bucket):
        sys.exit(1)

    count = upload_files(bucket, books)
    index_ok = upload_index(bucket, index_path)

    if count == len(books) and index_ok:
        log.info("Success!")
        log.info(f"https://{bucket}.s3.amazonaws.com/index.html")
    else:
        log.error("Some files failed to upload")
        sys.exit(1)


if __name__ == "__main__":
    main()
