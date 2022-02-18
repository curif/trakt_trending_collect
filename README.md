
# trakt_trending_collect

Get trending movies, filter them by parameters and add the movies to an specified Trakt list. 

# Instalation

Download the code and copy to a directory of your preference. 

# Requeriments

Please read the `requirements.txt` to understand the dependencies.

Run de requirements install:

```bash
pip3 install -r requirements.txt
```
# config.json

Create a json file (you can copy the `config.json.example` in the `config/` path).

```json
{
    "schedule_hours": 12,
    "filters": {
		"from_year": 2019,
		"filter_list": [ {
			"trakt_ratings": [5.5, 5.99],
			"votes": 500,
			"include_genres": [ "horror", "science-fiction" ],
			"exclude_genres": [ "family", "biography", "comedy", "animation", "sports", "documentary", "short", "romance", "music", "anime" ],
			"exclude_providers": [ "Netflix", "HBO Max" ]
		}, {
			"trakt_ratings": [6, 6.99],
			"votes": 500,
			"include_genres": [ "suspense","thriller", "horror", "mystery", "action", "adventure", "crime", "science-fiction" ],
			"exclude_genres": [ "family", "biography", "animation", "sports", "documentary", "short", "romance", "music", "anime" ],
			"exclude_providers": [ "Netflix", "HBO Max" ]
		}, {
			"trakt_ratings": [7, 100],
			"votes": 500,
			"include_genres": [],
			"exclude_genres": [ "family", "biography", "animation", "sports", "documentary", "short", "romance", "music", "anime"],
			"exclude_providers": [ "Netflix", "HBO Max" ]
			}
      ]
    },
    "trakt": {
        "base_url": "https://api.trakt.tv",
        "id": "your id here",
        "secret": "your secret",
        "list": "MyList",
        "user": "MyTraktUser"
    },
}

```
* schedule_hours: time between executions
* filters: requeriments to select a movie.
    * from_year: ignore movies released before this year.
    * filter_list: list of filters to apply (in order)
        * imdb_range: from/to califications. A movie with Trakt califications between this range will be selected and added to the list.
        * imdb_people: minimal number of people who voted.
        * include_genres: the movie must to have at least one of those genres. Empty means "all"
        * exclude_genres: if the movie has at least one of those will be excluded. Empty means "all"
        * exclude_providers: a list of providers that you want to exclude, may be because you are subscribed to those providers.
* trakt: 
    * trakt connection information (see below)
    * list: a trakt user list where you add the movies of interest.
    
# Examples

In the configuration example above, a Drama movie with a calification of 8/17000 (17000 votes that result in a calification of eight) will be selected. Instead, if the movie is a 'biography' will be excluded.

An Horror movie with a calification of 5.5/600 will be selected. The same but anime horror will be excluded. It's usefull if you like Horror movies but not Animes.

This configuration catches any movie with a calification 6.5/1000 or above. But exclude Shorts for example.

# Trakt

You must give permissions to the application to be able to access with your Trakt user. Go to the the applications page in Trakt and create a new application, then grant access to obtain your `id` and `secret`.

Goto https://trakt.tv/oauth/applications/new

Copy the id and secret to your 'config.json'.


# Docker

A `dockerfile` is provided in order to use the program under docker.

## docker create image

`docker build -t trakt-trending-collect .`

## docker-compose example

```yaml
  trakt_trending_collect:
    build:
      context: /home/curif/docker/trakt_trending_collect
    image: trakt-trending-collect:latest
    volumes:
     - /home/curif/docker/trakt_trending_collect/config:/usr/src/app/config
    environment:
      TZ: America/Argentina/Buenos_Aires
    restart: unless-stopped

```

