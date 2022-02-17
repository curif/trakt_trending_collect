from __future__ import absolute_import, division, print_function
import sys
from typing import Optional

from trakt import Trakt

import schedule
import time

from threading import Condition
import logging
import os
import json
from imdb import Cinemagoer

import pprint

logging.basicConfig(format='%(asctime)s [%(levelname)s] %(message)s', level=logging.DEBUG)

config = {}

pp = pprint.PrettyPrinter(indent=2)


def intersection(lst1, lst2):
    lst3 = [value for value in lst1 if value in lst2]
    return lst3


class Application(object):
    def __init__(self):
        self.is_authenticating = Condition()

        self.authorization = None

        # Bind trakt events
        Trakt.on('oauth.token_refreshed', self.on_token_refreshed)

    def authenticate(self):
        if not self.is_authenticating.acquire(blocking=False):
            logging.info('Authentication has already been started')
            return False

        # Request new device code
        code = Trakt['oauth/device'].code()

        print('Enter the code "%s" at %s to authenticate your account' % (
            code.get('user_code'),
            code.get('verification_url')
        ))

        # Construct device authentication poller
        poller = Trakt['oauth/device'].poll(**code) \
            .on('aborted', self.on_aborted) \
            .on('authenticated', self.on_authenticated) \
            .on('expired', self.on_expired) \
            .on('poll', self.on_poll)

        # Start polling for authentication token
        poller.start(daemon=False)

        # Wait for authentication to complete
        return self.is_authenticating.wait()

    def run(self):
        if not self.authorization:
            self.authenticate()

        if not self.authorization:
            logging.error('ERROR: Authentication required')
            exit(1)

        # STrakt.configuration.oauth.from_response(self.authorization)
        Trakt.configuration.defaults.oauth.from_response(self.authorization, refresh=True)

        # ('imdb', 'tt1815862'): <Movie 'After Earth' (2013)>
        logging.info("Retrieve trending from trakt")
        watched = {}
        watched = Trakt['sync/watched'].movies(watched,
                                               extended="full",
                                               exceptions=True)
        logging.info("{} movies retrieved".format(len(watched.keys())))
        """
        for k, movie in watched.items():
          pp.pprint([k, movie.title, movie.rating.votes, movie.is_watched])
          pp.pprint(movie.rating)
        """

        # get trending movies
        ia = Cinemagoer()
        def getImdbPK(movie):
            for k in movie.keys:
                if k[0] == 'imdb':
                    return k[1]
            return None
        def getImdb(movie):
            k = getImdbPK(movie)
            if k:
                return ia.get_movie(str.replace(k, 'tt', ''))
            return None

        nonWatchedTrending = {}
        trending = Trakt['movies'].trending(pagination=True, extended="full", per_page=25)
        for page in range(1, 20):
            for movie in trending.get(page):

                #pp.pprint([movie.title, movie.is_watched])
                if movie.pk in watched and watched[movie.pk].is_watched:
                    #logging.info("{} already watched".format(movie.title))
                    continue
                if movie.year < config["filters"]["from_year"]:
                    continue

                movie.__setattr__("distributors", [])
                movie.__setattr__("add_to_list", False)
                imdbMovie = getImdb(movie)
                if imdbMovie:
                    movie.distributors = [distri.data['name'] for distri in imdbMovie.data.get("distributors", [])]

                nonWatchedTrending[movie.pk] = movie

        logging.info("{} trending".format(len(nonWatchedTrending)))

        toBeAdded={}
        for fil in config["filters"]["filter_list"]:
            for moviePK, movie in nonWatchedTrending.items():
                if moviePK in toBeAdded:
                    continue

                if not ((len(fil["include_genres"]) == 0 or
                         len(intersection(movie.genres, fil["include_genres"])) > 0)
                        and (len(fil["exclude_genres"]) == 0 or
                             len(intersection(movie.genres, fil["exclude_genres"])) == 0)):
                    logging.debug(
                        "{} will not be added to the Trakt list because genres don't match: {}".format(movie.title,
                                                                                                       movie.genres))
                    continue

                if not movie.rating:
                    continue
                if not (fil["trakt_ratings"][0] <= movie.rating.value <= fil["trakt_ratings"][1]
                        and movie.rating.votes >= fil["votes"]):
                    continue

                logging.info(movie.distributors)
                if len(intersection(movie.distributors, fil['exclude_providers'])) > 0:
                    continue

                logging.info("will be added to the Trakt list ({}({}) - genres: {} - rating: {})".format(
                    movie.title, movie.released, movie.genres, movie.rating
                ))
                movie.add_to_list = True

        to_add = {"movies": [
            {"ids": {
                'imdb': getImdbPK(movie)
            }
            } for movie in nonWatchedTrending.values() if movie.add_to_list
        ]
        }
        logging.info("Add movies to list [{}]".format(config["trakt"]["list"]))
        if len(to_add["movies"]) > 0:
            logging.info(pprint.pformat(to_add))
            result = Trakt['users/*/lists/*'].add(
                config["trakt"]["user"],
                config["trakt"]["list"],
                to_add,
                exceptions=True
            )
            logging.info("{} added to the list".format(result["added"]["movies"]))
            logging.info("not found: {}".format(pprint.pformat(result["not_found"]["movies"])))
        else:
            logging.info("No new movies to add.")

        logging.info("Finished =====")

    def on_aborted(self):
        """Device authentication aborted.

        Triggered when device authentication was aborted (either with `DeviceOAuthPoller.stop()`
        or via the "poll" event)
        """

        print('Authentication aborted')

        # Authentication aborted
        self.is_authenticating.acquire()
        self.is_authenticating.notify_all()
        self.is_authenticating.release()

    def on_authenticated(self, authorization):
        """Device authenticated.

        :param authorization: Authentication token details
        :type authorization: dict
        """

        # Acquire condition
        self.is_authenticating.acquire()

        # Store authorization for future calls
        self.authorization = authorization

        print('Authentication successful - authorization: %r' % self.authorization)

        # Authentication complete
        self.is_authenticating.notify_all()
        self.is_authenticating.release()

        self.save_token()

    def on_expired(self):
        """Device authentication expired."""

        print('Authentication expired')

        # Authentication expired
        self.is_authenticating.acquire()
        self.is_authenticating.notify_all()
        self.is_authenticating.release()

    def on_poll(self, callback):
        """Device authentication poll.

        :param callback: Call with `True` to continue polling, or `False` to abort polling
        :type callback: func
        """

        # Continue polling
        callback(True)

    def on_token_refreshed(self, authorization):
        # OAuth token refreshed, store authorization for future calls
        self.authorization = authorization

        print('Token refreshed - authorization: %r' % self.authorization)
        self.save_token()

    def save_token(self):
        with open("config/authtoken.json", 'w') as outfile:
            json.dump(self.authorization, outfile)


def execute():
    app = Application()
    if os.path.exists("config/authtoken.json"):
        # authorization = os.environ.get('AUTHORIZATION')
        with open("config/authtoken.json", 'r') as file:
            app.authorization = json.load(file)
    app.run()


if __name__ == '__main__':
    # global config

    # Configure
    if not os.path.exists("config/config.json"):
        raise Exception("Error config.json not found")
    with open("config/config.json", 'r') as file:
        config = json.load(file)
        # print(config)

    Trakt.base_url = config["trakt"]["base_url"]

    Trakt.configuration.defaults.client(
        id=config["trakt"]["id"],
        secret=config["trakt"]["secret"],
    )

    # first auth
    if not os.path.exists("config/authtoken.json"):
        print('auth...')
        app = Application()
        app.authenticate()
        if not os.path.exists("config/authtoken.json"):
            print('Auth failed!')
            sys.exit(-1)

    execute()

    logging.info("Waiting...")

    schedule.every(config["schedule_hours"]).hours.do(execute)
    while True:
        schedule.run_pending()
        # print("waiting...")
        time.sleep(60)
