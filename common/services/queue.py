import pika
import json
import os
import logging
import asyncio
import aio_pika
from aio_pika import IncomingMessage

RABBIT_HOST = os.getenv("RABBIT_HOST", "rabbitmq")
SERVICE_NAME="[Queue]"


semaphore = asyncio.Semaphore(1)


def get_connection():
    return pika.BlockingConnection(
        pika.ConnectionParameters(host="rabbitmq", port=5672)
    )


def enqueue_task(task: dict, queue_name: str):
    connection = get_connection()
    channel = connection.channel()

    channel.queue_declare(queue=queue_name, durable=True)

    channel.basic_publish(
        exchange="",
        routing_key=queue_name,
        body=json.dumps(task),
        properties=pika.BasicProperties(
            delivery_mode=2
        )
    )

    connection.close()



async def async_consume(callback, queue_name, prefetch):
    prefetch = int(prefetch)
    """Асинхронное потребление сообщений из очереди RabbitMQ с контролем параллелизма"""
    while True:  # reconnect loop
        try:
            connection = await aio_pika.connect_robust(RABBIT_HOST, heartbeat=1200)
            channel = await connection.channel()
            await channel.set_qos(prefetch_count=prefetch)

            queue = await channel.declare_queue(queue_name, durable=True)
            logging.info(f"{SERVICE_NAME} Consuming from {queue_name}")

            async def wrapped_callback(in_mes: IncomingMessage):
                async with semaphore:
                    try:
                        await callback(in_mes)
                    except Exception:
                        logging.exception(f"{SERVICE_NAME} Failed processing message: {in_mes.body.decode()}")

            # Асинхронная итерация по сообщениям
            async with queue.iterator() as queue_iter:
                async for message in queue_iter:
                    asyncio.create_task(wrapped_callback(message))

        except Exception:
            logging.exception(f"{SERVICE_NAME} Connection lost. Reconnecting in 5s...")
            await asyncio.sleep(5)


async def publish(queue_name: str, message: dict):
    connection = await aio_pika.connect_robust(RABBIT_HOST)
    channel = await connection.channel()

    await channel.default_exchange.publish(
        aio_pika.Message(
            body=json.dumps(message).encode(),
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT
        ),
        routing_key=queue_name
    )

    await connection.close()