from __future__ import annotations

import json
from confluent_kafka import Consumer
from core.tools.extract import extract_long_term_facts_tool
from config import settings


def run_consumer(group_id: str = "ltm-extract-consumers") -> None:
    conf = {
        "bootstrap.servers": settings.kafka_bootstrap,
        "group.id": group_id,
        "auto.offset.reset": "latest",
        "enable.auto.commit": True,
    }
    c = Consumer(conf)
    c.subscribe(["ltm-extract"])
    print("[ltm_consumer] Started. Subscribed to 'ltm-extract'.")
    try:
        while True:
            msg = c.poll(1.0)
            if msg is None or msg.error():
                continue
            try:
                payload = json.loads(msg.value().decode("utf-8"))
                user_id = payload.get("user_id")
                text = payload.get("message") or ""
                if user_id is None or not text:
                    continue
                print(f"[ltm_consumer] Processing user_id={user_id}")
                facts = extract_long_term_facts_tool.invoke({"user_id": user_id, "message": text})
                try:
                    n = len(facts or [])
                except Exception:
                    n = 0
                if n:
                    # Log up to first 5 facts for readability
                    preview = facts[:5]
                    print(f"[ltm_consumer] Saved {n} fact(s) for user_id={user_id}: {preview}")
                else:
                    print(f"[ltm_consumer] No facts extracted for user_id={user_id}")
            except Exception:
                continue
    finally:
        c.close()

if __name__ == "__main__":
    run_consumer()