from config import api_key, apy_key_secret, access_token, access_token_secret, discordBotKey
import tweepy
import discord
from discord import message
from discord.ext import commands, tasks
from discord.app import Option
import db
import datetime
import pytz

utc=pytz.UTC
auth = tweepy.OAuthHandler(api_key, apy_key_secret)
auth.set_access_token(access_token, access_token_secret)
twitter = tweepy.API(auth, wait_on_rate_limit=True)

intents = discord.Intents.all()
intents.members = True
client = commands.Bot(intents=intents, help_command=None)

def get_user_id(twitterUser):
    user = twitter.get_user(screen_name=twitterUser)
    return(user.id)

def get_user_tweets(twitterID, last_tweet, last_at):
    tweets = twitter.user_timeline(user_id=twitterID, count=5)
    for t in tweets:
        #only tweets, no retweets --> "retweeted_status" not in t._json
        if t._json["id"] != last_tweet and (last_at == 0 or datetime.datetime.strptime(t._json["created_at"], "%a %b %d %H:%M:%S %z %Y") > last_at):
            last_tweet, last_at = t._json["id"], datetime.datetime.strptime(t._json["created_at"], "%a %b %d %H:%M:%S %z %Y")
    
    return(tweets[0]._json["user"], last_tweet, last_at)


@client.event
async def on_ready():
    print('Logged in as {0.user}'.format(client))
    if not check_tweets.is_running():
        check_tweets.start()


@client.slash_command(description="Create a distribution list / Check your distribution list.")
async def distrib_list(ctx):
    if not check_tweets.is_running():
        check_tweets.start()
    #if user doesn't have a distribution list, create it
    if db.record("SELECT discordID FROM users WHERE discordID = ?", ctx.author.id) == None:
        db.execute("INSERT INTO users VALUES (?,0,0,0)", ctx.author.id)
        db.save()
        embed = discord.Embed(title = "Creating distribution list...", description = f"Please type **/link_twitter** to link a twitter account to the distribution list.", colour=0xffffff)
        await ctx.send(embed=embed)
    #if user has a distribution list share the list members
    else:
        users = db.records("SELECT userID FROM distribList WHERE hostID = ?", ctx.author.id)
        l = ""
        for u in users:
            l += f"\n <@{u[0]}>"
        embed = discord.Embed(title = "Distribution List Members", description = f'The following members belong to your distribution list: {l}', colour=0xffffff)
        await ctx.send(embed=embed)


@client.slash_command(description="Links a twitter account to your distribution list.")
async def link_twitter(ctx, twitter_user: Option(str, "Input the twitter handle of the account that will be linked.")):
    #if user doesn't have a distribution list, force them to create one
    if db.record("SELECT discordID FROM users WHERE discordID = ?", ctx.author.id) == None:
        embed = discord.Embed(title = "Configuration Error", description = f"{ctx.author.mention} doesn't have a distribution list yet. Use the  /distrib_list  command to create one.", colour=0xd14d4d)
        await ctx.send(embed=embed)
    else:
        if twitter_user[0] == "@":
            twitter_user = twitter_user[1:]
        twitterID = get_user_id(twitter_user)
        db.execute("UPDATE users SET twitterID = ? WHERE discordID = ?", twitterID, ctx.author.id)
        db.save()
        embed = discord.Embed(title = "Distribution list created!", description = f'{ctx.author.mention} has created a new distribution list for [{twitter_user}](https://twitter.com/{twitter_user}). \n To add new members to the distribution list use the **?add** command.', colour=0x5fe3a6)
        await ctx.send(embed=embed)

@client.slash_command(description='Add a discord user to your distribution list.')
async def add(ctx, tag_discord_member: Option(discord.Member, "Tag the discord user that you want to add to the distribution list.")):
    if not check_tweets.is_running():
        check_tweets.start()
    
    users = db.record("SELECT discordID FROM users WHERE discordID = ?", ctx.author.id)
    if users == None:
        embed = discord.Embed(title = "Configuration Error", description = f"Before adding users to your distribution list you must configure your list! Use the  /distrib_list  command and follow the instructions.", colour=0xd14d4d)
        await ctx.send(embed=embed)

    else:
        db.execute("INSERT INTO distribList VALUES (?,?)", tag_discord_member.id, ctx.author.id)
        db.save()
        embed = discord.Embed(title = "New User Configured", description = f'{tag_discord_member.mention} has been added to your distribution list. If you want to see the whole list you can use the **?distrib_list** command.', colour=0x5fe3a6)
        await ctx.send(embed=embed)

@client.slash_command(description='Delete a discord user from your distribution list.')
async def remove(ctx, tag_discord_member: discord.Member):
    users = db.record("SELECT discordID FROM users WHERE discordID = ?", ctx.author.id)
    if users == None:
        embed = discord.Embed(title = "Configuration Error", description = f"Before removing users to your distribution list you must configure your list! Use the **?distrib_list** command and follow the instructions.", colour=0xd14d4d)
        await ctx.send(embed=embed)

    users = db.record("SELECT userID FROM distribList WHERE userID = ? AND hostID = ?", tag_discord_member.id, ctx.author.id)
    if users == None:
        embed = discord.Embed(title = "Configuration Error", description = f"{tag_discord_member.mention} does not belong to your distribution list.", colour=0xd14d4d)
        await ctx.send(embed=embed)

    else:
        db.execute("DELETE FROM distribList WHERE userID = ? AND hostID = ?", tag_discord_member.id, ctx.author.id)
        db.save()
        embed = discord.Embed(title = "User Removed", description = f'{tag_discord_member.mention} has been removed from the distribution list of [{twitterUser}](https://twitter.com/{twitterUser}). If you want to see the whole list you can use the **?distrib_list** command.', colour=0x5fe3a6)
        await ctx.send(embed=embed)

@client.slash_command(description='Unsubscribe from all distribution lists.')
async def unsuscribe(ctx):
    hosts = db.records("SELECT * FROM distribList WHERE userID = ?", ctx.author.id)
    if hosts == []:
        embed = discord.Embed(title = "Configuration Error", description = f"You don't belong to any distribution lists.", colour=0xd14d4d)
        await ctx.send(embed=embed)

    else:
        for h in hosts:
            db.execute("DELETE FROM distribList WHERE hostID = ? AND userID = ?", h[0], h[1])
            db.save()
            embed = discord.Embed(title = "Successfully Unsubscrided", description = f'{ctx.author.mention} has been removed from all the distribution lists.', colour=0x5fe3a6)
            await ctx.send(embed=embed)

@tasks.loop(seconds = 60)
async def check_tweets():
    hosts = db.records("SELECT * FROM users")
    print(hosts)
    for h in hosts:
        if h[2] == 0:
            author, last_tweet, last_at = get_user_tweets(h[1], h[2], h[3])
        else:
            author, last_tweet, last_at = get_user_tweets(h[1], h[2], datetime.datetime.strptime(h[3], "%Y-%m-%d %H:%M:%S%z"))
        #update last tweet info
        db.execute("UPDATE users SET lastTweet = ?, lastAt = ? WHERE discordID = ? AND twitterID = ?", last_tweet, last_at, h[0], h[1])
        db.save()

        if last_tweet != h[2]:
            users = db.records("SELECT userID FROM distribList WHERE hostID = ?", h[0])
            print(users)
            embed = discord.Embed(title = "Tweet Alert!", description = f"Check out this [new tweet](https://twitter.com/{author['screen_name']}/status/{last_tweet}) made by <@{h[0]}>.", colour=0xffffff)
            embed.set_footer(text = 'If you want to no longer receive alerts, type /unsubscribe. \nIf you want to have your own distribution list, DM @0xRusowsky')
            for user_id in users:
                user = client.get_user(user_id[0])
                await user.send(embed=embed)


client.run(discordBotKey)
