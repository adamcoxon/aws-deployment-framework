# Copyright 2019 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
Module used for working with the Deployment Map (yml) file.
"""

import os
import yaml

from errors import InvalidDeploymentMapError
from logger import configure_logger
LOGGER = configure_logger(__name__)


class DeploymentMap:
    def __init__(
            self,
            parameter_store,
            pipeline_name_prefix,
            map_path=None
    ):
        self.map_path = map_path or 'deployment_map.yml'
        self.map_dir_path = map_path or 'deployment_maps'
        self.parameter_store = parameter_store
        self.map_contents = self._get_deployment_map()
        self.map_contents = self._get_deployment_apps_from_dir()
        self.pipeline_name_prefix = pipeline_name_prefix
        self.account_ou_names = {}
        self._validate_deployment_map()

    def update_deployment_parameters(self, pipeline):
        for account in pipeline.template_dictionary['targets']:
            self.account_ou_names.update(
                {item['name']: item['path'] for item in account if item['name'] != 'approval'}
            )

        # TODO Ensure this doesn't grow to reach max parameter store size (4092)
        self.parameter_store.put_parameter(
            "/deployment/{0}/account_ous".format(
                pipeline.name
            ),
            str(self.account_ou_names)
        )
        if pipeline.notification_endpoint:
            self.parameter_store.put_parameter(
                "/notification_endpoint/{0}".format(
                    pipeline.name
                ),
                str(pipeline.notification_endpoint)
            )

    def _get_deployment_map(self, file_path=None):
        if file_path is None:
            file_path = self.map_path
        try:
            LOGGER.info('Loading deployment_map file %s', file_path)
            with open(file_path, 'r') as stream:
                return yaml.load(stream, Loader=yaml.FullLoader)
        except FileNotFoundError:
            LOGGER.error('Cannot Create Deployment Pipelines as there '
                         'is no deployment_map.yml file in the repository. '
                         'If this is your first time using ADF please see read the user guide'
                         , exc_info=True)

    def _get_deployment_apps_from_dir(self):
        if os.path.isdir(self.map_dir_path):
            for file in os.listdir(self.map_dir_path):
                if file.endswith(".yml") and file != 'example-deployment_map.yml':
                    deployment_map = self._get_deployment_map('{}/{}'.format(self.map_dir_path, file))
                    if 'pipelines' not in self.map_contents:
                        self.map_contents['pipelines'] = []
                    if 'pipelines' in deployment_map:
                        self.map_contents['pipelines'].extend(deployment_map['pipelines'])
        return self.map_contents

    def _validate_deployment_map(self):
        """
        Validates the deployment map contains valid configuration
        """
        try:
            for pipeline in self.map_contents["pipelines"]:
                for target in pipeline.get("targets", []):
                    if isinstance(target, dict):
                        # Prescriptive information on the error should be raised
                        assert target["path"]
        except KeyError:
            raise InvalidDeploymentMapError(
                "Deployment Map target or regions specification is invalid"
            )
