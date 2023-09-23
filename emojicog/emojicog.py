import json
import aiohttp
import os
from redbot.core import checks
from bs4 import BeautifulSoup
import discord
from redbot.core import commands, app_commands

class EmojiCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.session = aiohttp.ClientSession()
        self.role_config_file = os.path.join(os.path.dirname(__file__), "roles_config.json")
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

    @commands.command()
    @checks.is_owner()
    async def addemojirule(self, ctx, role_id: int):
        guild_id = str(ctx.guild.id)
        if guild_id not in self.allowed_roles:
            self.allowed_roles[guild_id] = []
        self.allowed_roles[guild_id].append(role_id)
        self.save_roles()
        await ctx.send(f"Role {role_id} added.")

    @commands.command()
    @checks.is_owner()
    async def removeemojirule(self, ctx, role_id: int):
        guild_id = str(ctx.guild.id)
        if guild_id in self.allowed_roles and role_id in self.allowed_roles[guild_id]:
            self.allowed_roles[guild_id].remove(role_id)
            self.save_roles()
            await ctx.send(f"Role {role_id} removed.")
        else:
            await ctx.send(f"Role {role_id} was not found in the list of allowed roles.")

    @app_commands.command()
    async def getemoji(self, interaction: discord.Interaction, emoji_name_or_url: str):
        await interaction.response.defer(ephemeral=True)
        guild_id = str(interaction.guild_id)

        if guild_id in self.allowed_roles:
            user_role_ids = [role.id for role in interaction.user.roles]
            if not any(role_id in user_role_ids for role_id in self.allowed_roles[guild_id]):
                await interaction.followup.send("You do not have permission to use this command.", ephemeral=True)
                return
        else:
            await interaction.followup.send("No roles have been set to use this command.", ephemeral=True)
            return

        async with self.session.get(emoji_name_or_url) as resp:
            if resp.status != 200:
                await interaction.followup.send("Failed to fetch the webpage.", ephemeral=True)
                return

            soup = BeautifulSoup(await resp.text(), 'html.parser')
            emoji_div = soup.find("div", {"class": "card-body emoji-pad"})
            if emoji_div:
                emoji_tag = emoji_div.find("img")
                if emoji_tag and 'src' in emoji_tag.attrs:
                    emoji_url = emoji_tag['src']
                    if not emoji_url.startswith('https://'):
                        emoji_url = "https://emoji.gg" + emoji_url

                    async with self.session.get(emoji_url) as img_resp:
                        if img_resp.status != 200:
                            await interaction.followup.send("Failed to download the emoji.", ephemeral=True)
                            return

                        image_data = await img_resp.read()

                        # Validate and sanitize the emoji name
                        emoji_name = emoji_name_or_url.split('/')[-1]
                        emoji_name = ''.join(e for e in emoji_name if e.isalnum() or e == '_')

                        await interaction.guild.create_custom_emoji(name=emoji_name, image=image_data)
                        await interaction.followup.send(f"Emoji added successfully.")
                else:
                    await interaction.followup.send("Could not find the emoji on the webpage.", ephemeral=True)
            else:
                await interaction.followup.send("Failed to parse the webpage.", ephemeral=True)
