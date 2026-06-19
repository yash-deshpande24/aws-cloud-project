#!/usr/bin/env python3
"""
VPC Inspector & Audit Tool
Cloud Hosting & Networking Project
Inspect subnets, route tables, security groups, NACLs
"""

import boto3
import json
import argparse


def get_client(region: str):
    return boto3.client("ec2", region_name=region)


def describe_vpc(client, vpc_id: str) -> dict:
    response = client.describe_vpcs(VpcIds=[vpc_id])
    vpc = response["Vpcs"][0]
    return {
        "VpcId": vpc["VpcId"],
        "CidrBlock": vpc["CidrBlock"],
        "State": vpc["State"],
        "IsDefault": vpc["IsDefault"],
        "DnsSupport": vpc.get("EnableDnsSupport", "Unknown"),
        "Tags": {t["Key"]: t["Value"] for t in vpc.get("Tags", [])},
    }


def list_subnets(client, vpc_id: str) -> list:
    response = client.describe_subnets(
        Filters=[{"Name": "vpc-id", "Values": [vpc_id]}]
    )
    subnets = []
    for s in response["Subnets"]:
        name = next((t["Value"] for t in s.get("Tags", []) if t["Key"] == "Name"), "N/A")
        subnets.append({
            "SubnetId": s["SubnetId"],
            "Name": name,
            "CidrBlock": s["CidrBlock"],
            "AZ": s["AvailabilityZone"],
            "AvailableIPs": s["AvailableIpAddressCount"],
            "Public": s["MapPublicIpOnLaunch"],
        })
    return subnets


def list_route_tables(client, vpc_id: str) -> list:
    response = client.describe_route_tables(
        Filters=[{"Name": "vpc-id", "Values": [vpc_id]}]
    )
    tables = []
    for rt in response["RouteTables"]:
        name = next((t["Value"] for t in rt.get("Tags", []) if t["Key"] == "Name"), "N/A")
        tables.append({
            "RouteTableId": rt["RouteTableId"],
            "Name": name,
            "Routes": [
                {
                    "Destination": r.get("DestinationCidrBlock", r.get("DestinationPrefixListId")),
                    "Target": r.get("GatewayId") or r.get("NatGatewayId") or r.get("InstanceId") or "local",
                    "State": r["State"],
                }
                for r in rt["Routes"]
            ],
            "Associations": [a["SubnetId"] for a in rt.get("Associations", []) if "SubnetId" in a],
        })
    return tables


def list_security_groups(client, vpc_id: str) -> list:
    response = client.describe_security_groups(
        Filters=[{"Name": "vpc-id", "Values": [vpc_id]}]
    )
    sgs = []
    for sg in response["SecurityGroups"]:
        sgs.append({
            "GroupId": sg["GroupId"],
            "Name": sg["GroupName"],
            "Description": sg["Description"],
            "InboundRules": len(sg["IpPermissions"]),
            "OutboundRules": len(sg["IpPermissionsEgress"]),
            "Inbound": [
                {
                    "Protocol": r.get("IpProtocol"),
                    "FromPort": r.get("FromPort"),
                    "ToPort": r.get("ToPort"),
                    "Sources": [ip["CidrIp"] for ip in r.get("IpRanges", [])],
                }
                for r in sg["IpPermissions"]
            ],
        })
    return sgs


def audit_security_groups(client, vpc_id: str) -> list:
    """Identify security group rules open to the world."""
    sgs = list_security_groups(client, vpc_id)
    warnings = []
    for sg in sgs:
        for rule in sg["Inbound"]:
            if "0.0.0.0/0" in rule.get("Sources", []):
                port = rule.get("FromPort")
                if port in [22, 3389]:
                    warnings.append({
                        "Severity": "HIGH",
                        "GroupId": sg["GroupId"],
                        "GroupName": sg["Name"],
                        "Issue": f"Port {port} open to 0.0.0.0/0",
                    })
                elif rule.get("Protocol") == "-1":
                    warnings.append({
                        "Severity": "CRITICAL",
                        "GroupId": sg["GroupId"],
                        "GroupName": sg["Name"],
                        "Issue": "All traffic open to 0.0.0.0/0",
                    })
    return warnings


def full_audit(client, vpc_id: str):
    print(f"\n{'='*60}")
    print(f" VPC AUDIT REPORT: {vpc_id}")
    print(f"{'='*60}\n")

    vpc = describe_vpc(client, vpc_id)
    print("VPC Details:")
    print(json.dumps(vpc, indent=2))

    subnets = list_subnets(client, vpc_id)
    print(f"\nSubnets ({len(subnets)}):")
    for s in subnets:
        pub = "PUBLIC" if s["Public"] else "PRIVATE"
        print(f"  {s['SubnetId']}  {s['CidrBlock']:18s}  {pub:8s}  {s['AZ']}  ({s['AvailableIPs']} IPs free)")

    rts = list_route_tables(client, vpc_id)
    print(f"\nRoute Tables ({len(rts)}):")
    for rt in rts:
        print(f"  {rt['RouteTableId']} — {rt['Name']}")
        for r in rt["Routes"]:
            print(f"    {r['Destination']:22s} → {r['Target']:30s} [{r['State']}]")

    warnings = audit_security_groups(client, vpc_id)
    if warnings:
        print(f"\n⚠️  Security Warnings ({len(warnings)}):")
        for w in warnings:
            print(f"  [{w['Severity']}] {w['GroupId']} ({w['GroupName']}): {w['Issue']}")
    else:
        print("\n✅ No critical security group issues found.")

    print(f"\n{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(description="VPC Inspector")
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--vpc-id", required=True, help="VPC ID to inspect")
    parser.add_argument("--audit", action="store_true", help="Run full security audit")
    args = parser.parse_args()

    client = get_client(args.region)

    if args.audit:
        full_audit(client, args.vpc_id)
    else:
        vpc = describe_vpc(client, args.vpc_id)
        subnets = list_subnets(client, args.vpc_id)
        print(json.dumps({"vpc": vpc, "subnets": subnets}, indent=2))


if __name__ == "__main__":
    main()
