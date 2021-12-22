import time

from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional

import parsel
import requests

from requests.models import HTTPError
from sqlalchemy import create_engine, desc, exc
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql.expression import except_


from valorant_scraper_gcp import (
    match_results_url, local_timezone, ts_string
)

from valorant_scraper_gcp.database.models import (
    valorant_scraper_base, Matches
)


class ValorantResults:
    def __init__(self, sqlite_db_path: str, request_delay: int = 1) -> None:
        self.session: requests.Session = requests.Session()
        self.current_page: int = 1
        self.max_pages: Optional[int] = None
        self.status_code: Optional[int] = None
        self.delay = request_delay
        
        self.selectors = {
            # relative to root or whole doc search
            'label': "//div[@class='wf-label mod-large']",
            'card': "//div[@class='wf-card']",
            # relative to label
            'match_item': "./a[contains(@class, 'wf-module-item match-item')]",
            # relative to card
            'match_time': "./div[@class='match-item-time']/text()",
            'match_event': "./div[@class='match-item-event text-of']/text()",
            'match_stakes': (
                "./div[@class='match-item-event text-of']/div"
                "[@class='match-item-event-series text-of']/text()"
            ),
            'match_stats': (
                "./div[@class='match-item-vod']/div[@class='wf-tag mod-big']/text()"
            )
        }

        self.sqlite_db_path = sqlite_db_path
        self.engine = create_engine(f"sqlite:///{self.sqlite_db_path}")
        self.db_session_maker = sessionmaker(bind=self.engine)
        # makes sure tables are created (if not already)
        valorant_scraper_base.metadata.create_all(self.engine)

        # get most recent match
        with self.db_session_maker() as sesh:
            self.latest_match: Optional[datetime] = (
                sesh
                .query(Matches.timestamp)
                .order_by(desc('timestamp'))
                .first()
            )

        if self.latest_match is None:
            # set date to earliest date if database is freshly made
            self.latest_match = datetime(1970, 1, 1, tzinfo=timezone(timedelta(seconds=3600), 'UTC'))
        
        else:
            # have to get it out of the tuple
            self.latest_match = self.latest_match[0].astimezone(
                timezone(timedelta(seconds=3600), 'UTC')
            )

        self.new_matches: bool = True

    def request(self) -> Optional[requests.models.Response]:
        with self.session as sesh:
            response = sesh.get(
                match_results_url.format(page=self.current_page)
            )

        if response.status_code != 200:
            self.status_code = response.status_code
            return None

        if self.max_pages is None:
            self.max_pages = int(
                parsel
                .Selector(response.text)
                .xpath("//a[@class='btn mod-page'][last()]/text()")
                .get()
            )

        return response

    def parse_response(self):
        response = self.request()

        if response is None:
            raise HTTPError(
                f"Response error: status code was {self.status_code}"
            )

        response_selector = parsel.Selector(response.text)
        for label, card in zip(
            response_selector.xpath(self.selectors['label']),
            response_selector.xpath(self.selectors['card'])
        ):
            match_data = {}
            match_data["page"] = self.current_page
            _date = "".join(label.xpath("./text()").getall()).strip()
            for match in card.xpath(self.selectors['match_item']):
                match_data['url'] = match.attrib['href']
                match_data['match_id'] = int(match.attrib['href'].split("/")[1])
                match_data["map_stats"] = False
                match_data["player_stats"] = False
                match_data["other_stats"] = False

                _time = (
                    match
                    .xpath(self.selectors['match_time'])
                    .get()
                    .strip()
                )

                match_data['timestamp'] = f"{_date}, {_time} {local_timezone}"
                match_data["event"] = "".join(
                    match.xpath(self.selectors['match_event']).getall()
                ).strip()

                match_data["stakes"] = (
                    match
                    .xpath(self.selectors['match_stakes'])
                    .get()
                    .strip()
                )

                for stat in match.xpath(self.selectors['match_stats']).getall():
                    match_data[f"{stat.strip().lower()}_stats"] = True
                
                self.process_item(match_data)

                if not(self.new_matches):
                    # breaks out of both loops at once ;)
                    return

                yield match_data

    def process_item(self, item: Dict[str, Any]):
        # replace text timestamp with datetime object for sqlite
        try:
            item['timestamp'] = datetime.strptime(
                item['timestamp'], ts_string
            )

        except ValueError:
            print(f"Timedelta error occurred on {item}")
            return None

        match_more_recent = item['timestamp'] >= self.latest_match

        if match_more_recent:
            # should catch the case where matches occur at the same datetime
            try:
                with self.db_session_maker() as sesh:
                    sesh.add(Matches(**item))
                    sesh.commit()

            # but it will fail if match_id is the same, bc it's not a different match            
            except exc.IntegrityError:
                print(f"Duplicate Match ID <{item['match_id']}> Found")
                self.new_matches = False
        
        else:
            self.new_matches = False

    def retrieve_matches_from_page_range(self, start: int, end: int) -> None:
        for i in range(start, end + 1):
            time.sleep(self.delay)
            self.current_page = i
            print(self.current_page)
            for _ in self.parse_response():
                pass

    def update_matches_database(self) -> None:
        if self.current_page != 1:
            print("Don't play with current_page attribute when using this method!\nExiting!")
            return None

        while self.new_matches:
            time.sleep(self.delay)
            print(f"Extracting data from page {self.current_page}")
            for item in self.parse_response():
                print(item)
            self.current_page += 1