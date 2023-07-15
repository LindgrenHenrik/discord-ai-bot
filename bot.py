import os
import re
import base64
import io
import discord
from discord.ext import commands
import openai
import aiohttp
import argparse
from dotenv import load_dotenv
import asyncio
import time
import requests
import json
import random
import docker

# Load environment variables
load_dotenv()

API_URL = os.getenv("API_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Check if environment variables are set
if not API_URL or not OPENAI_API_KEY or not BOT_TOKEN:
    raise EnvironmentError('Environment variables not set correctly. Please check your .env file.')

# Set OpenAI API key
openai.api_key = OPENAI_API_KEY

semaphore = asyncio.Lock()  # Semaphore to control access

# Create bot instance
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)


def parse_command(commands):
    """Parse the command string into separate arguments"""
    parser = argparse.ArgumentParser()

    # Define arguments
    parser.add_argument('--prompt', type=str, required=True)
    parser.add_argument('--batch_size', type=int, required=False, default=1)
    parser.add_argument('--cfg_scale', type=int, required=False, default=7)
    parser.add_argument('--seed', type=int, required=False, default=-1)
    parser.add_argument('--steps', type=int, required=False, default=25)

    # Split string and remove quotes
    split_list = re.findall(r'"[^"]+"|\S+', commands)
    split_list = [item.strip('"') for item in split_list]
    args = parser.parse_args(split_list)

    # Apply constraints
    args.steps = max(1, min(args.steps, 50))
    args.cfg_scale = max(1, min(args.cfg_scale, 30))
    args.batch_size = max(1, min(args.batch_size, 10))

    return args.__dict__


async def send_images(images, ctx):
    """Convert base64 images to files and send them"""
    files = []
    for i, image in enumerate(images):
        try:
            image_bytes = base64.b64decode(image)
            image_file = io.BytesIO(image_bytes)
            files.append(discord.File(image_file, f'image{i}.png'))
        except Exception as e:
            await ctx.reply(f'Error sending image: {e}')
            return

    await ctx.reply(files=files)


@bot.command()
async def info(ctx):
    """Info command handler"""
    await ctx.reply(
        f'The `!diffusion` command is used to generate images based on the provided prompt.\n'
        f'Usage: `!diffusion --prompt "your prompt here" [--steps num_steps] [--batch_size num] [--cfg_scale scale]`\n'
        f'Arguments:\n'
        f'`--prompt`: (required) The text prompt based on which the image is to be generated.\n'
        f'`--steps`: (optional) Number of steps to be used for the diffusion process. Default is 25. Must be between 1 and 50 (inclusive).\n'
        f'`--batch_size`: (optional) Size of the batch for the diffusion process. Default is 1. Must be between 1 and 10 (inclusive).\n'
        f'`--cfg_scale`: (optional) Scale configuration for the diffusion process. Default is 7. Must be between 1 and 30 (inclusive).\n'
        f'\nExample: `!diffusion --prompt "sunset over the mountains" --steps 25 --batch_size 2 --cfg_scale 7`\n'
        f'This command will generate an image based on the prompt "sunset over the mountains" using 25 steps, a batch size of 2, and a scale configuration of 7.\n'
    )


@bot.event
async def on_ready():
    """On bot ready event handler"""
    print(f'Bot has connected to Discord!')
    for guild in bot.guilds:
        print(f'Connected to guild: {guild.name} (id: {guild.id})')

# Emoji mapping for progress stages
PROGRESS_EMOJIS = ["\u0031\u20E3", "\u0032\u20E3", "\u0033\u20E3", "\u0034\u20E3", "\u0035\u20E3", "\u0036\u20E3", "\u0037\u20E3", "\u0038\u20E3", "\u0039\u20E3", "\U0001F51F"]

async def fetch_progress(ctx, message):
    """Fetch progress from the API and send it back to the channel"""
    last_stage = -1
    while True:
        async with aiohttp.ClientSession() as session:
            async with session.get(f'{API_URL}/sdapi/v1/progress', params={'skip_current_image': 'true'}) as response:
                r = await response.json()
                if response.status == 200:
                    progress = r.get('progress', 0)
                    current_stage = min(int(progress * 10), len(PROGRESS_EMOJIS) - 1)
                    if current_stage > last_stage:
                        await message.add_reaction(PROGRESS_EMOJIS[current_stage])
                        last_stage = current_stage
                    print(f'{message.author} progress {progress}')
                else:
                    await ctx.reply(f'Error: {response.status}')
        await asyncio.sleep(2)

@bot.command(name='hello')
async def hello(ctx):
    """Hello command handler"""
    user_id = ctx.message.author.id
    user_responses = {
        os.getenv("NIBBE"): 'wassup nigga',
        os.getenv("JEPPE"): 'sup',
        os.getenv("HENKE"): 'whats crackin',
        os.getenv("BULE"): 'hard stuck gold rofl lmao'
    }
    response = user_responses.get(user_id, 'yo yo yo yoy yo')
    await ctx.reply(response)


@bot.command()
async def diffusion(ctx, *, args):
    """Diffusion command handler"""

    start_time = time.time() # start a timer

    await ctx.message.add_reaction('\U0001F440') # side eye emoji
    if semaphore.locked():
        await ctx.message.add_reaction('\u23F2')  # Clock emoji
    await semaphore.acquire()
    await ctx.message.remove_reaction('\u23F2', bot.user)

    fetch_task = bot.loop.create_task(fetch_progress(ctx,ctx.message))

    ERROR = True
    try:
        print(f'Starting diffusion request from {ctx.message.author} with args: {args}')
        payload = parse_command(args)
        prompt = payload['prompt']


        # Start the progress fetching coroutine
        async with aiohttp.ClientSession() as session:
            async with session.post(f'{API_URL}/sdapi/v1/txt2img', json=payload) as response:
                r = await response.json()
                if response.status == 200:
                    await send_images(r.get('images', []), ctx)
                else:
                    await ctx.reply(f'Error: {response.status}')
        ERROR = False
    except SystemExit:
        await ctx.reply(f'Error: Incorrect command usage.\n Here is an exapmle or use !info to get full command info: \n!diffusion --prompt "kexchoklad" --steps 10 --batch_size 1 --cfg_scale 7')
    except Exception as e:
        print(f'Error getting stable diffusion from network: {e}')

    if ERROR:
        await ctx.reply(generate_promt_resp('An error has occurred, an image was not able to be generated from the stable diffusion neural network'))
    elif random.random() < 0.25:
        await ctx.reply(generate_promt_resp(payload['prompt']))
    
    while True:
        found_me = 0
        for reaction in ctx.message.reactions:
            if reaction.me:
                await reaction.remove(bot.user)
                found_me = 1
                break
        if found_me:
            continue
        else:
            break
    # Remove all reactions
    #await ctx.message.clear_reactions()
    #await ctx.message.reactions[0].remove(bot.user)
    await ctx.message.add_reaction('\u2705')  # Checkmark emoji

    # Calculate the duration
    duration = time.time() - start_time
    
    # Reply with the duration
    #await ctx.reply(f"It took me {duration:.2f} seconds to create an image based on '{prompt}'.")

    fetch_task.cancel()  # Cancel the fetch_progress coroutine
    semaphore.release()


@bot.command()
async def chat(ctx, *args):
    """Chat command handler"""
    arg = ' '.join(args)
    model = "gpt-3.5-turbo"
    try:
        response = openai.ChatCompletion.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": arg}
            ]
        )

        chat_response = response['choices'][0]['message']['content']
        max_message_length = 2000
        while len(chat_response) > max_message_length:
            await ctx.reply(chat_response[:max_message_length])
            chat_response = chat_response[max_message_length:]
        await ctx.reply(chat_response)
    except openai.error.InvalidRequestError as e:
        await ctx.reply(f'Error: {str(e)}')



def generate_promt_resp(arg):
    model = "gpt-3.5-turbo"
    response = openai.ChatCompletion.create(
        model=model,
        messages=[{"role": "system", "content": "you are a gen z teen with hella rizz and swagg, respond as if you have it, cap, rizz for real etc, The user text is a prompt that will generate a picture using stable diffusion, respoand a roast on why the prompt is bad using rizz, more rizz, more emotes"},
        {"role": "user", "content": arg}])
    chat_response = response['choices'][0]['message']['content']
    return chat_response


@bot.command(name='meme')
async def meme(ctx):
    response = requests.get('https://meme-api.com/gimme')
    json_data = json.loads(response.text)
    memes = json_data['url']

    await ctx.send(memes)


@bot.command()
async def rs_nn(ctx, *args):
    STABLE_DiFFUSION_ID = '085c912e4bbbdbba0b014af5321b0f17bab88df54c63b1dcd8c4b0d491f028c6'
    client = docker.from_env()
    try:
        container = client.containers.get(STABLE_DiFFUSION_ID)
        container.restart()
        await ctx.reply(f'The stable diffusion Docker container has been restarted')
    except docker.errors.NotFound:
        await ctx.reply(f'No such container')
    except docker.errors.APIError as e:
        await ctx.reply(f'An error occurred')

# Run the bot
bot.run(BOT_TOKEN)