from datetime import datetime

import bs4
from nbconvert.postprocessors import PostProcessorBase as Base


class Postprocessor(Base):
    def postprocess(self, input):
        self.log.info(f"Post-processing file '{input}'")

        with open(input, "r+") as f:
            html = f.read()
            soup = bs4.BeautifulSoup(html, "html.parser")

            self._add_published_date(soup)

            f.seek(0)
            f.write(str(soup))
            f.truncate()

    def _add_published_date(self, soup):
        published = soup.select_one("meta[property='og:article:published_time']")
        if not published:
            self.log.error(
                f"Skipping post-processing, cannot find 'meta[og:article:published_time]'"
            )
            return

        published_date_str = published.attrs["content"]
        tag = soup.new_tag("div", id="published_date")
        published_date = datetime.fromisoformat(published_date_str)
        tag.string = published_date.strftime("%d/%m/%Y")

        header = soup.select_one(".content h1:first-child")
        if not header:
            self.log.error(
                f"Skipping post-processing, cannot find '.content h1:first-child'"
            )
            return

        header.insert_before(tag)

        return soup
