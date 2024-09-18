## Setup

```bash
cd ./extract_artifacts
python -m venv .venv
. ./venv/bin/activate
pip install -r requirements.txt
```

## Configuration
Generate `configuration.yml`

```
source:
  es_url: "https://source.es.url/"
  basic_auth:
    username: "elastic"
    password: "changeme"
  verify_certs: False
  ca_certs: "./http_ca.crt"
data_folder: "./artifacts"
indices:
  - logs-endpoint.events.api-default
  - logs-endpoint.events.file-default
  - logs-endpoint.events.library-default
  - logs-endpoint.events.network-default
  - logs-endpoint.events.process-default
  - logs-endpoint.events.registry-default
  - logs-endpoint.events.security-default
```

- `data_folder`: folder to store artifacts 
- `indices`: datastreams/indices to extract

## Data Filtering
The script can be provided a JSON file with a query to filter the data extracted.  This is useful when you have a large source index but only need a few documents.  There is a sample query file, `query.sample.json`, provided as a guide.

## Maximum Document count
The script supports a parameter to limit the number of documents extracted, `-l` or `--limit`.  Use this to specifiy the maximum number of documents to extract from an index.  Currently the limit is applied to all matching indexes individiually rather than as an overall total.  If you specify a data stream which has 10 indexes and a limit of 100 documents, it will extract 100 documents from each of the 10 indexes extracting a total of 1,000 documents.  Another opportunity for enhancement.

## Executing the Script
````
usage: extract_artifacts.py [-h] [-c CONFIG] [-d] [-l LIMIT] [-q QUERY]

Extract artifacts from target data stream.

options:
  -h, --help            show this help message and exit
  -c CONFIG, --config CONFIG
                        Configuration file
  -d, --extract_docs    Option to extract documents from indices
  -l LIMIT, --limit LIMIT
                        Limit the number of documents extracted
  -q QUERY, --query QUERY
                        Query to filter documents
````
ex.:

```bash
python extract_artifacts.py -c configuration.yml
```

- `-d` to extract documents from indices 
- `-l` to limit documents extracted by count
- `-q` to limit documents extracted by query.
```bash
python extract_artifacts.py -c configuration.yml -d -q query.json -l 10000
```

## Updating the Track
`ilm`, `pipelines` and `templates` artifacts should replace corresponding artifacts in the `security` track.

Artifact references should be updated in the security track `./security/track.json`.  Component template references are generated in `track.snippet.json`

The compressed document artifact ex.: `.ds-logs-endpoint.events.process-default-2024.04.17-000001.data.ndjson.gz` should be renamed appropriately and move to cloud storage https://console.cloud.google.com/storage/browser/rally-internal-tracks/data/security.

The integration in the security track `./security/track.json` should be updated to point to the updated corpus.