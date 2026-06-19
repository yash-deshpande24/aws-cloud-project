#!/usr/bin/env python3
"""
ELB Monitor & Manager
Cloud Hosting & Networking Project
Inspect ALB/NLB health, targets, and listeners
"""

import boto3
import json
import argparse
from datetime import datetime, timezone, timedelta


def get_client(region: str):
    return boto3.client("elbv2", region_name=region)


def get_cw_client(region: str):
    return boto3.client("cloudwatch", region_name=region)


def list_load_balancers(client, project: str = None) -> list:
    response = client.describe_load_balancers()
    lbs = []
    for lb in response["LoadBalancers"]:
        tags_resp = client.describe_tags(ResourceArns=[lb["LoadBalancerArn"]])
        tags = {t["Key"]: t["Value"] for tl in tags_resp["TagDescriptions"] for t in tl["Tags"]}
        if project and tags.get("Project") != project:
            continue
        lbs.append({
            "Name": lb["LoadBalancerName"],
            "ARN": lb["LoadBalancerArn"],
            "DNS": lb["DNSName"],
            "Type": lb["Type"],
            "Scheme": lb["Scheme"],
            "State": lb["State"]["Code"],
            "VpcId": lb["VpcId"],
            "CreatedAt": lb["CreatedTime"].isoformat(),
            "Tags": tags,
        })
    return lbs


def get_target_health(client, target_group_arn: str) -> list:
    response = client.describe_target_health(TargetGroupArn=target_group_arn)
    return [
        {
            "Target": h["Target"]["Id"],
            "Port": h["Target"].get("Port", "N/A"),
            "State": h["TargetHealth"]["State"],
            "Reason": h["TargetHealth"].get("Reason", ""),
            "Description": h["TargetHealth"].get("Description", ""),
        }
        for h in response["TargetHealthDescriptions"]
    ]


def list_target_groups(client, lb_arn: str = None) -> list:
    kwargs = {}
    if lb_arn:
        kwargs["LoadBalancerArn"] = lb_arn
    response = client.describe_target_groups(**kwargs)
    tgs = []
    for tg in response["TargetGroups"]:
        health = get_target_health(client, tg["TargetGroupArn"])
        healthy = sum(1 for h in health if h["State"] == "healthy")
        tgs.append({
            "TargetGroupName": tg["TargetGroupName"],
            "ARN": tg["TargetGroupArn"],
            "Protocol": tg["Protocol"],
            "Port": tg["Port"],
            "HealthyTargets": healthy,
            "TotalTargets": len(health),
            "Targets": health,
        })
    return tgs


def get_alb_metrics(cw_client, lb_name: str, lb_arn: str, minutes: int = 60) -> dict:
    """Fetch key ALB CloudWatch metrics for the last N minutes."""
    end = datetime.now(timezone.utc)
    start = end - timedelta(minutes=minutes)

    lb_dim_value = "/".join(lb_arn.split("/")[-3:])

    def get_metric(metric_name, stat="Sum"):
        resp = cw_client.get_metric_statistics(
            Namespace="AWS/ApplicationELB",
            MetricName=metric_name,
            Dimensions=[{"Name": "LoadBalancer", "Value": lb_dim_value}],
            StartTime=start,
            EndTime=end,
            Period=300,
            Statistics=[stat],
        )
        datapoints = resp.get("Datapoints", [])
        if datapoints:
            return sum(d[stat] for d in datapoints)
        return 0

    return {
        "RequestCount": get_metric("RequestCount"),
        "HTTPCode_2XX": get_metric("HTTPCode_Target_2XX_Count"),
        "HTTPCode_4XX": get_metric("HTTPCode_Target_4XX_Count"),
        "HTTPCode_5XX": get_metric("HTTPCode_Target_5XX_Count"),
        "TargetResponseTime_Avg": get_metric("TargetResponseTime", "Average"),
        "ActiveConnections": get_metric("ActiveConnectionCount", "Average"),
        "PeriodMinutes": minutes,
    }


def health_check(client, cw_client, project: str = None):
    """Full health report of all load balancers."""
    lbs = list_load_balancers(client, project)

    print(f"\n{'='*60}")
    print(f" ELB HEALTH REPORT — {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'='*60}")

    for lb in lbs:
        status_icon = "✅" if lb["State"] == "active" else "❌"
        print(f"\n{status_icon}  {lb['Name']} ({lb['Type'].upper()})")
        print(f"   DNS:    {lb['DNS']}")
        print(f"   State:  {lb['State']}")
        print(f"   Scheme: {lb['Scheme']}")

        tgs = list_target_groups(client, lb["ARN"])
        for tg in tgs:
            health_pct = (tg["HealthyTargets"] / tg["TotalTargets"] * 100) if tg["TotalTargets"] > 0 else 0
            icon = "✅" if health_pct == 100 else ("⚠️" if health_pct > 0 else "❌")
            print(f"   {icon} Target Group: {tg['TargetGroupName']} — {tg['HealthyTargets']}/{tg['TotalTargets']} healthy")
            for t in tg["Targets"]:
                t_icon = "✅" if t["State"] == "healthy" else "❌"
                print(f"      {t_icon} {t['Target']}:{t['Port']} — {t['State']} {t['Reason']}")

        try:
            metrics = get_alb_metrics(cw_client, lb["Name"], lb["ARN"])
            print(f"   📊 Last {metrics['PeriodMinutes']}min Metrics:")
            print(f"      Requests:       {int(metrics['RequestCount'])}")
            print(f"      2xx:            {int(metrics['HTTPCode_2XX'])}")
            print(f"      4xx:            {int(metrics['HTTPCode_4XX'])}")
            print(f"      5xx:            {int(metrics['HTTPCode_5XX'])}")
            print(f"      Avg Latency:    {metrics['TargetResponseTime_Avg']:.4f}s")
        except Exception as e:
            print(f"   ⚠️  Could not fetch CloudWatch metrics: {e}")

    print(f"\n{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(description="ELB Monitor")
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--project", help="Filter by project tag")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("list", help="List all load balancers")
    subparsers.add_parser("health", help="Full health report")

    tg_p = subparsers.add_parser("targets", help="List target groups for an LB")
    tg_p.add_argument("lb_arn", help="Load balancer ARN")

    args = parser.parse_args()
    client = get_client(args.region)
    cw_client = get_cw_client(args.region)

    if args.command == "list":
        lbs = list_load_balancers(client, args.project)
        print(json.dumps(lbs, indent=2))
    elif args.command == "health":
        health_check(client, cw_client, args.project)
    elif args.command == "targets":
        tgs = list_target_groups(client, args.lb_arn)
        print(json.dumps(tgs, indent=2))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
