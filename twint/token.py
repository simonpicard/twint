import re
import time

import requests
import logging as logme

from . import url

import json
from io import StringIO


class TokenExpiryException(Exception):
    def __init__(self, msg):
        super().__init__(msg)


class RefreshTokenException(Exception):
    def __init__(self, msg):
        super().__init__(msg)


class Token:
    def __init__(self, config):
        self._session = requests.Session()
        self._session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36"
            }
        )
        self.config = config
        self._retries = 5
        self._timeout = 10
        self.url = "https://twitter.com"

    def _request(self):
        search_url = "https://twitter.com/search?q=" + self.config.Search

        req = self._session.prepare_request(
            requests.Request("GET", search_url)
        )
        r = self._session.send(
            req, allow_redirects=True, timeout=self._timeout
        )

        headers = {
            "accept": "*/*",
            "accept-encoding": "gzip, deflate, br",
            "accept-language": "en-GB,en;q=0.9",
            "authorization": "Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA",
            "content-length": "0",
            "content-type": "application/x-www-form-urlencoded",
            "origin": "https://twitter.com",
            "referer": "https://twitter.com/",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-site",
            "sec-gpc": "1",
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36",
            "x-twitter-active-user": "yes",
            "x-twitter-client-language": "en-GB",
        }
        self._session.headers.update(headers)

        activate_url = "https://api.twitter.com/1.1/guest/activate.json"

        req = self._session.prepare_request(
            requests.Request("POST", activate_url)
        )

        r = self._session.send(req, allow_redirects=True, timeout=10)

        gt = json.load(StringIO(r.text))["guest_token"]
        return gt

    def _request_bkp(self):
        for attempt in range(self._retries + 1):
            # The request is newly prepared on each retry because of potential cookie updates.
            req = self._session.prepare_request(
                requests.Request("GET", self.url)
            )
            logme.debug(f"Retrieving {req.url}")
            try:
                r = self._session.send(
                    req, allow_redirects=True, timeout=self._timeout
                )
            except requests.exceptions.RequestException as exc:
                if attempt < self._retries:
                    retrying = ", retrying"
                    level = logme.WARNING
                else:
                    retrying = ""
                    level = logme.ERROR
                logme.log(
                    level, f"Error retrieving {req.url}: {exc!r}{retrying}"
                )
            else:
                success, msg = (True, None)
                msg = f": {msg}" if msg else ""

                if success:
                    logme.debug(f"{req.url} retrieved successfully{msg}")
                    return r
            if attempt < self._retries:
                # TODO : might wanna tweak this back-off timer
                sleep_time = 2.0 * 2 ** attempt
                logme.info(f"Waiting {sleep_time:.0f} seconds")
                time.sleep(sleep_time)
        else:
            msg = f"{self._retries + 1} requests to {self.url} failed, giving up."
            logme.fatal(msg)
            self.config.Guest_token = None
            raise RefreshTokenException(msg)

    def refresh(self):
        logme.debug("Retrieving guest token")
        res = self._request()
        self.config.Guest_token = res

    def refresh_bkp(self):
        logme.debug("Retrieving guest token")
        res = self._request()
        match = re.search(r'\("gt=(\d+);', res.text)
        for attempt in range(self._retries):
            if match:
                logme.debug("Found guest token in HTML")
                self.config.Guest_token = str(match.group(1))
                break
            else:
                sleep_time = 2.0 ** (attempt + 1)
                logme.info(
                    f"TWINT GUEST TOKEN: Waiting {sleep_time:.0f} seconds"
                )
                time.sleep(sleep_time)

        else:
            self.config.Guest_token = None
            raise RefreshTokenException(
                "Could not find the Guest token in HTML"
            )
