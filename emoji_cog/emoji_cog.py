import discord
from redbot.core import commands, Config
import aiohttp
from bs4 import BeautifulSoup
import re
from urllib.parse import urlparse, urljoin
import asyncio
import json
import time
import aioredis

# Constants for rate limiting (adjust as needed)
RATE_LIMIT_SECONDS = 60  # Rate limit window in seconds
MAX_REQUESTS_PER_WINDOW = 5  # Maximum requests allowed per window

class EmojiCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=7465947364)  # Change the identifier to a unique value
        self.config.register_guild(allowed_roles=[])
        
        # Rate limiting using Redis
        self.redis = None
        self.rate_limit_key = "emoji_cog_rate_limit"
        
        self.session = aiohttp.ClientSession()

    async def cog_unload(self):
        await self.session.close()
        if self.redis:
            await self.redis.close()

    def is_valid_url(self, url):
        try:
            parsed_url = urlparse(url)
            # Ensure the URL has a scheme (http, https) and a network location (domain)
            if parsed_url.scheme not in {"http", "https"}:
                return False
            return bool(parsed_url.netloc)
        except ValueError:
            return False

    async def validate_image(self, ctx, emoji_name, emoji_data):
        # If emoji_data is None, it means no image data is provided (e.g., when fetching from a URL)
        if emoji_data is None:
            await ctx.send(f"No image data provided for '{emoji_name}'.")
            return False

        # Check the Content-Type header to ensure it's an image
        if hasattr(ctx.message, "attachments") and ctx.message.attachments:
            content_type = ctx.message.attachments[0].content_type
            if not content_type.startswith("image/"):
                await ctx.send(f"Invalid image type: {content_type}")
                return False

        # Check the Content-Length header for file size
        content_length = len(emoji_data)
        max_file_size = 2 * 1024 * 1024  # 2 MB (adjust as needed)
        if content_length > max_file_size:
            await ctx.send(f"Image size exceeds the limit (max {max_file_size / 1024} KB).")
            return False

        # Additional security check: Ensure that the image data is indeed an image
        if not emoji_data.startswith(b'\xFF\xD8\xFF\xE0'):
            await ctx.send("Invalid image format.")
            return False

        # Additional security check: Detect and reject images with malicious content (e.g., inappropriate content)
        # You may need to implement a more advanced image analysis library for this
        # For example, consider using a service like the Microsoft Azure Computer Vision API

        # Add more advanced security checks here as needed

        return True

    async def check_rate_limit(self, ctx):
        if not self.redis:
            return True
        
        user_id = ctx.author.id
        current_time = time.time()
        
        try:
            rate_limit_info = await self.redis.hgetall(self.rate_limit_key, encoding="utf-8")
            
            # Remove requests that are older than the rate limit window
            rate_limit_info = {k: float(v) for k, v in rate_limit_info.items() if current_time - float(v) <= RATE_LIMIT_SECONDS}
            
            if len(rate_limit_info) >= MAX_REQUESTS_PER_WINDOW:
                # User has reached the rate limit
                await ctx.send(f"You have reached the rate limit. Try again in {RATE_LIMIT_SECONDS} seconds.")
                return False
            else:
                # Add the current request time to the user's rate limit list
                rate_limit_info[user_id] = current_time
                await self.redis.hmset_dict(self.rate_limit_key, rate_limit_info)
                return True
        except Exception as e:
            # Handle rate limit check errors gracefully
            await ctx.send(f"Rate limit check failed: {e}")
            return True  # Continue if there's an issue with Redis

    @commands.group()
    async def emoji(self, ctx):
        """Manage emoji-related commands."""
        pass

    @emoji.command(name="listroles")
    async def list_roles(self, ctx):
        """List the roles allowed to use emoji commands."""
        guild_settings = self.config.guild(ctx.guild)
        allowed_roles = await guild_settings.allowed_roles()
        if allowed_roles:
            role_mentions = [f"<@&{role_id}>" for role_id in allowed_roles]
            await ctx.send(f"Roles allowed to use emoji commands: {', '.join(role_mentions)}")
        else:
            await ctx.send("No roles are allowed to use emoji commands.")

    @commands.command()
    async def getemoji(self, ctx, *emoji_urls: str):
        """Fetch and add emojis to the server."""
        allowed_roles = await self.config.guild(ctx.guild).allowed_roles()
        if not allowed_roles:
            await ctx.send("No roles are allowed to use emoji commands.")
            return

        for emoji_url in emoji_urls:
            if not self.is_valid_url(emoji_url):
                await ctx.send(f"Invalid URL: {emoji_url}")
                continue

            if not await self.check_rate_limit(ctx):  # Check rate limit before each emoji creation
                continue

            async with self.session.get(urljoin(ctx.message.jump_url, emoji_url)) as response:
                if response.status == 200:
                    soup = BeautifulSoup(await response.text(), 'html.parser')
                    emoji_element = soup.find('img', class_='emoji-img')  # Adjust this based on website structure

                    if emoji_element:
                        emoji_url = emoji_element['src']
                        emoji_name = re.sub(r'\W+', '_', emoji_element['alt'])[:32]  # Sanitize and limit name length

                        async with self.session.get(urljoin(ctx.message.jump_url, emoji_url)) as image_response:
                            if image_response.status == 200:
                                emoji_image = await image_response.read()
                                # Validate the fetched image
                                if not await self.validate_image(ctx, emoji_name, emoji_image):
                                    continue

                                try:
                                    emoji = await ctx.guild.create_custom_emoji(name=emoji_name, image=emoji_image)
                                    await ctx.send(f"Emoji '{emoji.name}' has been added to the server!")
                                except discord.Forbidden:
                                    await ctx.send("Bot does not have permission to create emojis.")
                                except discord.HTTPException as e:
                                    await ctx.send(f"Failed to create emoji: {e}")
                            else:
                                await ctx.send(f"Failed to fetch emoji: {emoji_name}")
                    else:
                        await ctx.send("Emoji not found on the page.")
                else:
                    await ctx.send("Failed to fetch the emoji page.")

def setup(bot):
    bot.add_cog(EmojiCog(bot))
