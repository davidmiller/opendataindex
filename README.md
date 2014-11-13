# Open Data Index

This is the code that powers the [Open Data Index](http://index.okfn.org/), an [Open Knowledge](http://okfn.org/) initiative.

The Open Data Index displays a snapshot of data collected in an [Open Data Survey](http://census.okfn.org).

This new Index codebase was written for the [2014 Global Survey](http://global.census.okfn.org), and can be used with any survey powered by the [survey codebase](https://github.com/okfn/opendatacensus).

The code generates a static site using [Pelican](http://docs.getpelican.com), a Python-based static site generator.

## Setup

Getting setup with the code is easy if you have some familiarity with Python and virtualenv.

* Setup a virtualenv for the project
* Install the dependencies: `pip install -r requirements.txt`
* Install the CLI: `cd cli && python setup.py install && cd ../`
* Grab data from the database: `python scripts/process.py`
* Populate the content sources: `odi populate` or `odi populate --limited` if you have a large amount of data (like the global Index), and want a smaller set for local development
* `pelican content -o output -s config_default.py`
* `./develop-server` to run a server that watches and builds

[Pelican documentation for more information](http://docs.getpelican.com)


## Deployment

Steps to create a snapshot for deployment::

    odi populate
    odi deploy


## Data

Data is found in the `data` directory. This both powers the site build and is
usuable in its own right (as a Tabular Data Package).

### Preparation

Data is prepared by the python script `scripts/process.py`. This pulls data
from the Open Data Index Survey (Census), processes it in various ways and then
writes it to the `data` directory. If you want to

To run the script do:

    python scripts/process.py

### Populate

Once the data has been prepared via the `process.py` script, there is an additional step to create the source files that will be used to generate the static site. All source files for rendering pages live under `content/pages`, and in this location, everything under `datasets`, `historical` and `places` is generated by running the following command:

    odi populate

If your your census data is sizable, or if you have many languages, Pelican's build times can be considerable, and this is a pain in development. To counter this, there is a `--limited` flag for populate that will generate a subset of `places` and `datasets` (configured on the ODI object in the settings file):

    odi populate --limited


## Visualisations

The Open Data Index has a small set of tools and patterns for implementing visualisations. The first visualisation is the **Choropleth map** (described below), and this is the reference implementation for other visualisations to follow.

Visualisations have the following features:

* A permalink for the visualisation (e.g.: /vis/map/)
* An embeddable version of the visualisation (e.g.: /vis/map/embed/)
* Tools for sharing the visualisation to social networks
* Tools to filter data in the visualisation
* An interface to pass state to a visualisation via URL params

### Choropleth map

Displays Open Data Index data via a map interface.

This visualisation is embedded in the project home page, and also available via its permalink:

* /vis/map/

Or its embeddable version:

* /vis/map/embed/

#### Map state

The state of the map is configurable: internally, via the uiState object, and via query params passed on the URL to the map.

The use case for this is to enable embedding of a particular state. The uiState object has the following defaults:

    uiStateDefaults = {
        filter: {
            year: currentYear,
            dataset: 'all'
        },
        panel: {
            logo: true,
            name: true,
            tools: true,
            share: true,
            embed: true,
            help: true,
            legend: true,
        },
        map: {
            place: undefined
        },
        embed: {
            width: '100%', // min-width for the map is 430px
            height: '508px',// min-height for the map is 430px
            title: 'Open Data Index'
        },
        asQueryString: undefined
    }

These defaults can be customized on initialisation of the map via URL params (a subset of the full uiState object):

* `filter_year`
* `filter_dataset`
* `panel_logo`
* `panel_name`
* `panel_tools`
* `panel_share`
* `panel_embed`
* `panel_help`
* `panel_legend`
* `map_place`
* `embed_width`
* `embed_height`
* `embed_title`

An example query:

* `http://index.okfn.org/vis/map/embed/?filter_year=2013&filter_dataset=timetables&panel_tools=false`

### Data tables

Displays the Index data in a tabular format. **These visualisation is not currently embeddedable.**

There are two types of tables:

* Overview:
* Slice:


## API

Open Data Index exposes a (simple) API for programmatic access to data. Currently, the API is available in both JSON and CSV formats.

### API endpoints

* {format} refers to either `json` or `csv`

#### /api/entries.{format}

Returns all entries in the database.


#### /api/entries/{year}.{format}

Returns entries sliced by year.

Available years:

* 2014
* 2013


#### /api/datasets.{format}

Returns all datasets in the database.


#### /api/datasets/{category}.{format}

Returns all datasets sliced by category, where `category` is a slugified string of the dataset category.

Available categories:

* civic-information
* environment
* finance
* geodata
* transport


#### /api/places.{format}

Returns all places in the database.


#### /api/questions.{format}

Returns all questions in the database.


## Translations

There are two types of Open Data Index content to translate: strings in the codebase, and strings in the source data.

Translations are managed with the Transifex client:

http://docs.transifex.com/developer/client/


## URL Aliases

If migrating from a previous Index site to the new static site, you'll need to implement aliases from some old URLs to the new ones. For all common URLs related to the Open Data Index, this is taken care of via the `alias` meta data per page. For the content sources that are **not** auto-generated (such as about, methodology, etc.), you can simply add a list of comma-separated URL paths to `alias`.
