import re
import signal
import logging
from typing import Optional

import discord
import websockets
import os

from discord.ext import commands;

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
owner: Optional[User] = None
BOT_ACTIVATOR = '~'
bot = commands.Bot(loop=loop, command_prefix='~')


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
                channel = bot.get_channel(int(os.getenv('DISCORD_CHANNEL')))

            if m.scope is SocketScope.PUBLIC:
                if channel:
                    if m.source is not SocketSource.BOT:
                        await channel.send(f"#{m.sender}: {m.message}")
            elif m.scope is SocketScope.PRIVATE:
                if owner:
                    await owner.send(f"#{m.sender}: {m.message}")


@bot.event
async def on_ready():
    logger.info('we should be ready')
    global channel
    global owner
    if not channel:
        channel = bot.get_channel(int(os.getenv('DISCORD_CHANNEL')))
    if not owner:
        app_info = await bot.application_info()
        owner = app_info.owner

    if not channel:
        logger.error('[discord] cannot connect to discord channel')
    else:
        logger.info('[discord] connected to '+os.getenv('DISCORD_CHANNEL'))


@bot.event
async def on_error(evt, *args, **kwargs):
    print("Error encountered", evt)


@bot.event
async def on_message(message):
    global socket
    print('[discord] message.content:', message.content)
    if message.content[0] == BOT_ACTIVATOR:
        cmd = message.content[1:]
        if cmd == 'hello':
            await message.channel.send('yo.')
        elif cmd == 'words':
            await message.channel.send(':flying_saucer: KLAATU BARADA NIKTO')

    elif message.author != bot.user and str(message.channel.id) == os.getenv('DISCORD_CHANNEL'):
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


@bot.command()
async def help(ctx, args=None):
    help_embed = discord.Embed(title="gort is helping.", colour = discord.Colour.red())
    command_names_list = [x.name for x in bot.commands]

    # If there are no arguments, just list the commands:
    if not args:
        help_embed.add_field(
            name="what he does:",
            value="\n".join([str(i+1)+". "+x.name for i,x in enumerate(bot.commands)]),
            inline=False
        )
        help_embed.add_field(
            name="learning more",
            value="type `~help [command name]` for more info",
            inline=False
        )

    # If the argument is a command, get the help text from that command:
    elif args in command_names_list:
        try:
            ag = bot.get_command(args)
            al = ""
            als = ag.aliases
            for i in range(len(als)):
                al += (str(als[i]) + ", ")
            tob = al.rstrip(" ,")
            help_embed.add_field(
                name=args,
                value = (ag.help + "\nalt commands: " + str(tob))
            )
        except:
            help_embed.add_field(
                name=args,
                value=bot.get_command(args).help
            )
            print("problem, bot?")

    # If someone is just trolling:
    else:
        help_embed.add_field(
            name="404",
            value="command not found"
        )
    await ctx.send(embed=help_embed)


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
                bot.start(os.getenv('DISCORD_TOKEN'))
            )
        finally:
            if not bot.is_closed():
                await bot.close()

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
    # bot.run(os.getenv('DISCORD_TOKEN'))
    await asyncio.gather(
        connect_ws(),
        bot.start(os.getenv('DISCORD_TOKEN')),
    )


if __name__ == "__main__":
    main_sync()
    # asyncio.run(main())
