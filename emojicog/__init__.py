from .emojicog import EmojiCog
from redbot.core import commands
from discord_slash import SlashCommand

async def setup(bot: commands.Bot):
    slash = SlashCommand(bot, sync_commands=True)  # Initializes slash commands
    await bot.add_cog(EmojiCog(bot, slash))
