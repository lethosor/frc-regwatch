import base64
import http
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

import requests
import tenacity
from tqdm import tqdm


@dataclass
class Event:
    key: str  # == str(year) + code
    code: str
    year: int

    @classmethod
    def from_key(cls, key: str):
        return cls(key=key, year=int(key[:4]), code=key[4:])

    @classmethod
    def from_year_and_code(cls, year: int, code: str):
        return cls(key=str(year) + code, year=year, code=code)


def wrap_retry_requests(func):
    return tenacity.retry(
        stop=tenacity.stop_after_attempt(3),
        wait=tenacity.wait_exponential(multiplier=1, min=4, max=10),
        retry=tenacity.retry_if_exception(
            lambda e: (
                isinstance(e, requests.exceptions.RequestException)
                and not (
                    isinstance(e, requests.exceptions.HTTPError)
                    and 400 <= e.response.status_code <= 499
                )
            )
        ),
    )(func)


def tqdm_dynamic_description(iterable, *, get_description, **kwargs):
    bar = tqdm(iterable, **kwargs)
    for item in bar:
        bar.set_description(get_description(item))
        yield item


class Client:
    thread_count = 3

    def get_all_events(self, year: int) -> list[Event]:
        raise NotImplementedError

    def get_event_teams(self, event: Event) -> list[int]:
        raise NotImplementedError

    def get_all_event_teams(self, year: int) -> dict[str, list[int]]:
        events = wrap_retry_requests(self.get_all_events)(year)
        self.validate_events(events)
        results = list(
            tqdm_dynamic_description(
                ThreadPoolExecutor(max_workers=self.thread_count).map(
                    wrap_retry_requests(
                        lambda event: (event, self.get_event_teams(event))
                    ),
                    events,
                ),
                get_description=lambda event_and_teams: event_and_teams[0].key,
                total=len(events),
                unit="events",
            )
        )
        return {event.key: sorted(teams) for (event, teams) in results}

    def validate_events(self, events: list[Event]):
        seen_keys = set()
        duplicate_keys = []
        for event in events:
            if event.key in seen_keys:
                duplicate_keys.append(event.key)
            seen_keys.add(event.key)
        if duplicate_keys:
            raise ValueError(f"Duplicate event keys: {duplicate_keys!r}")


class TBAClient(Client):
    def __init__(self):
        with open(os.environ.get("TBA_KEY_PATH", ".tba.key")) as f:
            self.api_key = f.read().strip()

    def get_all_events(self, year):
        res = self._request(f"events/{year}")
        return [Event.from_key(event["key"]) for event in res]

    def get_event_teams(self, event):
        try:
            res = self._request(f"event/{event.key}/teams/keys")
        except requests.HTTPError as e:
            if e.response.status_code == 404:
                return []
        return [int(team_key.removeprefix("frc")) for team_key in res]

    def _request(self, route):
        res = requests.get(
            f"https://www.thebluealliance.com/api/v3/{route.lstrip('/')}",
            headers={
                "X-TBA-Auth-Key": self.api_key,
            },
        )
        res.raise_for_status()
        return res.json()


class FRCClient(Client):
    def __init__(self):
        with open(os.environ.get("FRC_KEY_PATH", ".frc.key")) as f:
            self.api_user, self.api_key = f.read().strip().split(":")

    def get_all_events(self, year):
        res = self._request(f"{year}/events")
        return [
            Event.from_year_and_code(year, event["code"].lower())
            for event in res["Events"]
        ]

    def get_event_teams(self, event):
        try:
            res = self._request(
                f"{event.year}/teams", {"eventCode": event.code.upper()}
            )
        except requests.HTTPError as e:
            if e.response.status_code == 404:
                return []
        return [int(team["teamNumber"]) for team in res["teams"]]

    def _request(self, route, params=None):
        res = requests.get(
            f"https://frc-api.firstinspires.org/v3.0/{route.lstrip('/')}",
            params=params,
            headers={
                "Authorization": "Basic "
                + base64.b64encode(f"{self.api_user}:{self.api_key}".encode()).decode(),
            },
        )
        res.raise_for_status()
        return res.json()


class DummyClient(Client):
    def get_all_events(self, year):
        return [
            Event.from_key(f"{year}test1"),
            Event.from_year_and_code(year, "test2"),
            Event.from_year_and_code(year, "test3"),
            Event.from_year_and_code(year, "test4"),
        ]

    def get_event_teams(self, event):
        import time

        time.sleep(0.5)
        return [
            int(event.key[-1]),
            int(event.key[-1]) * 111,
            int(event.key[-1]) * 11,
        ]
