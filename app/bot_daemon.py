import re
import signal
import logging
from typing import Optional

import discord
import websockets
import os

from discord import User, GroupChannel
from dotenv import load_dotenv
import asyncio

from websocket import WebSocket

from .core.messaging import SocketMessage, SocketScope, SocketSource

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('BotDaemon')
socket: Optional[WebSocket] = None
channel: Optional[GroupChannel] = None
loop = asyncio.get_event_loop()
client = discord.Client(loop=loop)
owner: Optional[User] = None


async def connect_ws():
    global socket
    global channel
    global owner
    async with websockets.connect('ws://localhost:8000/ws/bot') as ws:
        socket = ws
        while True:
            msg = await ws.recv()
            print('websocket receive:', msg)
            m = SocketMessage.from_str(msg)
            if not channel:
                channel = client.get_channel(int(os.getenv('DISCORD_CHANNEL')))

            if m.scope is SocketScope.PUBLIC:
                if channel:
                    if m.source is not SocketSource.BOT:
                        await channel.send(f"#{m.sender}: {m.message}")
            if m.scope is SocketScope.PRIVATE:
                if owner:
                    await owner.send(f"#{m.sender}: {m.message}")


@client.event
async def on_ready():
    logger.info('we should be ready')
    global channel
    global owner
    if not channel:
        channel = client.get_channel(int(os.getenv('DISCORD_CHANNEL')))
    if not owner:
        app_info = await client.application_info()
        owner = app_info.owner

    if not channel:
        logger.error('[discord] cannot connect to discord channel')
    else:
        logger.info('[discord] connected to '+os.getenv('DISCORD_CHANNEL'))


@client.event
async def on_error(evt, *args, **kwargs):
    print("Error encountered", evt)


@client.event
async def on_message(message):
    global socket
    print('[discord] message.content:', message.content)
    if message.author != client.user and message.channel.id == os.getenv('DISCORD_CHANNEL'):
        if not socket:
            print('[discord] no websocket connection')
        else:
            msg = SocketMessage(source=SocketSource.BOT, sender=message.author.name, message=message.content)
            if message.reference:
                ref = message.reference.cached_message
                r = re.match('^#(.+?):', ref.content)
                if r.group(1):
                    msg.recipient = r.group(1)
            await socket.send(msg.to_str())


def run_sync():
    try:
        loop.add_signal_handler(signal.SIGINT, lambda: loop.stop())
        loop.add_signal_handler(signal.SIGTERM, lambda: loop.stop())
    except NotImplementedError:
        pass

    async def runner():
        try:
            await asyncio.gather(
                connect_ws(),
                client.start(os.getenv('DISCORD_TOKEN'))
            )
        finally:
            if not client.is_closed():
                await client.close()

    def stop_loop_on_completion(f):
        loop.stop()

    future = asyncio.ensure_future(runner(), loop=loop)
    future.add_done_callback(stop_loop_on_completion)
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        logger.info('Received signal to terminate bot and event loop.')
    finally:
        future.remove_done_callback(stop_loop_on_completion)
        logger.info('Cleaning up tasks.')
        # _cleanup_loop(loop)

    if not future.cancelled():
        try:
            return future.result()
        except KeyboardInterrupt:
            # I am unsure why this gets raised here but suppress it anyway
            return None


def main_sync() -> None:
    run_sync()


async def main() -> None:
    # client.run(os.getenv('DISCORD_TOKEN'))
    await asyncio.gather(
        connect_ws(),
        client.start(os.getenv('DISCORD_TOKEN')),
    )


if __name__ == "__main__":
    main_sync()
    # asyncio.run(main())
