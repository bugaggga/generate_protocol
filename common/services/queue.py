import json
import os
import logging
import asyncio
import aio_pika
from aio_pika.abc import AbstractIncomingMessage

RABBIT_HOST = os.getenv("RABBIT_HOST", "rabbitmq")
SERVICE_NAME="[Queue]"

semaphore = asyncio.Semaphore(1)


async def async_consume(callback, queue_name, prefetch):
    prefetch = int(prefetch)
    semaphore = asyncio.Semaphore(prefetch)  # создаём на работающем loop, согласуем с prefetch
    tasks: set[asyncio.Task] = set()
    #prefetch = int(prefetch)
    """Асинхронное потребление сообщений из очереди RabbitMQ с контролем параллелизма"""
    while True:  # reconnect loop
        try:
            connection = await aio_pika.connect_robust(RABBIT_HOST, heartbeat=1200)
            async with connection:
                channel = await connection.channel()
                await channel.set_qos(prefetch_count=prefetch)

                queue = await channel.declare_queue(queue_name, durable=True)
                logging.info(f"{SERVICE_NAME} Consuming from {queue_name}")

                async def wrapped_callback(in_mes: AbstractIncomingMessage):
                    async with semaphore:
                        try:
                            await callback(in_mes)
                        except Exception:
                            logging.exception(f"{SERVICE_NAME} Failed processing message: {in_mes.body.decode()}")
                        finally:
                            semaphore.release()

                # Асинхронная итерация по сообщениям
                async with queue.iterator() as queue_iter:
                    async for message in queue_iter:
                        await semaphore.acquire()  # backpressure ДО запуска задачи
                        task = asyncio.create_task(wrapped_callback(message))
                        tasks.add(task)  # сильная ссылка — задачу не соберёт GC
                        task.add_done_callback(tasks.discard)

        except asyncio.CancelledError:
            raise  # пропускаем отмену для graceful shutdown
        except Exception:
            logging.exception(f"{SERVICE_NAME} Connection lost. Reconnecting in 5s...")
            await asyncio.sleep(5)

async def get_channel() -> aio_pika.abc.AbstractChannel:
    global _conn, _channel
    if _conn is None or _conn.is_closed:
        _conn = await aio_pika.connect_robust(RABBIT_HOST)   # авто-переподключение
        _channel = await _conn.channel()                       # publisher_confirms=True по умолчанию
        # robust-канал переобъявит очереди после реконнекта автоматически
        for q in ("recognize_tasks", "llm_tasks"):
            await _channel.declare_queue(q, durable=True)      # durable: переживёт рестарт брокера
    return _channel

async def publish(queue_name: str, message: dict):
    connection = await aio_pika.connect_robust(RABBIT_HOST)
    channel = await connection.channel()

    await channel.default_exchange.publish(
        aio_pika.Message(
            body=json.dumps(message).encode(),
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT
        ),
        routing_key=queue_name,
        mandatory=True
    )

    #await connection.close()