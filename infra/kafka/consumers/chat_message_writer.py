# workers/chat_message_writer.py
from confluent_kafka import Consumer, KafkaException, KafkaError
import json, os, sys, signal
from core.repositories.conversation import ConversationRepo
from pymongo import UpdateOne, ASCENDING
from config import settings
TOPIC = "chat-messages"

def main():
    repo = ConversationRepo(db_name="EMOSTAGRAM", collection="messages")

    repo.client._MongoManager__database[repo.collection].create_index([("message_id", ASCENDING)], unique=True)

    consumer = Consumer({
        "bootstrap.servers": settings.kafka_bootstrap,
        "group.id": "chat-message-writer",
        "auto.offset.reset": "earliest",
        "enable.auto.commit": False,
        "max.poll.interval.ms": 300000,
    })

    consumer.subscribe([TOPIC])

    running = True
    def shutdown(*_):
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    try:
        while running:
            msg = consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    continue
                raise KafkaException(msg.error())

            try:
                event = json.loads(msg.value().decode("utf-8"))
                if event.get("event_type") != "message.created":
                    consumer.commit(msg) 
                    continue

                repo.client.update_one(
                    repo.collection,
                    filter={"message_id": event["message_id"]},
                    data={"$setOnInsert": {
                        "user_id": event["user_id"],
                        "message_id": event["message_id"],
                        "role": event["role"],
                        "content": event["content"],
                        "created_at": event["created_at"],
                        "correlation_id": event.get("correlation_id"),
                    }},
                )

                consumer.commit(msg)

            except Exception as e:
                print(f"[worker] error processing: {e}")
                consumer.commit(msg)

    finally:
        consumer.close()

if __name__ == "__main__":
    main()
