#!/usr/bin/env python3
"""
S3 Bucket Manager
Cloud Hosting & Networking Project
Upload, download, sync, and manage S3 buckets
"""

import boto3
import os
import sys
import argparse
import hashlib
from pathlib import Path
from botocore.exceptions import ClientError


def get_s3_client(region: str = "us-east-1"):
    return boto3.client("s3", region_name=region)


def upload_file(client, file_path: str, bucket: str, s3_key: str = None, public: bool = False):
    """Upload a single file to S3."""
    if s3_key is None:
        s3_key = os.path.basename(file_path)

    extra_args = {}
    if public:
        extra_args["ACL"] = "public-read"

    # Set content type
    import mimetypes
    content_type, _ = mimetypes.guess_type(file_path)
    if content_type:
        extra_args["ContentType"] = content_type

    try:
        client.upload_file(file_path, bucket, s3_key, ExtraArgs=extra_args if extra_args else None)
        print(f"Uploaded: {file_path} → s3://{bucket}/{s3_key}")
        return True
    except ClientError as e:
        print(f"Error uploading {file_path}: {e}")
        return False


def download_file(client, bucket: str, s3_key: str, local_path: str):
    """Download a file from S3."""
    os.makedirs(os.path.dirname(local_path) or ".", exist_ok=True)
    try:
        client.download_file(bucket, s3_key, local_path)
        print(f"Downloaded: s3://{bucket}/{s3_key} → {local_path}")
        return True
    except ClientError as e:
        print(f"Error downloading {s3_key}: {e}")
        return False


def sync_directory(client, local_dir: str, bucket: str, prefix: str = ""):
    """Sync a local directory to S3."""
    local_path = Path(local_dir)
    uploaded = 0
    failed = 0

    for file_path in local_path.rglob("*"):
        if file_path.is_file():
            relative = file_path.relative_to(local_path)
            s3_key = f"{prefix}/{relative}".lstrip("/") if prefix else str(relative)
            if upload_file(client, str(file_path), bucket, s3_key):
                uploaded += 1
            else:
                failed += 1

    print(f"\nSync complete: {uploaded} uploaded, {failed} failed.")


def list_objects(client, bucket: str, prefix: str = ""):
    """List objects in an S3 bucket."""
    paginator = client.get_paginator("list_objects_v2")
    objects = []

    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            objects.append({
                "Key": obj["Key"],
                "Size": obj["Size"],
                "LastModified": obj["LastModified"].isoformat(),
                "StorageClass": obj["StorageClass"],
            })

    return objects


def delete_object(client, bucket: str, s3_key: str):
    """Delete an object from S3."""
    client.delete_object(Bucket=bucket, Key=s3_key)
    print(f"Deleted: s3://{bucket}/{s3_key}")


def get_bucket_size(client, bucket: str):
    """Calculate total size of a bucket."""
    paginator = client.get_paginator("list_objects_v2")
    total_size = 0
    total_count = 0

    for page in paginator.paginate(Bucket=bucket):
        for obj in page.get("Contents", []):
            total_size += obj["Size"]
            total_count += 1

    return {
        "bucket": bucket,
        "total_objects": total_count,
        "total_size_bytes": total_size,
        "total_size_mb": round(total_size / (1024 * 1024), 2),
    }


def generate_presigned_url(client, bucket: str, s3_key: str, expiry: int = 3600):
    """Generate a pre-signed URL for temporary access."""
    url = client.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": s3_key},
        ExpiresIn=expiry,
    )
    return url


def main():
    parser = argparse.ArgumentParser(description="S3 Bucket Manager")
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--bucket", required=True, help="S3 bucket name")
    subparsers = parser.add_subparsers(dest="command")

    # Upload
    up = subparsers.add_parser("upload", help="Upload a file")
    up.add_argument("file", help="Local file path")
    up.add_argument("--key", help="S3 object key")
    up.add_argument("--public", action="store_true")

    # Download
    dl = subparsers.add_parser("download", help="Download a file")
    dl.add_argument("key", help="S3 object key")
    dl.add_argument("local", help="Local destination path")

    # Sync
    sy = subparsers.add_parser("sync", help="Sync directory to S3")
    sy.add_argument("directory", help="Local directory")
    sy.add_argument("--prefix", default="", help="S3 key prefix")

    # List
    ls = subparsers.add_parser("list", help="List objects")
    ls.add_argument("--prefix", default="")

    # Size
    subparsers.add_parser("size", help="Get bucket size")

    # Presign
    ps = subparsers.add_parser("presign", help="Generate pre-signed URL")
    ps.add_argument("key", help="S3 object key")
    ps.add_argument("--expiry", type=int, default=3600)

    args = parser.parse_args()
    client = get_s3_client(args.region)

    if args.command == "upload":
        upload_file(client, args.file, args.bucket, args.key, args.public)
    elif args.command == "download":
        download_file(client, args.bucket, args.key, args.local)
    elif args.command == "sync":
        sync_directory(client, args.directory, args.bucket, args.prefix)
    elif args.command == "list":
        objects = list_objects(client, args.bucket, args.prefix)
        for obj in objects:
            print(f"{obj['Key']:60s} {obj['Size']:>12} B  {obj['LastModified']}")
    elif args.command == "size":
        info = get_bucket_size(client, args.bucket)
        print(f"Bucket: {info['bucket']}")
        print(f"Objects: {info['total_objects']}")
        print(f"Size: {info['total_size_mb']} MB")
    elif args.command == "presign":
        url = generate_presigned_url(client, args.bucket, args.key, args.expiry)
        print(url)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
