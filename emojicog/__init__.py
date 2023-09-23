from .emojicog import EmojiCog

async def setup(bot):
    await bot.add_cog(EmojiCog(bot))
