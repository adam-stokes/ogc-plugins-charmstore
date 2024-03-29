import os
from glob import glob
from pathlib import Path
from pprint import pformat
import click
import sh
import yaml
import time
import uuid
from ogc.state import app
from ogc.spec import SpecProcessException


class CharmEnv:
    """ Charm environment
    """

    def __init__(self):
        try:
            self.build_dir = Path(os.environ.get("CHARM_BUILD_DIR"))
            self.layers_dir = Path(os.environ.get("CHARM_LAYERS_DIR"))
            self.interfaces_dir = Path(os.environ.get("CHARM_INTERFACES_DIR"))
            self.tmp_dir = Path(os.environ.get("WORKSPACE"))
        except TypeError:
            raise SpecProcessException(
                "CHARM_BUILD_DIR, CHARM_LAYERS_DIR, CHARM_INTERFACES_DIR, WORKSPACE: "
                "Unable to find some or all of these charm build environment variables."
            )


charm_sh = sh.charm.bake(_env=app.env.copy())


def push(repo_path, out_path, charm_entity, is_bundle=False):
    """ Pushes a built charm to Charmstore
    """

    app.log.debug(f"vcs: {repo_path} build-path: {out_path} {charm_entity}")
    git_commit = sh.git("rev-parse", "HEAD", _cwd=repo_path)
    git_commit = git_commit.stdout.decode().strip()
    app.log.debug(f"grabbing git revision {git_commit}")

    resource_args = []
    if not is_bundle:
        # Build a list of `oci-image` resources that have `upstream-source` defined,
        # which is added for this logic to work.
        resources = yaml.safe_load(
            Path(out_path).joinpath("metadata.yaml").read_text()
        ).get("resources", {})
        images = {
            name: details["upstream-source"]
            for name, details in resources.items()
            if details["type"] == "oci-image" and details.get("upstream-source")
        }
        app.log.debug(f"Found {len(images)} oci-image resources:\n{pformat(images)}\n")
        for image in images.values():
            app.log.debug(f"Pulling {image}...")
            sh.docker.pull(image)

        # Convert the image names and tags to `--resource foo=bar` format
        # for passing to `charm push`.
        resource_args = [
            arg
            for name, image in images.items()
            for arg in ("--resource", f"{name}={image}")
        ]

    out = charm_sh.push(out_path, charm_entity, *resource_args)
    app.log.debug(f"Charm push returned: {out}")
    # Output includes lots of ansi escape sequences from the docker push,
    # and we only care about the first line, which contains the url as yaml.
    out = yaml.safe_load(out.stdout.decode().strip().splitlines()[0])
    app.log.debug(f"Setting {out['url']} metadata: {git_commit}")
    charm_sh.set(out["url"], "commit={}".format(git_commit))


def pull_layers(layer_index, layer_list, layer_branch, retries=15, timeout=60):
    charm_env = CharmEnv()
    layer_list = yaml.safe_load(Path(layer_list).read_text(encoding="utf8"))
    num_runs = 0
    for layer_map in layer_list:
        layer_name = list(layer_map.keys())[0]
        if layer_name == "layer:index":
            continue

        app.log.debug(layer_name)

        def download():
            for line in charm_sh(
                "pull-source",
                "-v",
                "-i",
                layer_index,
                layer_name,
                _iter=True,
                _bg_exc=False,
            ):
                app.log.debug(f" -- {line.strip()}")

        try:
            num_runs += 1
            download()
        except TypeError as e:
            raise SpecProcessException(f"Could not download charm: {e}")
        except sh.ErrorReturnCode_1 as e:
            app.log.debug(f"Problem: {e}, retrying [{num_runs}/{retries}]")
            if num_runs == retries:
                raise SpecProcessException(
                    f"Could not download charm after {retries} retries."
                )
            time.sleep(timeout)
            download()
        ltype, name = layer_name.split(":")
        if ltype == "layer":
            sh.git.checkout("-f", layer_branch, _cwd=str(charm_env.layers_dir / name))
        elif ltype == "interface":
            sh.git.checkout(
                "-f", layer_branch, _cwd=str(charm_env.interfaces_dir / name)
            )
        else:
            raise SpecProcessException(f"Unknown layer/interface: {layer_name}")


def promote(charm_list, filter_by_tag, from_channel="unpublished", to_channel="edge"):
    charm_list = yaml.safe_load(Path(charm_list).read_text(encoding="utf8"))

    for charm_map in charm_list:
        for charm_name, charm_opts in charm_map.items():
            if not any(match in filter_by_tag for match in charm_opts["tags"]):
                continue

            charm_entity = f"cs:~{charm_opts['namespace']}/{charm_name}"
            app.log.debug(
                f"Promoting :: {charm_entity:^35} :: from:{from_channel} to: {to_channel}"
            )
            charm_id = charm_sh.show(charm_entity, "--channel", from_channel, "id")
            charm_id = yaml.safe_load(charm_id.stdout.decode())
            resources_args = []
            try:
                resources = charm_sh(
                    "list-resources",
                    charm_id["id"]["Id"],
                    channel=from_channel,
                    format="yaml",
                )
                resources = yaml.safe_load(resources.stdout.decode())
                if resources:
                    resources_args = [
                        (
                            "--resource",
                            "{}-{}".format(resource["name"], resource["revision"]),
                        )
                        for resource in resources
                    ]
            except sh.ErrorReturnCode_1:
                app.log.debug("No resources for {}".format(charm_id))
            charm_sh.release(
                charm_id["id"]["Id"], "--channel", to_channel, *resources_args
            )


def resource(charm_entity, channel, builder, out_path, resource_spec):
    out_path = Path(out_path)
    resource_spec = yaml.safe_load(Path(resource_spec).read_text())
    resource_spec_fragment = resource_spec.get(charm_entity, None)
    app.log.debug(resource_spec_fragment)
    if not resource_spec_fragment:
        raise SpecProcessException("Unable to determine resource spec for entity")

    os.makedirs(str(out_path), exist_ok=True)
    charm_id = charm_sh.show(charm_entity, "--channel", channel, "id")
    charm_id = yaml.safe_load(charm_id.stdout.decode())
    try:
        resources = charm_sh(
            "list-resources", charm_id["id"]["Id"], channel=channel, format="yaml"
        )
    except sh.ErrorReturnCode_1:
        app.log.debug("No resources found for {}".format(charm_id))
        return
    resources = yaml.safe_load(resources.stdout.decode())
    builder_sh = Path(builder).absolute()
    app.log.debug(builder_sh)
    for line in sh.bash(str(builder_sh), _cwd=out_path, _iter=True, _bg_exc=False):
        app.log.info(line.strip())
    for line in glob("{}/*".format(out_path)):
        resource_path = Path(line)
        resource_fn = resource_path.parts[-1]
        resource_key = resource_spec_fragment.get(resource_fn, None)
        if resource_key:
            is_attached = False
            is_attached_count = 0
            while not is_attached:
                try:
                    out = charm_sh.attach(
                        charm_entity,
                        "--channel",
                        channel,
                        f"{resource_key}={resource_path}",
                        _err_to_out=True,
                        _bg_exc=False
                    )
                    is_attached = True
                except sh.ErrorReturnCode_1 as e:
                    app.log.debug(f"Problem attaching resources, retrying: {e}")
                    is_attached_count += 1
                    if is_attached_count > 10:
                        raise SpecProcessException(
                            "Could not attach resource and max retry count reached."
                        )
            app.log.debug(out)


def build(
    charm_list,
    layer_list,
    layer_index,
    charm_branch,
    layer_branch,
    resource_spec,
    filter_by_tag,
    to_channel,
    dry_run,
):
    charm_env = CharmEnv()
    _charm_list = yaml.safe_load(Path(charm_list).read_text(encoding="utf8"))

    pull_layers(layer_index, layer_list, layer_branch)
    for charm_map in _charm_list:
        for charm_name, charm_opts in charm_map.items():
            downstream = f"https://github.com/{charm_opts['downstream']}"
            if not any(match in filter_by_tag for match in charm_opts["tags"]):
                continue

            if dry_run:
                app.log.debug(
                    f"{charm_name:^25} :: vcs-branch: {charm_branch} to-channel: {to_channel} tags: {','.join(charm_opts['tags'])}"
                )
                continue
            charm_entity = f"cs:~{charm_opts['namespace']}/{charm_name}"
            src_path = charm_name
            os.makedirs(src_path)

            dst_path = str(charm_env.build_dir / charm_name)
            for line in sh.git.clone(
                "--branch",
                charm_branch,
                downstream,
                src_path,
                _iter=True,
                _bg_exc=False,
            ):
                app.log.debug(line)

            for line in charm_sh.build(
                r=True, force=True, _cwd=src_path, _iter=True, _bg_exc=False
            ):
                app.log.info(line.strip())
            charm_sh.proof(_cwd=dst_path)
            if not dry_run:
                push(src_path, dst_path, charm_entity)
                resource_builder = charm_opts.get("resource_build_sh", None)
                if resource_builder:
                    resource(
                        charm_entity,
                        "unpublished",
                        f"{src_path}/{resource_builder}",
                        f"{dst_path}/tmp",
                        resource_spec,
                    )
    if not dry_run:
        promote(charm_list, filter_by_tag, to_channel=to_channel)


def build_bundles(bundle_list, filter_by_tag, bundle_repo, to_channel, dry_run):
    charm_env = CharmEnv()
    _bundle_list = yaml.safe_load(Path(bundle_list).read_text(encoding="utf8"))
    app.log.debug("bundle builds")
    bundle_repo_dir = charm_env.tmp_dir / "bundles-kubernetes"
    bundle_build_dir = charm_env.tmp_dir / "tmp-bundles"
    sh.rm("-rf", bundle_repo_dir)
    sh.rm("-rf", bundle_build_dir)
    os.makedirs(str(bundle_repo_dir), exist_ok=True)
    os.makedirs(str(bundle_build_dir), exist_ok=True)
    for line in sh.git.clone(
        bundle_repo, str(bundle_repo_dir), _iter=True, _bg_exc=False
    ):
        app.log.debug(line)
    for bundle_map in _bundle_list:
        for bundle_name, bundle_opts in bundle_map.items():
            if not any(match in filter_by_tag for match in bundle_opts["tags"]):
                app.log.debug(f"Skipping {bundle_name}")
                continue
            app.log.debug(f"Processing {bundle_name}")
            cmd = [
                str(bundle_repo_dir / "bundle"),
                "-o",
                str(bundle_build_dir / bundle_name),
                "-c",
                to_channel,
                bundle_opts["fragments"],
            ]
            app.log.debug(f"Running {' '.join(cmd)}")
            import subprocess

            subprocess.call(" ".join(cmd), shell=True)
            bundle_entity = f"cs:~{bundle_opts['namespace']}/{bundle_name}"
            app.log.debug(f"Check {bundle_entity}")
            if not dry_run:
                push(
                    str(bundle_repo_dir),
                    str(bundle_build_dir / bundle_name),
                    bundle_entity,
                    is_bundle=True,
                )
    if not dry_run:
        promote(bundle_list, filter_by_tag, to_channel=to_channel)
