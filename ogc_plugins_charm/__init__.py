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

__version__ = "1.0.0"
__author__ = "Adam Stokes"
__author_email__ = "adam.stokes@gmail.com"
__maintainer__ = "Adam Stokes"
__maintainer_email__ = "adam.stokes@gmail.com"
__plugin_name__ = "ogc-plugins-charmstore"
__description__ = "ogc-plugins-charmstore, a ogc plugin for interacting with juju charmstore"
__git_repo__ = "https://github.com/battlemidget/ogc-plugin-charmstore"
__example__ = """

## Example 1

```yaml
plan:
  - charmstore:
      charms:
        description: |
          Builds the charms that make up Kubernetes
        env-requires:
          - CHARM_BUILD_DIR
          - CHARM_LAYERS_DIR
          - CHARM_INTERFACES_DIR
          - CHARM_CACHE_DIR
          - CHARM_BRANCH
          - FILTER_BY_TAG
          - LAYER_BRANCH
          - LAYER_INDEX
          - LAYER_LIST
          - CHARM_LIST
          - RESOURCE_SPEC
          - BUNDLE_LIST
          - BUNDLE_REPO
          - TO_CHANNEL
          - TMPDIR
          - WORKSPACE
        script: |
          #!/bin/bash
          set -eux
          python3 charms.py build --charm-list "$CHARM_LIST" \
            --charm-branch "$CHARM_BRANCH" \
            --to-channel "$TO_CHANNEL" \
            --resource-spec "$RESOURCE_SPEC" \
            --filter-by-tag "$FILTER_BY_TAG" \
            --layer-index  "$LAYER_INDEX" \
            --layer-list "$LAYER_LIST" \
            --layer-branch "$LAYER_BRANCH"
      tags = [build-charms]
  - charmstore:
      bundles:
        description: |
          Buildes the bundles that make up Kubernetes
        env-requires:
          - FILTER_BY_TAG
          - BUNDLE_LIST
          - BUNDLE_REPO
          - TO_CHANNEL
          - TMPDIR
          - WORKSPACE
        script: |
          #!/bin/bash
          set -eux
          python3 charms.py build-bundles \
            --to-channel "$TO_CHANNEL" \
            --bundle-list "$BUNDLE_LIST" \
            --filter-by-tag "$FILTER_BY_TAG"
      tags: [build-bundles]
```
"""

class CharmStore(SpecPlugin):

    friendly_name = "OGC CharmStore Plugin"

    options = [
        {
            "key": "charms.charm-branch",
            "required": True,
            "description": "GIT branch of the charm to build from",
        },
        {
            "key": "charms.to-channel",
            "required": True,
            "description": "Charmstore channel to publish built charm to",
        },
        {
            "key": "charms.filter-by-tag",
            "required": False,
            "description": "Build tag to filter by, (ie. k8s or general)",
        },
        {
            "key": "charms.list",
            "required": True,
            "description": "Path to a yaml list of charms to build",
        },
        {
            "key": "charms.resource-spec",
            "required": False,
            "description": "Path to yaml list resource specifications when building charm resources",
        },
        {
            "key": "charms.layer-index",
            "required": False,
            "description": "Path to public layer index",
        },
        {
            "key": "charms.layer-list",
            "required": False,
            "description": "Path to yaml list of layers to cache prior to a charm build",
        },
        {
            "key": "charms.layer-branch",
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
            "key": "bundles.filter-by-tag",
            "required": False,
            "description": "Build tag to filter by, (ie. k8s or general)",
        },
    ]

    def __str__(self):
        return __description__

    def conflicts(self):
        if self.get_plugin_option("bundles") and not self.get_plugin_option(
            "bundles.list"
        ):
            raise SpecProcessException(
                "Must have a bundles.list defined to use with the bundle builder."
            )

    def process(self):
        app.log.debug("Processing charm")
        build_charms = self.opt("charms")
        build_bundles = self.opt("bundles")

        # Charm Build options
        charm_list = self.opt("charms.list")
        layer_list = self.opt("charms.layer-list")
        layer_index = self.opt("charms.layer-index")
        charm_branch = self.opt("charms.charm-branch")
        layer_branch = self.opt("charms.layer-branch")
        resource_spec = self.opt("charms.resource-spec")
        filter_by_tag = self.opt("charms.filter-by-tag")
        to_channel = self.opt("charms.to-channel")

        # Bundle Build options
        bundle_list = self.opt("bundles.list")
        bundle_repo = self.opt("bundles.repo")

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


__class_plugin_obj__ = CharmStore
