from .emoji_cog import EmojiCog  # Updated import statement


async def setup(bot):
    cog = EmojiCog(bot)
    await bot.add_cog(cog)
