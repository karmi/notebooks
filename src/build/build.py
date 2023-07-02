import os
import argparse
import glob
import re
import shutil
import yaml

from datetime import datetime

import nbformat

from nbconvert import HTMLExporter
from nbconvert.writers.files import FilesWriter
from nbconvert.nbconvertapp import NbConvertApp

from bs4 import BeautifulSoup
from jinja2 import Environment, FileSystemLoader

from traitlets.config import get_config

import processors


# For Jinja templates
def datetime_format(value, format="%d/%m/%Y"):
    try:
        getattr(value, "strftime")
    except AttributeError:
        value = datetime.fromisoformat(value)
    return value.strftime(format)


def convert_single_notebook(app, notebook_path, output_dir):
    app.output_files_dir = os.path.join(
        output_dir, os.path.splitext(os.path.basename(notebook_path))[0]
    )
    app.writer.build_directory = app.output_files_dir
    app.convert_single_notebook(notebook_path)


def extract_metadata_from_html(file):
    with open(file, "r") as f:
        soup = BeautifulSoup(f, "html.parser")

    meta = soup.find_all("meta")
    # print(meta)

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


def get_frontmatter_from_notebook(nb):
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


def create_homepage(data, template_file, output_dir):
    file_loader = FileSystemLoader(
        [
            os.path.join(
                os.path.dirname(os.path.realpath(__file__)), "templates", "homepage"
            ),
            os.path.join(
                os.path.dirname(os.path.realpath(__file__)), "templates", "common"
            ),
        ]
    )
    env = Environment(loader=file_loader)

    print(data)

    template = env.get_template(template_file)
    template.environment.globals.update(data["globals"])
    template.environment.filters["datetime_format"] = datetime_format

    output = template.render(pages=data["pages"])

    with open(os.path.join(output_dir, "index.html"), "w") as file:
        file.write(output)

    shutil.copytree(
        os.path.join(
            os.path.dirname(os.path.realpath(__file__)),
            "templates",
            "homepage",
            "css",
        ),
        os.path.join(output_dir, "css"),
        dirs_exist_ok=True,
    )

    shutil.copytree(
        os.path.join(
            os.path.dirname(os.path.realpath(__file__)),
            "templates",
            "common",
            "assets",
        ),
        os.path.join(output_dir, "assets"),
        dirs_exist_ok=True,
    )


def main(input_dir, output_dir):
    build_drafts = re.match("ye?s?|true", args.draft, re.IGNORECASE)

    notebooks = glob.glob(os.path.join(input_dir, "*.ipynb"))

    config = get_config()

    config.TemplateExporter.template_name = "nbconvert"
    config.TemplateExporter.extra_template_basedirs = [
        os.path.join(os.path.dirname(os.path.realpath(__file__)), "templates"),
    ]
    config.TemplateExporter.extra_template_paths = [
        os.path.join(os.path.dirname(os.path.realpath(__file__)), "templates", "common")
    ]

    config.Exporter.preprocessors = [
        processors.update_metadata.Preprocessor,
        processors.remove_cells.Preprocessor,
        processors.remove_output.Preprocessor,
        processors.remove_stderr.Preprocessor,
    ]

    app = NbConvertApp()
    app.config = config

    app.export_format = "html"
    app.exporter = HTMLExporter(app.config)

    if os.getenv("GA_ID"):
        app.exporter.environment.globals["google_analytics_id"] = os.getenv("GA_ID")

    app.writer = FilesWriter()

    app.output_base = "index"

    for notebook_path in notebooks:
        nb = nbformat.read(notebook_path, as_version=4)
        metadata = get_frontmatter_from_notebook(nb)
        if metadata.get("draft") and not build_drafts:
            print(f"Skipping draft [{notebook_path}]")
        else:
            convert_single_notebook(app, notebook_path, output_dir)

    html_files = glob.glob(os.path.join(output_dir, "**/index.html"))

    metadata_list = []
    for html_file in html_files:
        print(f"Processing [{html_file}]")
        metadata = extract_metadata_from_html(html_file)
        metadata["dirname"] = os.path.split(os.path.dirname(html_file))[-1]
        metadata_list.append(metadata)

        metadata_list = sorted(
            metadata_list,
            key=lambda x: datetime.strptime(
                x.get("og:article:published_time", "1900-01-01"), "%Y-%m-%d"
            ),
            reverse=True,
        )

    payload = {
        "pages": metadata_list,
        "globals": {
            "site_name": "nb.karmi",
            "site_title": "Notebooks • nb.karmi.cz",
            "site_description": "A journal of a journey, written&nbsp;by&nbsp;<a href='https://karmi.cz'>Karel&nbsp;Minařík</a>.",
        },
    }

    if os.getenv("GA_ID"):
        payload["globals"]["google_analytics_id"] = os.getenv("GA_ID")

    create_homepage(payload, "index.html.j2", output_dir)


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
    args = parser.parse_args()

    main(args.input_dir, args.output_dir)
