CREATE TABLE IF NOT EXISTS log(
    chat_id VARCHAR(9),
    source VARCHAR(64),
    artist VARCHAR(64),
    title VARCHAR (128),
    album VARCHAR (128) default "unknown",
    date float,
    CONSTRAINT PK_log PRIMARY KEY (chat_id,artist,title)
);

CREATE TABLE IF NOT EXISTS sp_tokens(
    chat_id VARCHAR(9) NOT NULL,
    token VARCHAR(512),
    refresh VARCHAR(512),
    expires INT,
    CONSTRAINT PK_sp_tokens PRIMARY KEY (chat_id)
);
