"""
Extract index artifacts from elasticsearch
"""

import argparse
import gzip
import json
import os
import shutil
import time

import yaml
from elasticsearch import Elasticsearch, NotFoundError
from elasticsearch.helpers import parallel_bulk, scan


def check_index(es_client, index_name):
    """
    Check if an index exists.

    Parameters:
    - ec_client (obj): Connection object to an Elasticsearch instance.
    - index_name (str): Name of the index to find.

    Returns:
    - index_exists (obj): Response from the check index call.
    """
    index_exists = es_client.indices.exists(index=index_name)
    print(f"Does index {index_name} exist: {index_exists}")

    return index_exists


def get_ds(es_client, data_stream_name, folder=""):
    """
    Get details for a data stream.

    Parameters:
    - es_client (obj): Elasticsearch connection.
    - data_stream_name (str): Name of the data stream.
    - folder (str): Directory where the data stream details should be written.

    Returns:
    - resp.body (obj): Body of the response from the get data stream call.
    """
    resp = es_client.indices.get_data_stream(name=data_stream_name, include_defaults=True)
    with open(folder + data_stream_name + ".ds.json", "w", encoding="utf-8") as json_file:
        json.dump(resp.body, json_file, indent=4)

    return resp.body


def get_ilm(es_client, ilm_name, folder=""):
    """
    Get details for an index lifecycle management policy.

    Parameters:
    - es_client (obj): Elasticsearch connection.
    - ilm_name (str): Name of the index lifecycle management policy.
    - folder (str): Directory where the ilm details should be written.

    Returns:
    - resp[ilm_name] (obj): Body of the response from the get lifecycle call.
    """
    resp = es_client.ilm.get_lifecycle(name=ilm_name)
    resp[ilm_name].pop("version", None)
    resp[ilm_name].pop("modified_date", None)
    resp[ilm_name].pop("in_use_by", None)

    ilm_folder = folder + "ilm/"

    if not os.path.exists(ilm_folder):
        os.makedirs(ilm_folder)

    with open(ilm_folder + ilm_name + ".json", "w", encoding="utf-8") as json_file:
        json.dump(resp[ilm_name], json_file, indent=2)

    return resp[ilm_name]


def get_pipelines(es_client, template, folder=""):
    """
    Get pipelines for an index template.

    Parameters:
    - es_client (obj): Elasticsearch connection.
    - template (dict): template to extract used pipelines.
    - folder (str): Directory where the pipeline details should be written.
    """
    pipelines_folder = folder + "pipelines/"
    if not os.path.exists(pipelines_folder):
        os.makedirs(pipelines_folder)

    if "settings" in template and "index" in template["settings"]:
        for pipeline_key in template["settings"]["index"].keys() & {"default_pipeline", "final_pipeline"}:
            pipeline_name = template["settings"]["index"][pipeline_key]
            pipeline_resp = es_client.ingest.get_pipeline(id=pipeline_name)
            if "deprecated" in pipeline_resp[pipeline_name]:
                del pipeline_resp[pipeline_name]["deprecated"]
            with open(pipelines_folder + pipeline_name + ".json", "w", encoding="utf-8") as pipeline_json_file:
                json.dump(pipeline_resp[pipeline_name], pipeline_json_file, indent=2)


def get_templates(es_client, template_name, folder=""):
    """
    Get artifacts for an index template.  These are the composable template, the component templates and the pipelines

    Parameters:
    - es_client (obj): Elasticsearch connection.
    - template_name (str): Name of the index template.
    - folder (str): Directory where the template details should be written.

    Returns:
    - resp['index_templates'][0]['index_template'] (obj): Index template details from the API call.
    """
    templates_folder = folder + "templates/"
    if not os.path.exists(templates_folder):
        os.makedirs(templates_folder)

    composable_folder = templates_folder + "composable/"
    if not os.path.exists(composable_folder):
        os.makedirs(composable_folder)

    component_folder = templates_folder + "component/"
    if not os.path.exists(component_folder):
        os.makedirs(component_folder)

    resp = es_client.indices.get_index_template(name=template_name)
    resp["index_templates"][0]["index_template"]["data_stream"].pop("failure_store", None)

    get_pipelines(es_client, resp["index_templates"][0]["index_template"]["template"], folder)

    for component_template in resp["index_templates"][0]["index_template"]["composed_of"]:
        try:
            comp_resp = es_client.cluster.get_component_template(name=component_template)
            with open(component_folder + component_template + ".json", "w", encoding="utf-8") as component_json_file:
                json.dump(comp_resp["component_templates"][0], component_json_file, indent=2)
            get_pipelines(es_client, comp_resp["component_templates"][0]["component_template"]["template"], folder)
        except NotFoundError:
            if component_template in resp["index_templates"][0]["index_template"]["ignore_missing_component_templates"]:
                pass

    # Add in a custom component templates to composable templates
    resp["index_templates"][0]["index_template"]["composed_of"].append("track-shared-logsdb-mode")
    with open(composable_folder + template_name + ".json", "w", encoding="utf-8") as composable_json_file:
        json.dump(resp["index_templates"][0], composable_json_file, indent=2)

    return resp["index_templates"][0]["index_template"]


def get_index(es_client, index_name, folder=""):
    """
    Get the details on an index and save artifacts: templates, ilm and pipelines.

    Parameters:
    - es_client (obj): Elasticsearch connection.
    - template_name (str): Name of the index.
    - folder (str): Directory where the index details should be written.

    Returns:
    - index_details (dict): Dictionary containing the details of the index.
    """
    index_details = {}
    index = None
    index_list = []
    has_ilm = False
    has_datastream = False
    # check if index exists
    index_exists = check_index(es_client, index_name)
    # get index
    if index_exists:
        # we have an index so process it
        resp = es_client.indices.get(index=index_name, expand_wildcards="all", flat_settings=True)
        count = 0
        for key in resp.keys():
            index = key
            index_list.append(key)
            if "index.lifecycle.name" in resp[index]["settings"]:
                has_ilm = True
            if "data_stream" in resp[index]:
                has_datastream = True
            if count == 0:
                with open(folder + index_name + ".json", "w", encoding="utf-8") as json_file:
                    # remove the keys that are not allowed at creation time
                    resp[key]["settings"].pop("index.creation_date", None)
                    resp[key]["settings"].pop("index.uuid", None)
                    resp[key]["settings"].pop("index.version.created", None)
                    resp[key]["settings"].pop("index.provided_name", None)
                    index_details["configuration"] = resp[key]
                    json.dump(resp[key], json_file, indent=4)
                count += 1
            else:
                with open(folder + index_name + ".json", "a", encoding="utf-8") as json_file:
                    json.dump(resp[key], json_file, indent=4)
        index_details["index_list"] = index_list
    if has_ilm:
        ilm = get_ilm(es_client, resp[index]["settings"]["index.lifecycle.name"], folder)
        index_details["ilm"] = ilm
    if has_datastream:
        ds = get_ds(es_client, resp[index]["data_stream"], folder)
        index_details["data_stream"] = ds
        template = get_templates(es_client, ds["data_streams"][0]["template"], folder)
        index_details["template"] = template

    return index_details


def generate_documents(es_client, index_name, query, preserve_order=False):
    """
    Return generator that reads documents from an elasticsearch index.

    Parameters:
    - es_client (obj): Elasticsearch connection.
    - index_name (str): Name of the index to read.
    - query (str): JSON string to limit the index read.
    - preserve_order (bool): Set to True to maintain a standard order in the
        returned documents.  This may be an expensive operation and negate
        the performance benefits of using scan.

    Returns:
    - Generator object with each iteration being a document from the index.
    """
    for doc in scan(es_client, index=index_name, query=query, preserve_order=preserve_order, size=2000):
        yield doc


def extract_data(es_client, index_name, doc_limit=None, query=None, folder=""):
    """
    Read documents from the Elasticsearch index.

    Parameters:
    - es_client (obj): Elasticsearch connection.
    - index_name (str): Name of the index to read.
    - doc_limit (int): Maximum number of documents to read.
    - query (str): JSON string to limit the index read.
    - folder (str): Directory where the index data should be written.

    Returns:
    - Nothing.
    """
    export_count = 0
    start_time = time.time()
    with gzip.open(folder + index_name + ".data.ndjson.gz", "wt") as json_file:
        for document in generate_documents(es_client, index_name, query):
            export_count += 1
            json_line = json.dumps(document["_source"]) + "\n"
            json_file.write(json_line)
            if (export_count % 10000) == 0:
                interim_time = time.time()
                elapsed_time = interim_time - start_time
                rate = (export_count / elapsed_time) * 60
                hours = int(elapsed_time // 3600)
                minutes = int((elapsed_time % 3600) // 60)
                seconds = int(elapsed_time % 60)
                print(f"Exported {export_count:,} " f"(running time {hours}:{minutes:02d}:{seconds:02d}) " f"({rate:,.0f} docs/min)")
            if doc_limit and export_count >= doc_limit:
                break


def main():
    parser = argparse.ArgumentParser(description="Extract artifacts from target data stream.")

    parser.add_argument("-c", "--config", type=str, default="./configuration.yml", help="Configuration file")
    parser.add_argument("-d", "--extract_docs", action="store_true", help="Option to extract documents from indices")
    parser.add_argument("-l", "--limit", type=int, help="Limit the number of documents extracted")
    parser.add_argument("-q", "--query", type=str, help="Query to filter documents")
    args = parser.parse_args()

    # Access the values of the parsed arguments
    configuration_file = args.config
    doc_limit = args.limit
    query_file = args.query

    print(f"Configuration File: {configuration_file}")
    print(f"Document Limit:     {doc_limit}")
    print(f"Query File:         {query_file}")

    # Load variables from the YAML configuration file
    stream = open(configuration_file, "r", encoding="utf-8")
    config = yaml.load(stream, Loader=yaml.CLoader)
    indices = config["indices"]

    print(f"Indices:            {indices}")

    # set extract storage location
    if "data_folder" in config:
        artifact_folder = config["data_folder"]
        if not artifact_folder.endswith("/"):
            artifact_folder += "/"
    else:
        print("No folder specified for storing extracts.  " "The data will be stored in the `./artifacts`.")
        artifact_folder = "./artifacts/"
    if os.path.exists(artifact_folder):
        os.rmdir(artifact_folder)
    shutil.copytree("track_artifacts", artifact_folder)

    def get_es_kwargs(config):
        es_kwargs = {"http_compress": True, "request_timeout": 300, "hosts": config["es_url"]}
        if "api_key" in config and "encoded" in config["api_key"]:
            es_kwargs["api_key"] = config["api_key"]["encoded"]
        if "basic_auth" in config and "username" in config["basic_auth"] and "password" in config["basic_auth"]:
            es_kwargs["basic_auth"] = [
                config["basic_auth"]["username"],
                config["basic_auth"]["password"],
            ]
        if "verify_certs" in config:
            es_kwargs["verify_certs"] = config["verify_certs"]
        if "cert_fingerprint" in config:
            es_kwargs["ssl_assert_fingerprint"] = config["cert_fingerprint"]
        if "ca_certs" in config:
            es_kwargs["ca_certs"] = config["ca_certs"]
        return es_kwargs

    source_es_kwargs = get_es_kwargs(config["source"])

    if query_file:
        # load the query
        with open(query_file, "r", encoding="utf-8") as file:
            query = json.load(file)
    else:
        query = None

    # connect to Elasticsearch source
    kwargs = source_es_kwargs
    source_es = Elasticsearch(**kwargs)

    component_templates = set()
    for index_name in indices:
        print(f"Extract artifacts from: {index_name}")
        source_index_details = get_index(source_es, index_name, artifact_folder)
        for component_template in source_index_details["template"]["composed_of"]:
            component_templates.add(component_template)
        if args.extract_docs:
            if source_index_details["index_list"]:
                for index in source_index_details["index_list"]:
                    print(f"Index to extract data from: {index}")
                    extract_data(source_es, index, doc_limit, query, artifact_folder)
            else:
                exit(f"No index named {index_name} found in source system.")
        print(f"Completed extracting from: {index_name}")

    print(f"Generating track.snippet.json snippet for component templates")
    track_component_templates = {"component-templates": []}
    for component_template in component_templates:
        if os.path.isfile(os.path.join(os.getcwd(), f"{artifact_folder}templates/component/{component_template}.json")):
            track_component_templates["component-templates"].append(
                {
                    "name": component_template,
                    "template": f"./templates/component/{component_template}.json",
                    "template-path": "component_template"
                }
            )
    track_component_templates["component-templates"].sort(key=lambda x: x["name"])
    with open(artifact_folder + "track.snippet.json", "w", encoding="utf-8") as track_json_file:
        json.dump(track_component_templates, track_json_file, indent=2)

    source_es.close()


if __name__ == "__main__":
    import urllib3

    urllib3.disable_warnings()
    main()
