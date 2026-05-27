import asyncio
import logging

from app.infrastructure.outbox import outbox_loop

logging.basicConfig(level=logging.INFO)


async def main():
    logging.info("[Worker] Starting outbox loop")

    async def run():
        while True:
            try:
                await outbox_loop()
            except Exception:
                logging.exception("[Worker] outbox_loop crashed, restarting in 5s")
                await asyncio.sleep(5)

    await run()
    logging.info("[Worker] Stopped")


if __name__ == "__main__":
    asyncio.run(main())