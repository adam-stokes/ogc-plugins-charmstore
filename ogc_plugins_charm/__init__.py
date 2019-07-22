"""
---
targets: ['docs/plugins/charm.md']
---
"""

import os
import click
import sys
import sh
import uuid
import yaml
import textwrap
from tempfile import gettempdir
from melddict import MeldDict
from ogc.state import app
from ogc.spec import SpecPlugin, SpecProcessException
from . import api


class Charm(SpecPlugin):

    friendly_name = "OGC Charm Plugin"
    description = "Charm plugin for building Juju charms and bundles"

    options = [
        {
            "key": "charms.charm_branch",
            "required": True,
            "description": "GIT branch of the charm to build from",
        },
        {
            "key": "charms.to_channel",
            "required": True,
            "description": "Charmstore channel to publish built charm to",
        },
        {
            "key": "charms.filter_by_tag",
            "required": False,
            "description": "Build tag to filter by, (ie. k8s or general)",
        },
        {
            "key": "charms.list",
            "required": True,
            "description": "Path to a yaml list of charms to build",
        },
        {
            "key": "charms.resource_spec",
            "required": False,
            "description": "Path to yaml list resource specifications when building charm resources",
        },
        {
            "key": "charms.layer_index",
            "required": False,
            "description": "Path to public layer index",
        },
        {
            "key": "charms.layer_list",
            "required": False,
            "description": "Path to yaml list of layers to cache prior to a charm build",
        },
        {
            "key": "charms.layer_branch",
            "required": False,
            "description": "GIT Branch to build layers from",
        },
        {
            "key": "bundles.list",
            "required": False,
            "description": "Path to yaml list of bundles to build",
        },
        {"key": "bundles.repo", "required": False, "description": "GIT Bundle repo"},
        {
            "key": "bundles.filter_by_tag",
            "required": False,
            "description": "Build tag to filter by, (ie. k8s or general)",
        },
    ]

    def conflicts(self):
        if self.get_plugin_option("bundles") and not self.get_plugin_option(
            "bundles.list"
        ):
            raise SpecProcessException(
                "Must have a bundles.list defined to use with the bundle builder."
            )

    def _g(self, key):
        """ get plugin option
        """
        return self.get_plugin_option(key)

    def process(self):
        app.log.debug("Processing charm")
        build_charms = self._g("charms")
        build_bundles = self._g("bundles")

        # Charm Build options
        charm_list = self._g("charms.list")
        layer_list = self._g("charms.layer_list")
        layer_index = self._g("charms.layer_index")
        charm_branch = self._g("charms.charm_branch")
        layer_branch = self._g("charms.layer_branch")
        resource_spec = self._g("charms.resource_spec")
        filter_by_tag = self._g("charms.filter_by_tag")
        to_channel = self._g("charms.to_channel")

        # Bundle Build options
        bundle_list = self._g("bundles.list")
        bundle_repo = self._g("bundles.repo")

        if build_charms:
            app.log.info("Building charms")
            api.build(
                charm_list,
                layer_list,
                layer_index,
                charm_branch,
                layer_branch,
                resource_spec,
                filter_by_tag,
                to_channel,
                dry_run=False,
            )

        if build_bundles:
            api.build_bundles(
                bundle_list, filter_by_tag, bundle_repo, to_channel, dry_run=False
            )

    @classmethod
    def doc_example(cls):
        return textwrap.dedent(
            """
        ## Example

        ```toml
        [Charm]
        name = "Building Charms"
        description = \"\"\"
        Build the charms that make up a Juju bundle
        \"\"\"

        [Charm.charms]
        charm_branch = "master"
        filter_by_tag = "k8s"
        layer_branch = "master"
        layer_index = "https://charmed-kubernetes.github.io/layer-index/"
        layer_list = "builders/charms/charm-layer-list.yaml"
        list = "builders/charms/charm-support-matrix.yaml"
        resource_spec = "builders/charms/resource-spec.yaml"
        to_channel = "edge"

        [Charm.bundles]
        filter_by_tag = "k8s"
        bundle_list = "builders/charms/charm-bundles-list.yaml"
        deps = ["snap:charm/latest/edge:classic"]
        ```
        """
        )


__class_plugin_obj__ = Charm
