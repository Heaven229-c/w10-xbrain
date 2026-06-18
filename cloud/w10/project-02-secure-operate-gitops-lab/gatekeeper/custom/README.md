# Lab 03 - Custom Gatekeeper Policies

This folder contains custom ConstraintTemplates written for Lab 03.

```text
custom/
├── templates/      # Custom ConstraintTemplate + Rego
├── constraints/    # Custom Constraint objects
└── tests/          # Reject/pass test manifests
```

The policies are synced by ArgoCD through:

```text
argocd/apps/gatekeeper-custom-templates.yaml
argocd/apps/gatekeeper-custom-constraints.yaml
```

Implemented custom policies:

1. Reject Deployment when `spec.replicas > 5`.
2. Require workload label `owner`.
3. Allow images only from `ghcr.io/heaven229-c/`.
