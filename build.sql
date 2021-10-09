CREATE TABLE IF NOT EXISTS users (
    discordID integer PRIMARY KEY,
    twitterID integer DEFAULT 0,
    lastTweet integer DEFAULT 0,
    lastAt timestamp DEFAULT NULL
);

CREATE TABLE IF NOT EXISTS distribList (
    userID integer PRIMARY KEY,
    hostID integer DEFAULT 0
);
