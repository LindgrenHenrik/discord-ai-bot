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
    parser.add_argument('--steps', type=int, required=False, default=50)

    # Split string and remove quotes
    split_list = re.findall(r'"[^"]+"|\S+', commands)
    split_list = [item.strip('"') for item in split_list]
    args = parser.parse_args(split_list)

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


@bot.event
async def on_ready():
    """On bot ready event handler"""
    print(f'Bot has connected to Discord!')
    for guild in bot.guilds:
        print(f'Connected to guild: {guild.name} (id: {guild.id})')


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
    try:
        payload = parse_command(args)
        await ctx.message.add_reaction('\U0001F440')
        async with aiohttp.ClientSession() as session:
            async with session.post(f'{API_URL}/sdapi/v1/txt2img', json=payload) as response:
                r = await response.json()
                if response.status == 200:
                    await send_images(r.get('images', []), ctx)
                else:
                    await ctx.reply(f'Error: {response.status}')
    except SystemExit:
        await ctx.reply(f'Error: Incorrect command usage.\n!diffusion --prompt "kexchoklad" --steps 10 --batch_size 1 --cfg_scale 7')
    except Exception as e:
        await ctx.reply(f'Error: {e}')


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


# Run the bot
bot.run(BOT_TOKEN)