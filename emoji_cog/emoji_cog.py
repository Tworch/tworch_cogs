import discord
from redbot.core import commands
import requests
from bs4 import BeautifulSoup
import re

# Define a list of allowed user IDs (bot owner and other allowed users)
ALLOWED_USER_IDS = [556433749424734215,1113483997171945633,885109837673951242]  # Replace with the desired user IDs

class EmojiCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def is_allowed_user(self, ctx):
        return ctx.author.id in ALLOWED_USER_IDS

    @commands.command()
    async def getemoji(self, ctx, *emoji_urls: str):
        if not self.is_allowed_user(ctx):
            await ctx.send("You do not have permission to use this command.")
            return

        for emoji_url in emoji_urls:
            response = requests.get(emoji_url)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                emoji_element = soup.find('img', class_='emoji-img')  # Adjust this based on website structure

                if emoji_element:
                    emoji_url = emoji_element['src']
                    emoji_name = re.sub(r'\W+', '_', emoji_element['alt'])[:32]  # Sanitize and limit name length

                    # Fetch emoji image
                    response = requests.get(emoji_url)
                    if response.status_code == 200:
                        emoji_image = response.content
                    else:
                        await ctx.send(f"Failed to fetch emoji: {emoji_name}")
                        continue

                    # Upload emoji to the server
                    try:
                        emoji = await ctx.guild.create_custom_emoji(name=emoji_name, image=emoji_image)
                        await ctx.send(f"Emoji '{emoji.name}' has been added to the server!")
                    except discord.Forbidden:
                        await ctx.send("Bot does not have permission to create emojis.")
                    except discord.HTTPException as e:
                        await ctx.send(f"Failed to create emoji: {e}")
                else:
                    await ctx.send("Emoji not found on the page.")
            else:
                await ctx.send(f"Failed to fetch the emoji page: {emoji_url}")

def setup(bot):
    bot.add_cog(EmojiCog(bot))
