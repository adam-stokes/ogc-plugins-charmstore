# ogc-plugins-charm

Charm build plugin

# Usage

In a ogc spec, place the following:

```toml
[Charm]

[Charm.charms]
charm_support_matrix = "charm-support-matrix.yaml"
resource_spec = "resource-spec.yaml"
layer_list = "charm-layer-list.yaml"

[Charm.bundles]
bundle_list = "charm-bundles-list.yaml"
```

# see `ogc spec-doc Charm` for more information.
