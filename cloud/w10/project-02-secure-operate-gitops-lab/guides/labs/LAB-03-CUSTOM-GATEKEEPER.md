# Lab 03 - Custom ConstraintTemplate bằng Rego

## 1. Mục tiêu lab

Lab này chứng minh em có thể tự viết policy admission bằng Rego, không chỉ dùng policy có sẵn.

Yêu cầu lab:

| # | Custom policy | Kết quả mong đợi |
|---|---|---|
| 1 | Reject `Deployment` nếu `replicas > 5` | Deployment 6 replicas bị reject, 5 replicas pass |
| 2 | Bắt buộc workload có label `owner` | Workload thiếu `owner` bị reject, có `owner` pass |
| 3 | Chỉ cho image từ registry của mình | Image ngoài `ghcr.io/heaven229-c/` bị reject, image đúng registry pass |

Lab này triển khai bằng GitOps:

```text
Code policy trong Git
        ↓
Commit + push lên GitHub
        ↓
ArgoCD sync
        ↓
Gatekeeper enforce tại Kubernetes API server
        ↓
Test manifest vi phạm reject, manifest hợp lệ pass
```

## 2. Kiến trúc file Lab 03

Lab 03 dùng riêng folder:

```text
gatekeeper/custom/
├── README.md
├── templates/
│   ├── deployment-replica-limit.yaml
│   ├── required-owner-label.yaml
│   └── allowed-image-registry.yaml
├── constraints/
│   ├── deployment-replica-limit.yaml
│   ├── required-owner-label.yaml
│   └── allowed-image-registry.yaml
└── tests/
    ├── invalid-replicas-deployment.yaml
    ├── valid-replicas-deployment.yaml
    ├── invalid-missing-owner-deployment.yaml
    ├── valid-owner-deployment.yaml
    ├── invalid-image-registry-pod.yaml
    └── valid-image-registry-pod.yaml
```

ArgoCD quản lý Lab 03 bằng 2 App:

```text
argocd/apps/
├── gatekeeper-custom-templates.yaml
└── gatekeeper-custom-constraints.yaml
```

Lý do tách thành 2 App:

- `ConstraintTemplate` phải được tạo trước.
- `Constraint` phụ thuộc vào `ConstraintTemplate`.
- Nếu apply cùng lúc, constraint có thể fail vì Kubernetes chưa biết kind custom mới.

## 3. Thứ tự GitOps chuẩn

Trong project này, thứ tự ArgoCD sync-wave là:

```text
wave 4  gatekeeper
wave 5  gatekeeper-templates
wave 6  gatekeeper-constraints
wave 7  gatekeeper-custom-templates
wave 8  gatekeeper-custom-constraints
```

Ý nghĩa:

- Wave 4 cài Gatekeeper controller và CRD.
- Wave 5-6 cài 4 policy bắt buộc của Lab 02.
- Wave 7-8 cài 3 policy tự viết của Lab 03.

Kiểm tra file App custom template:

```powershell
Get-Content argocd\apps\gatekeeper-custom-templates.yaml
```

Cần thấy:

```yaml
path: cloud/w10/project-02-secure-operate-gitops-lab/gatekeeper/custom/templates
argocd.argoproj.io/sync-wave: "7"
```

Kiểm tra file App custom constraint:

```powershell
Get-Content argocd\apps\gatekeeper-custom-constraints.yaml
```

Cần thấy:

```yaml
path: cloud/w10/project-02-secure-operate-gitops-lab/gatekeeper/custom/constraints
argocd.argoproj.io/sync-wave: "8"
```

## 4. Custom policy 1 - Giới hạn replicas của Deployment

File template:

```powershell
Get-Content gatekeeper\custom\templates\deployment-replica-limit.yaml
```

File này định nghĩa kind mới:

```yaml
kind: K8sDeploymentReplicaLimit
```

Logic Rego:

- Lấy `spec.replicas` của Deployment.
- Nếu không khai báo replicas thì xem như mặc định là `1`.
- Lấy `maxReplicas` từ constraint.
- Nếu `replicas > maxReplicas` thì reject.

File constraint:

```powershell
Get-Content gatekeeper\custom\constraints\deployment-replica-limit.yaml
```

Cấu hình enforce:

```yaml
kind: K8sDeploymentReplicaLimit
spec:
  enforcementAction: deny
  parameters:
    maxReplicas: 5
```

Policy này chỉ match:

```yaml
apiGroups: ["apps"]
kinds: ["Deployment"]
```

Vì đề bài yêu cầu reject Deployment nếu replicas lớn hơn 5, không cần áp dụng cho Pod hoặc Rollout.

## 5. Custom policy 2 - Bắt buộc workload có label owner

File template:

```powershell
Get-Content gatekeeper\custom\templates\required-owner-label.yaml
```

File này định nghĩa kind mới:

```yaml
kind: K8sRequiredWorkloadOwner
```

Logic Rego:

- Lấy label name từ parameter, mặc định là `owner`.
- Kiểm tra `metadata.labels`.
- Nếu workload không có label `owner`, hoặc label rỗng, thì reject.

File constraint:

```powershell
Get-Content gatekeeper\custom\constraints\required-owner-label.yaml
```

Cấu hình enforce:

```yaml
kind: K8sRequiredWorkloadOwner
spec:
  enforcementAction: deny
  parameters:
    labelName: owner
```

Policy này match các workload:

```text
Pod
Deployment
StatefulSet
DaemonSet
Job
CronJob
Rollout
```

Đây là policy quản trị ownership. Khi cluster có nhiều workload, label `owner` giúp biết team hoặc cá nhân chịu trách nhiệm.

## 6. Custom policy 3 - Chỉ cho image từ registry của mình

File template:

```powershell
Get-Content gatekeeper\custom\templates\allowed-image-registry.yaml
```

File này định nghĩa kind mới:

```yaml
kind: K8sAllowedImageRegistry
```

Logic Rego:

- Duyệt qua container trong Pod template.
- Lấy image của từng container.
- Chỉ cho image bắt đầu bằng prefix được cấu hình.
- Nếu image không bắt đầu bằng prefix đó thì reject.

File constraint:

```powershell
Get-Content gatekeeper\custom\constraints\allowed-image-registry.yaml
```

Cấu hình registry được phép:

```yaml
parameters:
  allowedPrefix: ghcr.io/heaven229-c/
```

Ý nghĩa:

- `ghcr.io/heaven229-c/w10-api:b1558d7` pass.
- `docker.io/library/nginx:1.27.3` reject.
- `nginx:1.27.3` reject.

Đây là policy supply chain cơ bản: workload chỉ được dùng image từ registry do mình kiểm soát.

## 7. Validate YAML trước khi commit

Đứng ở thư mục project:

```powershell
cd E:\Xbrain\tf_learning\cloud\w10\project-02-secure-operate-gitops-lab
```

Validate YAML bằng Python:

```powershell
$env:PYTHONIOENCODING='utf-8'
@'
from pathlib import Path
import yaml

paths = [
    Path("gatekeeper/custom/templates"),
    Path("gatekeeper/custom/constraints"),
    Path("gatekeeper/custom/tests"),
    Path("argocd/apps")
]

for folder in paths:
    for file in sorted(folder.glob("*.yaml")):
        list(yaml.safe_load_all(file.read_text(encoding="utf-8")))
        print("YAML_OK", file)
'@ | python -
```

Nếu không có traceback, YAML hợp lệ.

## 8. Commit và push code

Kiểm tra thay đổi:

```powershell
git status --short
```

Chỉ add các file của Lab 03:

```powershell
git add argocd\apps\gatekeeper-custom-templates.yaml
git add argocd\apps\gatekeeper-custom-constraints.yaml
git add gatekeeper\custom
git add guides\labs\LAB-03-CUSTOM-GATEKEEPER.md
```

Commit:

```powershell
git commit -m "feat(w10): add custom gatekeeper policies"
```

Push:

```powershell
git push origin main
```

Nếu đang ở branch khác, push branch hiện tại rồi tạo pull request trên GitHub Web UI.

## 9. Sync bằng ArgoCD

Vì máy hiện tại không dùng được lệnh `argocd app list`, dùng `kubectl` để kiểm tra Application.

Trước hết đảm bảo root app đang quản lý folder `argocd/apps`:

```powershell
kubectl apply -f argocd\root.yaml
```

Ép ArgoCD refresh root app:

```powershell
kubectl annotate application root -n argocd argocd.argoproj.io/refresh=hard --overwrite
```

Kiểm tra các App đã xuất hiện:

```powershell
kubectl get applications -n argocd
```

Kỳ vọng thấy thêm:

```text
gatekeeper-custom-templates
gatekeeper-custom-constraints
```

Kiểm tra trạng thái sync/health:

```powershell
kubectl get applications -n argocd -o custom-columns=NAME:.metadata.name,SYNC:.status.sync.status,HEALTH:.status.health.status
```

Nếu chưa sync ngay, mở ArgoCD UI và bấm sync theo thứ tự:

```text
root
gatekeeper-custom-templates
gatekeeper-custom-constraints
```

## 10. Kiểm tra Gatekeeper đã nhận template và constraint

Kiểm tra 3 ConstraintTemplate custom:

```powershell
kubectl get constrainttemplate k8sdeploymentreplicalimit
kubectl get constrainttemplate k8srequiredworkloadowner
kubectl get constrainttemplate k8sallowedimageregistry
```

Kiểm tra 3 Constraint custom:

```powershell
kubectl get k8sdeploymentreplicalimit
kubectl get k8srequiredworkloadowner
kubectl get k8sallowedimageregistry
```

Kỳ vọng:

```text
deployment-replica-limit
required-workload-owner
allowed-image-registry
```

Kiểm tra namespace `demo` đã bật enforce:

```powershell
kubectl get namespace demo --show-labels
```

Cần thấy:

```text
admission.gatekeeper.sh/enforce=true
```

## 11. Test policy 1 - Deployment replicas > 5 bị reject

Manifest vi phạm:

```powershell
Get-Content gatekeeper\custom\tests\invalid-replicas-deployment.yaml
```

Điểm vi phạm:

```yaml
replicas: 6
```

Chạy test:

```powershell
kubectl apply --dry-run=server -f gatekeeper\custom\tests\invalid-replicas-deployment.yaml
```

Kỳ vọng:

```text
Error from server (Forbidden)
```

Manifest hợp lệ:

```powershell
Get-Content gatekeeper\custom\tests\valid-replicas-deployment.yaml
```

Điểm hợp lệ:

```yaml
replicas: 5
```

Chạy test:

```powershell
kubectl apply --dry-run=server -f gatekeeper\custom\tests\valid-replicas-deployment.yaml
```

Kỳ vọng:

```text
deployment.apps/valid-replica-limit created (server dry run)
```

## 12. Test policy 2 - Thiếu label owner bị reject

Manifest vi phạm:

```powershell
Get-Content gatekeeper\custom\tests\invalid-missing-owner-deployment.yaml
```

Điểm vi phạm:

```yaml
metadata:
  labels:
    app: invalid-missing-owner
    env: w10
```

Không có:

```yaml
owner: platform-team
```

Chạy test:

```powershell
kubectl apply --dry-run=server -f gatekeeper\custom\tests\invalid-missing-owner-deployment.yaml
```

Kỳ vọng:

```text
Error from server (Forbidden)
```

Manifest hợp lệ:

```powershell
Get-Content gatekeeper\custom\tests\valid-owner-deployment.yaml
```

Chạy test:

```powershell
kubectl apply --dry-run=server -f gatekeeper\custom\tests\valid-owner-deployment.yaml
```

Kỳ vọng:

```text
deployment.apps/valid-owner-label created (server dry run)
```

## 13. Test policy 3 - Image ngoài registry bị reject

Manifest vi phạm:

```powershell
Get-Content gatekeeper\custom\tests\invalid-image-registry-pod.yaml
```

Điểm vi phạm:

```yaml
image: docker.io/library/nginx:1.27.3
```

Chạy test:

```powershell
kubectl apply --dry-run=server -f gatekeeper\custom\tests\invalid-image-registry-pod.yaml
```

Kỳ vọng:

```text
Error from server (Forbidden)
```

Manifest hợp lệ:

```powershell
Get-Content gatekeeper\custom\tests\valid-image-registry-pod.yaml
```

Điểm hợp lệ:

```yaml
image: ghcr.io/heaven229-c/w10-api:b1558d7
```

Chạy test:

```powershell
kubectl apply --dry-run=server -f gatekeeper\custom\tests\valid-image-registry-pod.yaml
```

Kỳ vọng:

```text
pod/valid-image-registry created (server dry run)
```

## 14. Vì sao dùng dry-run=server khi test

Lệnh:

```powershell
kubectl apply --dry-run=server -f <file>
```

vẫn gửi manifest lên Kubernetes API server, nên admission webhook của Gatekeeper vẫn chạy.

Ưu điểm:

- Vẫn chứng minh được reject/pass.
- Không tạo resource thật trong cluster.
- Tránh pod hợp lệ bị `ImagePullBackOff` nếu thiếu image pull secret.
- Phù hợp để demo policy admission cho mentor.

Nếu mentor yêu cầu tạo thật, bỏ `--dry-run=server` ở manifest hợp lệ rồi xóa sau test:

```powershell
kubectl apply -f gatekeeper\custom\tests\valid-image-registry-pod.yaml
kubectl delete pod valid-image-registry -n demo
```

## 15. Dọn resource nếu có apply thật

```powershell
kubectl delete deployment invalid-too-many-replicas -n demo --ignore-not-found
kubectl delete deployment valid-replica-limit -n demo --ignore-not-found
kubectl delete deployment invalid-missing-owner -n demo --ignore-not-found
kubectl delete deployment valid-owner-label -n demo --ignore-not-found
kubectl delete pod invalid-image-registry -n demo --ignore-not-found
kubectl delete pod valid-image-registry -n demo --ignore-not-found
```

## 16. Tiêu chí đạt Lab 03

Lab đạt khi chứng minh đủ:

| Điều kiện | Kết quả |
|---|---|
| Có 3 ConstraintTemplate custom | `kubectl get constrainttemplate` thấy đủ 3 template |
| Có 3 Constraint custom | `kubectl get` thấy đủ 3 constraint |
| Deployment 6 replicas | Reject |
| Deployment 5 replicas | Pass |
| Workload thiếu label owner | Reject |
| Workload có label owner | Pass |
| Image ngoài `ghcr.io/heaven229-c/` | Reject |
| Image trong `ghcr.io/heaven229-c/` | Pass |
| Triển khai qua GitOps | Có commit Git và ArgoCD App synced |

## 17. Diễn giải evidence cho mentor

Lab 03 chứng minh em đã tự viết policy admission bằng Rego thay vì chỉ dùng policy có sẵn. Ba `ConstraintTemplate` custom tạo ra ba loại constraint mới: giới hạn số replicas của Deployment, bắt buộc workload có label owner, và giới hạn image chỉ được lấy từ registry `ghcr.io/heaven229-c/`. Các constraint được quản lý bằng ArgoCD theo thứ tự template trước, constraint sau. Khi test, manifest vi phạm bị Kubernetes API server từ chối bởi Gatekeeper admission webhook, còn manifest hợp lệ được API server chấp nhận.
