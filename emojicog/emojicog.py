import json
import aiohttp
import discord
from bs4 import BeautifulSoup
from redbot.core import commands, checks
from discord_slash import cog_ext, SlashContext
from discord_slash.utils.manage_commands import create_option

class EmojiCog(commands.Cog):
    def __init__(self, bot, slash):
        self.bot = bot
        self.slash = slash
        self.session = aiohttp.ClientSession()
        self.role_config_file = "roles_config.json"
        self.load_roles()

    def load_roles(self):
        try:
            with open(self.role_config_file, "r") as f:
                self.allowed_roles = json.load(f)
        except FileNotFoundError:
            self.allowed_roles = {}

    def save_roles(self):
        with open(self.role_config_file, "w") as f:
            json.dump(self.allowed_roles, f)

    @cog_ext.cog_slash(
        name="emoji",
        description="Emoji related commands.",
        options=[
            create_option(
                name="action",
                description="What action do you want to perform?",
                option_type=3,
                required=True,
                choices=["listroles", "get"]
            ),
            create_option(
                name="emoji_name_or_url",
                description="Emoji name or URL, if action is get",
                option_type=3,
                required=False
            )
        ]
    )
    async def _emoji(self, ctx: SlashContext, action: str, emoji_name_or_url: str = None):
        if action == "listroles":
            await self.emoji_listroles(ctx)
        elif action == "get":
            if emoji_name_or_url:
                await self.emoji_get(ctx, emoji_name_or_url)
            else:
                await ctx.send("Please specify an emoji name or URL.")
        else:
            await ctx.send("Invalid action.")

    async def emoji_listroles(self, ctx):
        roles = ', '.join([str(role_id) for role_id in self.allowed_roles.get(str(ctx.guild.id), [])])
        await ctx.send(f"Roles allowed to use `getemoji`: {roles}")

    @commands.command(name='addrole')
    @checks.is_owner()
    async def emoji_addrole(self, ctx, role: discord.Role):
        guild_id = str(ctx.guild.id)
        if guild_id not in self.allowed_roles:
            self.allowed_roles[guild_id] = []
        self.allowed_roles[guild_id].append(role.id)
        self.save_roles()
        await ctx.send(f"Role `{role.name}` added.")

    @commands.command(name='removerole')
    @checks.is_owner()
    async def emoji_removerole(self, ctx, role: discord.Role):
        guild_id = str(ctx.guild.id)
        if guild_id in self.allowed_roles and role.id in self.allowed_roles[guild_id]:
            self.allowed_roles[guild_id].remove(role.id)
            self.save_roles()
            await ctx.send(f"Role `{role.name}` removed.")
        else:
            await ctx.send(f"Role `{role.name}` was not found in the list of allowed roles.")

    async def emoji_get(self, ctx, emoji_name_or_url: str):
        guild_id = str(ctx.guild.id)
        
        # Check role-based restriction
        if guild_id in self.allowed_roles:
            user_role_ids = [role.id for role in ctx.author.roles]
            if not any(role_id in user_role_ids for role_id in self.allowed_roles[guild_id]):
                await ctx.send("You do not have permission to use this command.")
                return
        else:
            await ctx.send("No roles have been set to use this command.")
            return

        try:
            async with self.session.get(emoji_name_or_url) as resp:
                soup = BeautifulSoup(await resp.text(), 'html.parser')
        except Exception as e:
            await ctx.send(f"An error occurred while fetching the webpage: {e}")
            return

        emoji_div = soup.find("div", {"class": "card-body emoji-pad"})
        if emoji_div:
            emoji_tag = emoji_div.find("img")
            if emoji_tag and 'src' in emoji_tag.attrs:
                emoji_url = emoji_tag['src']
                if not emoji_url.startswith('https://'):
                    emoji_url = "https://emoji.gg" + emoji_url
            else:
                await ctx.send("Emoji image not found on the webpage.")
                return
        else:
            await ctx.send("Emoji section not found on the webpage.")
            return

        try:
            async with self.session.get(emoji_url) as resp:
                image_data = await resp.read()
        except Exception as e:
            await ctx.send(f"An error occurred while fetching the emoji image: {e}")
            return

        try:
            emoji_name = emoji_name_or_url.split("/")[-1]  # extracting last part from URL
            await ctx.guild.create_custom_emoji(name=emoji_name.split("-")[-1], image=image_data)  # using last part as the emoji name
            await ctx.send(f"Emoji `{emoji_name}` has been added.")
        except Exception as e:
            await ctx.send(f"An error occurred while creating the emoji: {e}")
