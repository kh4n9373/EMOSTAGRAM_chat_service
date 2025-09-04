
from confluent_kafka import Producer
import json, time

class KafkaProducerClient:
    def __init__(self, bootstrap_servers: str):
        self.producer = Producer({
            "bootstrap.servers": bootstrap_servers,
            "enable.idempotence": False,  
            "acks": "all",
            "linger.ms": 5,
            "batch.num.messages": 1000,
            "retries": 5,
        })

    def send(self, topic: str, key: str, value: dict, timeout: float = 0.0):
        payload = json.dumps(value, separators=(",", ":"), ensure_ascii=False)
        err_holder = {"err": None}

        def _cb(err, msg):
            err_holder["err"] = err

        self.producer.produce(topic=topic, key=key, value=payload, callback=_cb)
        # fire-and-forget to avoid blocking request latency; errors will appear in broker metrics/logs
        self.producer.poll(0)

    def flush(self):
        self.producer.flush(5.0)
