# Licensed to Elasticsearch B.V. under one or more contributor
# license agreements. See the NOTICE file distributed with
# this work for additional information regarding copyright
# ownership. Elasticsearch B.V. licenses this file to you under
# the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# 	http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.

import pytest

from .conftest import ServerlessProjectConfig

pytest_rally = pytest.importorskip("pytest_rally")


class TestTrackRepository:
    include_tracks = [
        "cohere_vector",
        # "dense_vector", (slow)
        "eql",
        "elastic/apm",
        "geonames",
        "geopoint",
        "geopointshape",
        "geoshape",
        "github_archive",
        "http_logs",
        # "k8s_metrics", (slow)
        # "msmarco-v2-vector", (slow for test mode)
        "nested",
        "noaa",
        "nyc_taxis",
        "percolator",
        "pmc",
        "so",
        # "so_vector", (excludes in _source)
        # "sql", (no support for test mode)
        "tsdb",
        "tsdb_k8s_queries",
    ]

    skip_challenges = {
        "nyc_taxis": ["esql"],
        "tsdb": ["downsample"],
        "tsdb_k8s_queries": ["esql"],
    }
    skip_challenges_user = {
        "geonames": ["append-no-conflicts"],
        "http_logs": ["append-no-conflicts", "runtime-fields"],
        "k8s_metrics": ["append-no-conflicts-metrics-with-fast-refresh", "fast-refresh-index-only", "fast-refresh-index-with-search"],
    }
    disable_assertions = {
        "http_logs": ["append-no-conflicts", "runtime-fields"],
        "nyc_taxis": ["update-aggs-only"],
    }

    def test_autogenerated(self, operator, rally, track, challenge, rally_options, project_config: ServerlessProjectConfig):
        track_params = {"number_of_replicas": 1}
        if track in self.include_tracks and challenge not in self.skip_challenges.get(track, []):
            if not operator and challenge in self.skip_challenges_user.get(track, []):
                pytest.skip()
            if challenge in self.disable_assertions.get(track, []):
                rally_options.update({"enable_assertions": False})
            if challenge == "runtime-fields":
                track_params.update({"runtime_fields": "true"})
            # required to avoid index out of bounds for frequent_items_all_100 operation
            # TODO verify if index refresh prior to this operation is enough to prevent an error
            if challenge == "frequent-items" and not operator:
                track_params.update({"post_ingest_sleep": "true", "post_ingest_sleep_duration": 15})
            ret = rally.race(
                track=track,
                challenge=challenge,
                track_params=track_params,
                client_options=project_config.get_client_options_file(operator),
                target_hosts=project_config.target_host,
                **rally_options,
            )
            assert ret == 0
        else:
            pytest.skip()
