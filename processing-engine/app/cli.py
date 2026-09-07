from __future__ import annotations

import argparse
import asyncio
import json
import sys

import httpx


def main() -> None:
    parser = argparse.ArgumentParser(description="Processing Engine CLI")
    parser.add_argument("--base-url", default="http://localhost:8000", help="API base URL")
    parser.add_argument("--api-key", default="dev-key", help="API key")

    sub = parser.add_subparsers(dest="command")

    # Pipeline commands
    sub.add_parser("pipelines", help="List pipelines")
    p_create = sub.add_parser("create-pipeline", help="Create pipeline from JSON file")
    p_create.add_argument("file", help="JSON config file path")

    # Job commands
    j_submit = sub.add_parser("submit", help="Submit job")
    j_submit.add_argument("--pipeline-id", required=True, help="Pipeline UUID")
    j_submit.add_argument("--content", help="Text content to process")
    j_submit.add_argument("--url", help="Source URL")
    j_submit.add_argument("--file", help="File with content")

    j_status = sub.add_parser("status", help="Check job status")
    j_status.add_argument("job_id", help="Job UUID")

    j_result = sub.add_parser("result", help="Get job result")
    j_result.add_argument("job_id", help="Job UUID")

    # Stats/costs
    sub.add_parser("stats", help="Get processing stats")
    sub.add_parser("costs", help="Get cost report")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    asyncio.run(_dispatch(args))


async def _dispatch(args: argparse.Namespace) -> None:
    headers = {"X-Api-Key": args.api_key}
    base = args.base_url.rstrip("/")

    async with httpx.AsyncClient(headers=headers, timeout=30.0) as client:
        if args.command == "pipelines":
            resp = await client.get(f"{base}/v1/pipelines")
            resp.raise_for_status()
            for p in resp.json():
                print(f"  {p['id']}  {p['name']}  v{p['version']}  active={p['is_active']}")

        elif args.command == "create-pipeline":
            with open(args.file) as f:
                config = json.load(f)
            resp = await client.post(f"{base}/v1/pipelines", json=config)
            resp.raise_for_status()
            data = resp.json()
            print(f"Pipeline created: {data['id']} ({data['name']})")

        elif args.command == "submit":
            content = args.content
            if args.file:
                with open(args.file) as f:
                    content = f.read()
            if not content and not args.url:
                print("Error: --content or --url or --file required")
                sys.exit(1)

            payload = {
                "pipeline_id": args.pipeline_id,
                "items": [{"content": content, "source_url": args.url}],
            }
            resp = await client.post(f"{base}/v1/jobs", json=payload)
            resp.raise_for_status()
            data = resp.json()
            print(f"Job submitted: {data['id']} (status={data['status']})")

        elif args.command == "status":
            resp = await client.get(f"{base}/v1/jobs/{args.job_id}")
            resp.raise_for_status()
            data = resp.json()
            print(
                f"Job {data['id']}: {data['status']} ({data['items_completed']}/{data['items_total']} done)"
            )

        elif args.command == "result":
            resp = await client.get(f"{base}/v1/jobs/{args.job_id}/result")
            resp.raise_for_status()
            print(json.dumps(resp.json(), indent=2, ensure_ascii=False))

        elif args.command == "stats":
            resp = await client.get(f"{base}/v1/stats")
            resp.raise_for_status()
            data = resp.json()
            print(
                f"Jobs: {data['total_jobs']} | Items: {data['total_items']} | "
                f"Success: {data['success_rate']:.1f}% | Cost: ${data['total_cost_usd']:.4f}"
            )

        elif args.command == "costs":
            resp = await client.get(f"{base}/v1/costs")
            resp.raise_for_status()
            data = resp.json()
            print(f"Total cost: ${data['total_cost_usd']:.4f} ({data['total_calls']} calls)")
            for item in data.get("breakdown", []):
                print(
                    f"  {item['label']}: ${item['total_cost_usd']:.4f} ({item['total_calls']} calls)"
                )


if __name__ == "__main__":
    main()
