import json
import discord
from discord.ext import commands
import aiohttp
import base64
import io
import openai
from dotenv import load_dotenv
import os
import argparse
import re

# Load environment variables from the .env file
load_dotenv()

API_URL = os.getenv("API_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
BOT_TOKEN = os.getenv("BOT_TOKEN")

openai.api_key = OPENAI_API_KEY


# Create a new bot instance
intents = discord.Intents.default()
#intents.messages = True
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)


def parse_command(commands):    
    parser = argparse.ArgumentParser()

    # Define arguments
    parser.add_argument('--prompt', type=str, required=True)
    parser.add_argument('--batch_size', type=int, required=False, default = 1)
    parser.add_argument('--cfg_scale', type=int, required=False, default = 7)
    parser.add_argument('--seed', type=int, required=False, default = -1)
    parser.add_argument('--steps', type=int, required=False, default = 50)
    
    # Split the string at spaces, excluding spaces within quotes
    split_list = re.findall(r'"[^"]+"|\S+', commands)

    # Remove the quotes from the split values
    split_list = [item.strip('"') for item in split_list]
    args = parser.parse_args(split_list)

    return args.__dict__


@bot.event
async def on_ready():
    print(f'Bot has connected to Discord!')
    for guild in bot.guilds:
        print(f'Connected to guild: {guild.name} (id: {guild.id})')


# Define the 'hello' command
@bot.command(name='hello')
async def hello(ctx):
    if ctx.message.author.id == int(os.getenv("NIBBE")): # nibbe
        await ctx.reply('wassup nigga')
    elif ctx.message.author.id == int(os.getenv("JEPPE")): # jeppe
        await ctx.reply('sup')
    elif ctx.author.id == int(os.getenv("HENKE")): # henke
        await ctx.reply('whats crackin')
    elif ctx.author.id == int(os.getenv("BULE")): # ludwig
        await ctx.reply('hard stuck gold rofl lmao')
    else:
        await ctx.reply('yo yo yo yoy yo')

# Command: !diffusion
@bot.command()
async def diffusion(ctx, *, args):
    # This function will be called when '!diffusion' command is used in any channel the bot has access to

    try:
        payload = parse_command(args)
        success = True
    except SystemExit:
        await ctx.reply(f'Error: Incorrect command usage.\n!diffusion --prompt "kexchoklad" --steps 10 --batch_size 1 --cfg_scale 7')
        success = False
    except Exception as e:
        await ctx.reply(f'Error: {e}')
        success = False

    if success:
        await ctx.message.add_reaction('\U0001F440')
        async with aiohttp.ClientSession() as session:
            async with session.post(f'{API_URL}/sdapi/v1/txt2img', json=payload) as response:
                # Add reaction to acknowledge the message
                r = await response.json()

                # Check if the request was successful
                if response.status == 200:
                    # If successful, send the response data back to the channel
                    # Extract data from response
                    images = r.get('images', [])
                    parameters = r.get('parameters', {})
                    info = r.get('info', '')

                    # Send images to the channel
                    for i, image in enumerate(images):
                        try:
                            # Try to decode the base64 string and create an image file
                            image_bytes = base64.b64decode(image)
                            image_file = io.BytesIO(image_bytes)
                            await ctx.reply(file=discord.File(image_file, f'image{i}.png'))
                        except Exception as e:
                            # If there's an error, send a message
                            await ctx.reply(f'Error sending image: {e}')

                    # Send parameters to the channel
                    #await ctx.send(f'Parameters: {parameters}')
                    # Send info to the channel
                    #await ctx.send(f'Info: {info}')



                else:
                    # If not successful, send an error message
                    await ctx.reply(f'Error: {response.status}')


# Command: !chat
@bot.command()
async def chat(ctx, *args):
    # This function will be called when '!chat' command is used in any channel the bot has access to
    arg = ' '.join(args)
    # Define the payload
    MODEL = "gpt-3.5-turbo"
    try:
        # Send the API request
        
        response = openai.ChatCompletion.create(
            model = MODEL,
            messages = [
                {"role": "system","content":"You are a helpful assistant."},
                {"role": "user","content":arg}
            ]
        )

        # Extract the response
        chat_response = response['choices'][0]['message']['content']
        # Send the chat response to the channel
        max_message_length = 2000  # Maximum length of a single message
        while len(chat_response) > max_message_length:
            await ctx.reply(chat_response[:max_message_length])
            chat_response = chat_response[max_message_length:]
        await ctx.reply(chat_response)


    except openai.error.InvalidRequestError as e:
        # If there's an error, send a message
        await ctx.reply(f'Error: {str(e)}')



# Run the bot
bot.run(BOT_TOKEN)
