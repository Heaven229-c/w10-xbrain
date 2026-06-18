# External Secrets Operator Config

This folder is managed by the `eso-config` ArgoCD Application.

```text
eso/
├── secret-store.yaml
└── external-secret.yaml
```

Runtime AWS credentials are intentionally not stored in Git. Create them in the cluster with `kubectl create secret generic aws-credentials -n demo ...` before syncing `eso-config`.

The app consumes the generated Kubernetes Secret `db-secret` through a mounted volume, not an environment variable. Mounted Secret volumes can refresh without restarting the pod; environment variables cannot.
