import argparse
import asyncio
import base64
import io
import json
import os
import random
import re
import time

import aiohttp
import discord
import openai
import requests
from discord.ext import commands
from dotenv import load_dotenv
from requests.exceptions import ConnectionError, Timeout, TooManyRedirects

# Load environment variables
load_dotenv()

API_URL = os.getenv("API_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Check if environment variables are set
if not API_URL or not OPENAI_API_KEY or not BOT_TOKEN:
    raise EnvironmentError(
        "Environment variables not set correctly. Please check your .env file."
    )

# Set OpenAI API key
openai.api_key = OPENAI_API_KEY

semaphore = asyncio.Lock()  # Semaphore to control access

# Create bot instance
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


def parse_command(commands):
    """Parse the command string into separate arguments"""
    parser = argparse.ArgumentParser()

    # Define arguments
    parser.add_argument("--prompt", type=str, required=True)
    parser.add_argument("--batch_size", type=int, required=False, default=1)
    parser.add_argument("--cfg_scale", type=int, required=False, default=7)
    parser.add_argument("--seed", type=int, required=False, default=-1)
    parser.add_argument("--steps", type=int, required=False, default=25)
    parser.add_argument("--width", type=int, required=False, default=512)
    parser.add_argument("--height", type=int, required=False, default=512)

    # Split string and remove quotes
    split_list = re.findall(r'"[^"]+"|\S+', commands)
    split_list = [item.strip('"') for item in split_list]

    try:
        args = parser.parse_args(split_list)
    except argparse.ArgumentError as e:
        return None, f"Argument parsing error: {e}"
    except SystemExit as e:
        return None, f"Argument parsing error: {e}"

    # Apply constraints
    args.steps = max(1, min(args.steps, 50))
    args.cfg_scale = max(1, min(args.cfg_scale, 30))
    args.batch_size = max(1, min(args.batch_size, 10))
    args.width = max(1, max(args.width, 512))
    args.height = max(1, max(args.height, 512))

    return vars(args), None


async def send_images(images, ctx):
    """Convert base64 images to files and send them"""
    files = []
    for i, image in enumerate(images):
        try:
            image_bytes = base64.b64decode(image)
            image_file = io.BytesIO(image_bytes)
            files.append(discord.File(image_file, f"image{i}.png"))
        except Exception as e:
            await ctx.reply(f"Error sending image: {e}")
            return

    await ctx.reply(files=files)


@bot.command()
async def info(ctx):
    """Info command handler"""
    await ctx.reply(
        "The `!diffusion` command is used to generate images based on the provided prompt.\n"
        'Usage: `!diffusion --prompt "your prompt here" [--steps num_steps] [--batch_size num] [--cfg_scale scale]`\n'
        "Arguments:\n"
        "`--prompt`: (required) The text prompt based on which the image is to be generated.\n"
        "`--steps`: (optional) Number of steps to be used for the diffusion process. Default is 25. Must be between 1 and 50 (inclusive).\n"
        "`--batch_size`: (optional) Size of the batch for the diffusion process. Default is 1. Must be between 1 and 10 (inclusive).\n"
        "`--cfg_scale`: (optional) Scale configuration for the diffusion process. Default is 7. Must be between 1 and 30 (inclusive).\n"
        '\nExample: `!diffusion --prompt "sunset over the mountains" --steps 25 --batch_size 2 --cfg_scale 7`\n'
        'This command will generate an image based on the prompt "sunset over the mountains" using 25 steps, a batch size of 2, and a scale configuration of 7.\n'
    )


@bot.event
async def on_ready():
    """On bot ready event handler"""
    print("Bot has connected to Discord!")
    for guild in bot.guilds:
        print(f"Connected to guild: {guild.name} (id: {guild.id})")


# Emoji mapping for progress stages
PROGRESS_EMOJIS = [
    "\u0031\u20e3",
    "\u0032\u20e3",
    "\u0033\u20e3",
    "\u0034\u20e3",
    "\u0035\u20e3",
    "\u0036\u20e3",
    "\u0037\u20e3",
    "\u0038\u20e3",
    "\u0039\u20e3",
    "\U0001f51f",
]


async def fetch_progress(ctx, message):
    """Fetch progress from the API and send it back to the channel"""
    last_stage = -1
    while True:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{API_URL}/sdapi/v1/progress", params={"skip_current_image": "true"}
            ) as response:
                r = await response.json()
                if response.status == 200:
                    progress = r.get("progress", 0)
                    current_stage = min(int(progress * 10), len(PROGRESS_EMOJIS) - 1)
                    if current_stage > last_stage:
                        await safe_add_reaction(message, PROGRESS_EMOJIS[current_stage])
                        last_stage = current_stage
                    print(f"{message.author} progress {progress}")
                else:
                    await ctx.reply(f"Error: {response.status}")
        await asyncio.sleep(2)


@bot.command(name="hello")
async def hello(ctx):
    """Hello command handler"""
    user_id = ctx.message.author.id
    user_responses = {
        os.getenv("NIBBE"): "wassup",
        os.getenv("JEPPE"): "sup",
        os.getenv("HENKE"): "whats crackin",
        os.getenv("BULE"): "hard stuck gold rofl lmao",
    }
    response = user_responses.get(user_id, "yo yo yo yoy yo")
    await ctx.reply(response)


@bot.command()
async def diffusion(ctx, *, args):
    """Diffusion command handler"""

    start_time = time.time()  # start a timer

    await safe_add_reaction(ctx.message, "\U0001f440")
    if semaphore.locked():
        await safe_add_reaction(ctx.message, "\u23f2")  # Clock emoji
    await semaphore.acquire()
    await safe_remove_reaction(ctx.message, "\u23f2", bot.user)

    fetch_task = bot.loop.create_task(fetch_progress(ctx, ctx.message))

    SUCCESS = False
    SKIP = True
    try:
        print(f"Starting diffusion request from {ctx.message.author} with args: {args}")
        payload, parse_error = parse_command(args)
        if parse_error:
            raise SystemExit(parse_error)

        # Start the progress fetching coroutine
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{API_URL}/sdapi/v1/txt2img", json=payload
            ) as response:
                r = await response.json()
                if response.status == 200:
                    await send_images(r.get("images", []), ctx)
                else:
                    await ctx.reply(f"Error: {response.status}")
        SUCCESS = True
    except SystemExit:
        await ctx.reply(
            'Error: Incorrect command usage.\n Here is an exapmle or use !info to get full command info: \n!diffusion --prompt "kexchoklad" --steps 10 --batch_size 1 --cfg_scale 7'
        )
        SKIP = False
    except Exception as e:
        print(f"Error getting stable diffusion from network: {e}")
        await ctx.reply(f"An error occurred: {str(e)}")
    finally:
        fetch_task.cancel()  # Cancel the fetch_progress coroutine
        semaphore.release()

    if SUCCESS and (random.random() < 0.25):
        await ctx.reply(await generate_prompt_resp(payload["prompt"]))
    elif SKIP:
        await ctx.reply(
            await generate_prompt_resp(
                "An error has occurred, an image was not able to be generated from the stable diffusion neural network"
            )
        )

    while True:
        found_me = 0
        for reaction in ctx.message.reactions:
            if reaction.me:
                await safe_remove_reaction(ctx.message, reaction.emoji, bot.user)
                found_me = 1
                break
        if found_me:
            continue
        else:
            break

    await safe_add_reaction(ctx.message, "\u2705")  # Checkmark emoji

    duration = time.time() - start_time
    # await ctx.reply(f"It took me {duration:.2f} seconds to create an image based on '{prompt}'.")


async def safe_remove_reaction(message, emoji, user, max_retries=5):
    """Safely remove a reaction, retrying on rate limit errors."""
    for attempt in range(max_retries):
        try:
            await message.remove_reaction(emoji, user)
            return
        except discord.errors.HTTPException as e:
            if e.status == 429:
                retry_after = e.response.headers.get("Retry-After")
                if retry_after:
                    retry_after = float(retry_after)
                    print(f"Rate limited. Retrying after {retry_after} seconds.")
                    await asyncio.sleep(retry_after)
                else:
                    await asyncio.sleep(2**attempt)  # Exponential backoff
            else:
                raise e


async def safe_add_reaction(message, emoji, max_retries=5):
    """Safely add a reaction, retrying on rate limit errors."""
    for attempt in range(max_retries):
        try:
            await message.add_reaction(emoji)
            return
        except discord.errors.HTTPException as e:
            if e.status == 429:
                retry_after = e.response.headers.get("Retry-After")
                if retry_after:
                    retry_after = float(retry_after)
                    print(f"Rate limited. Retrying after {retry_after} seconds.")
                    await asyncio.sleep(retry_after)
                else:
                    await asyncio.sleep(2**attempt)  # Exponential backoff
            else:
                raise e


@bot.command()
async def chat(ctx, *args):
    """Chat command handler"""
    arg = " ".join(args)
    model = "gpt-4o-mini"
    try:
        response = await retry_openai_request(
            openai.ChatCompletion.create,
            model=model,
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": arg},
            ],
        )

        chat_response = response["choices"][0]["message"]["content"]
        max_message_length = 2000
        while len(chat_response) > max_message_length:
            await ctx.reply(chat_response[:max_message_length])
            chat_response = chat_response[max_message_length:]
        await ctx.reply(chat_response)
    except openai.error.InvalidRequestError as e:
        await ctx.reply(f"Error: {str(e)}")


async def retry_openai_request(request_function, *args, max_retries=5, **kwargs):
    """Retries a given OpenAI API request function upon connection failure."""
    for attempt in range(max_retries):
        try:
            return request_function(*args, **kwargs)
        except (
            openai.error.APIConnectionError,
            openai.error.Timeout,
            ConnectionError,
            Timeout,
            TooManyRedirects,
        ) as e:
            print(
                f"Error communicating with OpenAI: {e}. Retrying ({attempt + 1}/{max_retries})..."
            )
            await asyncio.sleep(2**attempt)
    raise Exception(f"Failed to complete OpenAI request after {max_retries} attempts")


async def generate_prompt_resp(arg):
    response = await retry_openai_request(
        openai.ChatCompletion.create,
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": "you are a gen z teen with hella rizz and swag, respond as if you have it, cap, rizz for real etc, The user text is a prompt that will generate a picture using stable diffusion, respond a roast on why the prompt is bad using rizz, more rizz, more emotes",
            },
            {"role": "user", "content": arg},
        ],
    )
    chat_response = response["choices"][0]["message"]["content"]
    return chat_response


@bot.command(name="meme")
async def meme(ctx):
    response = requests.get("https://meme-api.com/gimme")
    json_data = json.loads(response.text)
    memes = json_data["url"]

    await ctx.send(memes)


# @bot.command()
# async def rs_nn(ctx, *args):
#     STABLE_DiFFUSION_ID = '085c912e4bbbdbba0b014af5321b0f17bab88df54c63b1dcd8c4b0d491f028c6'
#     client = docker.from_env()
#     try:
#         container = client.containers.get(STABLE_DiFFUSION_ID)
#         container.restart()
#         await ctx.reply(f'The stable diffusion Docker container has been restarted')
#     except docker.errors.NotFound:
#         await ctx.reply(f'No such container')
#     except docker.errors.APIError as e:
#         await ctx.reply(f'An error occurred')

# Run the bot
bot.run(BOT_TOKEN)
