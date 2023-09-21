import discord
from redbot.core import commands, checks, Config
import aiohttp
from bs4 import BeautifulSoup
import re
from urllib.parse import urlparse, urljoin
import asyncio
import json
import time  # Import the time module

# Constants for rate limiting (adjust as needed)
RATE_LIMIT_SECONDS = 60  # Rate limit window in seconds
MAX_REQUESTS_PER_WINDOW = 5  # Maximum requests allowed per window

class EmojiCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=1234567890)  # Change the identifier to a unique value
        self.config.register_guild(allowed_roles=[])
        self.rate_limit = {}  # Rate limit dictionary

        self.session = aiohttp.ClientSession()

    async def cog_unload(self):
        await self.session.close()

    def is_valid_url(self, url):
        try:
            parsed_url = urlparse(url)
            return all([parsed_url.scheme, parsed_url.netloc])
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

        # Add more security checks here as needed

        return True

    async def check_rate_limit(self, ctx):
        user_id = ctx.author.id
        current_time = time.time()
        user_rate_limit = self.rate_limit.get(user_id, [])
        
        # Remove requests that are older than the rate limit window
        user_rate_limit = [t for t in user_rate_limit if current_time - t <= RATE_LIMIT_SECONDS]
        
        if len(user_rate_limit) >= MAX_REQUESTS_PER_WINDOW:
            # User has reached the rate limit
            await ctx.send(f"You have reached the rate limit. Try again in {RATE_LIMIT_SECONDS} seconds.")
            return False
        else:
            # Add the current request time to the user's rate limit list
            user_rate_limit.append(current_time)
            self.rate_limit[user_id] = user_rate_limit
            return True

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

    async def add_allowed_role(self, ctx, role_id):
        guild_settings = self.config.guild(ctx.guild)
        allowed_roles = await guild_settings.allowed_roles()
        if role_id not in allowed_roles:
            allowed_roles.append(role_id)
            await guild_settings.allowed_roles.set(allowed_roles)
            await ctx.send("Role has been added to the allowed roles list.")
        else:
            await ctx.send("Role is already in the allowed roles list.")

    async def remove_allowed_role(self, ctx, role_id):
        guild_settings = self.config.guild(ctx.guild)
        allowed_roles = await guild_settings.allowed_roles()
        if role_id in allowed_roles:
            allowed_roles.remove(role_id)
            await guild_settings.allowed_roles.set(allowed_roles)
            await ctx.send("Role has been removed from the allowed roles list.")
        else:
            await ctx.send("Role is not in the allowed roles list.")

    @commands.command()
    @checks.is_owner()
    async def allowrole(self, ctx, role: discord.Role):
        """Allow a role to use emoji commands."""
        await self.add_allowed_role(ctx, role.id)

    @commands.command()
    @checks.is_owner()
    async def disallowrole(self, ctx, role: discord.Role):
        """Disallow a role from using emoji commands."""
        await self.remove_allowed_role(ctx, role.id)

def setup(bot):
    bot.add_cog(EmojiCog(bot))
