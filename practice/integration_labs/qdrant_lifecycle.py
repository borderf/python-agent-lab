"""Exercise Qdrant persistence and authorization filters with hand vectors."""

import argparse
from pathlib import Path

from qdrant_client import QdrantClient, models


def visible(client, tenant):
    result = client.query_points(
        "policies", query=[1.0, 0.0], limit=10,
        query_filter=models.Filter(must=[
            models.FieldCondition(key="tenant", match=models.MatchValue(value=tenant)),
            models.FieldCondition(key="active", match=models.MatchValue(value=True)),
        ]),
    )
    return [point.payload["source"] for point in result.points]


def run(folder: Path):
    folder.mkdir(parents=True, exist_ok=True)
    client = QdrantClient(path=str(folder))
    try:
        if not client.collection_exists("policies"):
            client.create_collection("policies", vectors_config=models.VectorParams(size=2, distance=models.Distance.COSINE))
        client.upsert("policies", points=[
            models.PointStruct(id=1, vector=[1.0, 0.0], payload={"source": "a-v1", "tenant": "a", "active": True}),
            models.PointStruct(id=2, vector=[1.0, 0.0], payload={"source": "b-v1", "tenant": "b", "active": True}),
        ], wait=True)
        assert visible(client, "a") == ["a-v1"]
        client.upsert("policies", points=[models.PointStruct(
            id=3, vector=[1.0, 0.0], payload={"source": "a-v2", "tenant": "a", "active": False})], wait=True)
        assert visible(client, "a") == ["a-v1"]
        client.set_payload("policies", payload={"active": False}, points=[1], wait=True)
        client.set_payload("policies", payload={"active": True}, points=[3], wait=True)
        assert visible(client, "a") == ["a-v2"]
    finally:
        client.close()
    client = QdrantClient(path=str(folder))
    try:
        assert visible(client, "a") == ["a-v2"]
        client.delete("policies", points_selector=models.PointIdsList(points=[1, 3]), wait=True)
        assert visible(client, "a") == []
        assert visible(client, "b") == ["b-v1"]
    finally:
        client.close()
    print("PASS: actual local Qdrant upsert, filters, reopen, version switch, deletion")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--folder", type=Path, default=Path(".learning-labs/qdrant"))
    run(parser.parse_args().folder)
