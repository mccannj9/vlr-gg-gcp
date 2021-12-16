import parsel
import requests

from typing import Optional

from requests.models import HTTPError

from valorant_scraper_gcp import (
    match_results_url, local_timezone
)


class ValorantResults:
    def __init__(self) -> None:
        self.session: requests.Session = requests.Session()
        self.current_page: int = 1
        self.max_pages: Optional[int] = None
        self.status_code: Optional[int] = None
        
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

    def request(self) -> Optional[requests.models.Response]:
        with self.session as sesh:
            response = sesh.get(match_results_url.format(page=self.current_page))

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
            raise HTTPError(f"Response error: status code was {self.status_code}")

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

                yield match_data

        self.current_page += 1