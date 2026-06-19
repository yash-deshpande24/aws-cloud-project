#!/usr/bin/env python3
"""
IAM Auditor & User Manager
Cloud Hosting & Networking Project
List users, roles, policies, and detect security issues
"""

import boto3
import json
import argparse
from datetime import datetime, timezone


def get_client():
    return boto3.client("iam")


def list_users(client) -> list:
    paginator = client.get_paginator("list_users")
    users = []
    for page in paginator.paginate():
        for u in page["Users"]:
            # Check MFA
            mfa = client.list_mfa_devices(UserName=u["UserName"])
            has_mfa = len(mfa["MFADevices"]) > 0

            # Check access keys
            keys = client.list_access_keys(UserName=u["UserName"])
            active_keys = [k for k in keys["AccessKeyMetadata"] if k["Status"] == "Active"]

            users.append({
                "UserName": u["UserName"],
                "UserId": u["UserId"],
                "ARN": u["Arn"],
                "CreatedAt": u["CreateDate"].isoformat(),
                "LastLogin": u.get("PasswordLastUsed", "Never").isoformat() if hasattr(u.get("PasswordLastUsed", ""), "isoformat") else "Never",
                "MFAEnabled": has_mfa,
                "ActiveAccessKeys": len(active_keys),
            })
    return users


def list_roles(client) -> list:
    paginator = client.get_paginator("list_roles")
    roles = []
    for page in paginator.paginate():
        for r in page["Roles"]:
            roles.append({
                "RoleName": r["RoleName"],
                "RoleId": r["RoleId"],
                "ARN": r["Arn"],
                "CreatedAt": r["CreateDate"].isoformat(),
                "MaxSessionDuration": r.get("MaxSessionDuration", 3600),
                "TrustPolicy": json.dumps(r["AssumeRolePolicyDocument"]),
            })
    return roles


def list_policies(client, scope: str = "Local") -> list:
    paginator = client.get_paginator("list_policies")
    policies = []
    for page in paginator.paginate(Scope=scope):
        for p in page["Policies"]:
            policies.append({
                "PolicyName": p["PolicyName"],
                "ARN": p["Arn"],
                "AttachmentCount": p["AttachmentCount"],
                "CreatedAt": p["CreateDate"].isoformat(),
                "UpdatedAt": p["UpdateDate"].isoformat(),
            })
    return policies


def audit_users(client) -> list:
    """Identify IAM security issues for users."""
    users = list_users(client)
    issues = []

    for u in users:
        # No MFA
        if not u["MFAEnabled"]:
            issues.append({
                "Severity": "HIGH",
                "User": u["UserName"],
                "Issue": "MFA not enabled",
            })

        # Multiple access keys
        if u["ActiveAccessKeys"] > 1:
            issues.append({
                "Severity": "MEDIUM",
                "User": u["UserName"],
                "Issue": f"{u['ActiveAccessKeys']} active access keys (rotate regularly)",
            })

        # Never logged in (stale users)
        if u["LastLogin"] == "Never" and u["ActiveAccessKeys"] == 0:
            issues.append({
                "Severity": "LOW",
                "User": u["UserName"],
                "Issue": "User has never logged in and has no access keys (consider removing)",
            })

    return issues


def create_role_policy(role_name: str, s3_bucket: str) -> dict:
    """Generate a least-privilege S3 policy document for a role."""
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "S3ReadWrite",
                "Effect": "Allow",
                "Action": [
                    "s3:GetObject",
                    "s3:PutObject",
                    "s3:DeleteObject",
                ],
                "Resource": f"arn:aws:s3:::{s3_bucket}/*",
            },
            {
                "Sid": "S3ListBucket",
                "Effect": "Allow",
                "Action": "s3:ListBucket",
                "Resource": f"arn:aws:s3:::{s3_bucket}",
            },
        ],
    }


def main():
    parser = argparse.ArgumentParser(description="IAM Auditor")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("list-users", help="List all IAM users")
    subparsers.add_parser("list-roles", help="List all IAM roles")
    subparsers.add_parser("list-policies", help="List customer-managed policies")
    subparsers.add_parser("audit", help="Run IAM security audit")

    gp = subparsers.add_parser("gen-policy", help="Generate S3 least-privilege policy")
    gp.add_argument("--role", required=True)
    gp.add_argument("--bucket", required=True)

    args = parser.parse_args()
    client = get_client()

    if args.command == "list-users":
        users = list_users(client)
        print(json.dumps(users, indent=2))

    elif args.command == "list-roles":
        roles = list_roles(client)
        print(json.dumps(roles, indent=2))

    elif args.command == "list-policies":
        policies = list_policies(client)
        print(json.dumps(policies, indent=2))

    elif args.command == "audit":
        issues = audit_users(client)
        if not issues:
            print("✅ No IAM security issues detected.")
        else:
            print(f"⚠️  {len(issues)} IAM issue(s) found:\n")
            for issue in issues:
                print(f"  [{issue['Severity']:8s}] {issue['User']:30s} — {issue['Issue']}")

    elif args.command == "gen-policy":
        policy = create_role_policy(args.role, args.bucket)
        print(json.dumps(policy, indent=2))

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
