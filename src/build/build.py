from datetime import datetime
import argparse
import glob
import logging
import os
import re
import shutil
import time
import yaml

from bs4 import BeautifulSoup
import jinja2
import requests

import traitlets.config

import nbformat
from nbconvert import HTMLExporter
from nbconvert.writers.files import FilesWriter
from nbconvert.nbconvertapp import NbConvertApp

import processors


class Application:
    def __init__(self, base_path, config, metadata):
        self.base_path = base_path
        self.config = config
        self.metadata = metadata

        self.logger = logging.getLogger("Builder")
        self.logger.setLevel(logging.INFO)
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(name)-20s ┊ %(message)s"))
        self.logger.addHandler(handler)

        self._converter = NbConvertApp()
        self._converter.config = self.config
        self._converter.log_format = "%(name)-20s ┊ %(message)s"

        self._converter.export_format = "html"
        self._converter.exporter = HTMLExporter(self._converter.config)

        self._converter.writer = FilesWriter()
        self._converter.output_base = "index"

        self._converter.exporter.environment.globals.update(self.metadata)
        self._converter.exporter.environment.filters[
            "datetime_format"
        ] = TemplateHelpers.datetime_format

    def get_base_path(self, *args):
        return os.path.join(self.base_path, *args)

    def generate_homepage(self, html_path, output_dir):
        self.logger.info("Generating homepage...")
        self.logger.info(80 * "┄")
        generator = HomepageGenerator(self)
        generator.generate(html_path, output_dir)

    def generate_notebooks(self, notebooks_path, output_dir):
        self.logger.info("Converting notebooks to HTML...")
        self.logger.info(80 * "┄")
        generator = NotebookGenerator(self)
        for notebook_path in notebooks_path:
            self._converter.writer.build_directory = output_dir
            generator.generate(notebook_path, output_dir)

    def clear_cache(self):
        self.logger.info("Clearing cache...")
        self.logger.info(80 * "┄")
        cleaner = CacheCleaner(self)
        cleaner.clear_cache()


class Config:
    @staticmethod
    def get_config():
        config = traitlets.config.get_config()

        config.TemplateExporter.template_name = "nbconvert"

        config.TemplateExporter.extra_template_basedirs = [
            os.path.join(os.path.dirname(os.path.realpath(__file__)), "templates"),
        ]

        config.TemplateExporter.extra_template_paths = [
            os.path.join(
                os.path.dirname(os.path.realpath(__file__)), "templates", "common"
            )
        ]

        config.Exporter.preprocessors = [
            processors.update_metadata.Preprocessor,
            processors.remove_cells.Preprocessor,
            processors.remove_output.Preprocessor,
            processors.remove_stderr.Preprocessor,
        ]

        return config

    @staticmethod
    def get_metadata(args: argparse.Namespace):
        metadata = {
            "site_name": "nb.karmi",
            "site_hostname": "https://nb.karmi.cz",
            "site_title": "Notebooks • nb.karmi.cz",
            "site_description": "A journal of a journey, written&nbsp;by&nbsp;<a href='https://karmi.cz'>Karel&nbsp;Minařík</a>.",
            "github_url": "https://github.com/karmi/notebooks",
            "generated_on": datetime.utcnow(),
            "build_drafts": re.match("ye?s?|true", args.draft, re.IGNORECASE),
        }

        if os.getenv("GA_ID"):
            metadata["google_analytics_id"] = os.getenv("GA_ID")

        if os.getenv("CF_PAGES_COMMIT_SHA"):
            metadata["commit_sha"] = os.getenv("CF_PAGES_COMMIT_SHA")

        return metadata


class HomepageGenerator:
    def __init__(self, app: Application):
        self.app = app

    def get_metadata(self, file):
        with open(file, "r") as f:
            soup = BeautifulSoup(f, "html.parser")

        meta = soup.find_all("meta")
        data = {}

        for tag in meta:
            if "property" in tag.attrs:
                if tag.attrs["property"].lower() in [
                    "og:title",
                    "og:description",
                    "og:article:published_time",
                ]:
                    data[tag.attrs["property"].lower()] = tag.attrs["content"]

        return data

    def generate(self, html_path, output_dir):
        file_loader = jinja2.FileSystemLoader(
            [
                self.app.get_base_path("templates", "homepage"),
                self.app.get_base_path("templates", "common"),
            ]
        )
        env = jinja2.Environment(loader=file_loader)

        metadata_list = []
        for html_file in html_path:
            self.app.logger.info(f"Processing '{html_file}'")
            metadata = self.get_metadata(html_file)
            metadata["dirname"] = os.path.split(os.path.dirname(html_file))[-1]
            metadata_list.append(metadata)

            metadata_list = sorted(
                metadata_list,
                key=lambda x: datetime.strptime(
                    x.get("og:article:published_time", "1900-01-01"), "%Y-%m-%d"
                ),
                reverse=True,
            )

        data = {
            "pages": metadata_list,
            "globals": self.app.metadata,
        }

        template = env.get_template("index.html.j2")
        template.environment.globals.update(data["globals"])
        template.environment.filters[
            "datetime_format"
        ] = TemplateHelpers.datetime_format

        output = template.render(pages=data["pages"])

        with open(os.path.join(output_dir, "index.html"), "w") as file:
            file.write(output)

        self.copy_assets(output_dir)

    def copy_assets(self, output_dir):
        source_to_dest = {
            ("templates", "homepage", "css"): ("css",),
            ("templates", "common", "assets"): ("assets",),
            ("templates", "common", "pages", "404.html"): ("404.html",),
            ("templates", "common", "assets", "icons", "favicon.ico"): ("favicon.ico",),
        }

        for src, dst in source_to_dest.items():
            src_path = self.app.get_base_path(*src)
            dest_path = os.path.join(output_dir, *dst)

            if os.path.isdir(src_path):
                shutil.copytree(src_path, dest_path, dirs_exist_ok=True)
            else:
                shutil.copyfile(src_path, dest_path)


class NotebookGenerator:
    def __init__(self, app: Application):
        self.app = app

    def get_metadata(self, nb):
        tag = "metadata"
        for cell in nb["cells"]:
            if "tags" in cell["metadata"] and tag in cell["metadata"]["tags"]:
                # Remove the comment character (#) and extra whitespace
                source = "\n".join(
                    [
                        line.strip()[1:].strip()
                        for line in cell["source"].split("\n")
                        if line.startswith("#")
                    ]
                )
                return yaml.safe_load(source)
            else:
                return {}

    def generate(self, notebook_path, output_dir):
        nb = nbformat.read(notebook_path, as_version=4)
        metadata = self.get_metadata(nb)
        if metadata.get("draft") and not self.app.metadata["build_drafts"]:
            self.app.logger.info(f"Skipping draft '{notebook_path}'")
        else:
            self.app._converter.output_files_dir = os.path.join(
                output_dir, os.path.splitext(os.path.basename(notebook_path))[0]
            )
            self.app._converter.writer.build_directory = (
                self.app._converter.output_files_dir
            )
            self.app._converter.exporter.environment.globals.update(
                {"notebook_filename": os.path.basename(notebook_path)}
            )
            self.app._converter.convert_single_notebook(notebook_path)

            if metadata.get("cover"):
                filepath = metadata.get("cover")[1:]
                os.makedirs(
                    os.path.dirname(os.path.join(output_dir, filepath)), exist_ok=True
                )
                shutil.copyfile(
                    self.app.get_base_path("..", "..", "content", filepath),
                    os.path.join(output_dir, filepath),
                )


class CacheCleaner:
    def __init__(self, app: Application):
        self.app = app

    def clear_cache(self):
        if os.getenv("CLOUDFLARE_ZONE_ID"):
            cloudflare_zone_id = os.getenv("CLOUDFLARE_ZONE_ID")
        else:
            raise RuntimeError("The environment variable CLOUDFLARE_ZONE_ID is not set")

        if os.getenv("CLOUDFLARE_API_KEY"):
            cloudflare_api_key = os.getenv("CLOUDFLARE_API_KEY")
        else:
            raise RuntimeError("The environment variable CLOUDFLARE_API_KEY is not set")

        url = f"https://api.cloudflare.com/client/v4/zones/{cloudflare_zone_id}/purge_cache"

        response = requests.request(
            "POST",
            url,
            json={"purge_everything": True},
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {cloudflare_api_key}",
            },
        )

        if response.status_code > 200:
            error_message = "".join(e["message"] for e in response.json()["errors"])
            self.app.logger.error(
                f"Error making request to Cloudflare: {error_message}"
            )
            raise RuntimeError(f"HTTP Error: [{response.status_code}] {error_message}")
        else:
            self.app.logger.info("Succesfully cleared the Cloudflare cache")


class TemplateHelpers:
    @staticmethod
    def datetime_format(value, format="%d/%m/%Y"):
        try:
            getattr(value, "strftime")
        except AttributeError:
            value = datetime.fromisoformat(value)
        return value.strftime(format)


def main(args: argparse.Namespace):
    start = time.perf_counter()
    app = Application(
        base_path=os.path.dirname(os.path.realpath(__file__)),
        config=Config.get_config(),
        metadata=Config.get_metadata(args),
    )

    app.logger.info("─" * 80)
    app.generate_notebooks(
        glob.glob(os.path.join(args.input_dir, "*.ipynb")),
        args.output_dir,
    )

    app.logger.info("─" * 80)
    app.generate_homepage(
        glob.glob(os.path.join(args.output_dir, "**", "index.html")),
        args.output_dir,
    )

    if re.match("ye?s?|true", args.clear_cache, re.IGNORECASE):
        app.logger.info("─" * 80)
        app.clear_cache()

    app.logger.info("─" * 80)
    app.logger.info(f"Duration: {time.perf_counter()-start:0.2f}sec")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input_dir",
        help="Directory containing Jupyter notebooks",
        required=True,
    )
    parser.add_argument(
        "--output_dir",
        help="Directory to write exported notebooks",
        required=True,
    )
    parser.add_argument(
        "--draft",
        help="Whether to build draft notebooks",
        default="false",
    )
    parser.add_argument(
        "--clear-cache",
        help="Whether to clear Cloudflare cache",
        default="false",
    )
    args = parser.parse_args()

    main(args)
