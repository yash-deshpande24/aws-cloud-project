#!/usr/bin/env python3
"""
EC2 Instance Manager
Cloud Hosting & Networking Project
Manage EC2 instances: list, start, stop, describe
"""

import boto3
import argparse
import json
import sys
from datetime import datetime


def get_ec2_client(region: str = "us-east-1"):
    return boto3.client("ec2", region_name=region)


def list_instances(client, project_name: str = None):
    """List all EC2 instances, optionally filtered by project tag."""
    filters = []
    if project_name:
        filters.append({"Name": "tag:Project", "Values": [project_name]})

    response = client.describe_instances(Filters=filters)
    instances = []

    for reservation in response["Reservations"]:
        for inst in reservation["Instances"]:
            name = next(
                (t["Value"] for t in inst.get("Tags", []) if t["Key"] == "Name"),
                "N/A",
            )
            instances.append(
                {
                    "InstanceId": inst["InstanceId"],
                    "Name": name,
                    "State": inst["State"]["Name"],
                    "Type": inst["InstanceType"],
                    "PublicIP": inst.get("PublicIpAddress", "N/A"),
                    "PrivateIP": inst.get("PrivateIpAddress", "N/A"),
                    "LaunchTime": inst["LaunchTime"].isoformat(),
                }
            )

    return instances


def start_instance(client, instance_id: str):
    """Start a stopped EC2 instance."""
    response = client.start_instances(InstanceIds=[instance_id])
    return response["StartingInstances"][0]


def stop_instance(client, instance_id: str):
    """Stop a running EC2 instance."""
    response = client.stop_instances(InstanceIds=[instance_id])
    return response["StoppingInstances"][0]


def describe_instance(client, instance_id: str):
    """Get detailed info about a specific EC2 instance."""
    response = client.describe_instances(InstanceIds=[instance_id])
    inst = response["Reservations"][0]["Instances"][0]
    return {
        "InstanceId": inst["InstanceId"],
        "State": inst["State"]["Name"],
        "Type": inst["InstanceType"],
        "AMI": inst["ImageId"],
        "KeyPair": inst.get("KeyName", "N/A"),
        "PublicIP": inst.get("PublicIpAddress", "N/A"),
        "PrivateIP": inst.get("PrivateIpAddress", "N/A"),
        "SubnetId": inst.get("SubnetId", "N/A"),
        "VpcId": inst.get("VpcId", "N/A"),
        "LaunchTime": inst["LaunchTime"].isoformat(),
        "Tags": {t["Key"]: t["Value"] for t in inst.get("Tags", [])},
        "SecurityGroups": [sg["GroupId"] for sg in inst.get("SecurityGroups", [])],
    }


def main():
    parser = argparse.ArgumentParser(description="EC2 Instance Manager")
    parser.add_argument("--region", default="us-east-1", help="AWS region")
    parser.add_argument("--project", help="Filter by project name tag")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("list", help="List all instances")
    start_p = subparsers.add_parser("start", help="Start an instance")
    start_p.add_argument("instance_id", help="EC2 instance ID")
    stop_p = subparsers.add_parser("stop", help="Stop an instance")
    stop_p.add_argument("instance_id", help="EC2 instance ID")
    desc_p = subparsers.add_parser("describe", help="Describe an instance")
    desc_p.add_argument("instance_id", help="EC2 instance ID")

    args = parser.parse_args()
    client = get_ec2_client(args.region)

    if args.command == "list" or args.command is None:
        instances = list_instances(client, args.project)
        print(json.dumps(instances, indent=2))

    elif args.command == "start":
        result = start_instance(client, args.instance_id)
        print(f"Starting instance {args.instance_id}: {result['CurrentState']['Name']}")

    elif args.command == "stop":
        result = stop_instance(client, args.instance_id)
        print(f"Stopping instance {args.instance_id}: {result['CurrentState']['Name']}")

    elif args.command == "describe":
        info = describe_instance(client, args.instance_id)
        print(json.dumps(info, indent=2))

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
