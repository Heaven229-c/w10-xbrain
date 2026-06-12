# Demo Test Runbook - W9 GitOps Observability Canary

Runbook nay chay duoc tu luc khoi dong lab den luc demo day du 4 tieu chi cham bai. Dung PowerShell tren Windows, chay tu repo root `E:\Xbrain\tf_learning`.

Tat ca evidence la screenshot PNG luu trong `docs/image/`. Khong quay video.

## 0. Muc Tieu Demo

Sau khi chay xong, ban phai co du 12 screenshot:

| File | Proof |
| --- | --- |
| `docs/image/01-git-commit.png` | Git commit bad canary da doi desired state |
| `docs/image/02-actions-pass.png` | GitHub Actions W9 pass |
| `docs/image/03-argocd-synced-healthy.png` | ArgoCD apps `Synced/Healthy` |
| `docs/image/04-no-drift-self-heal.png` | Drift bi ArgoCD self-heal ve Git |
| `docs/image/05-reproduce-from-git.png` | Clean bootstrap/app-of-apps reproduce tu Git |
| `docs/image/06-slo-rule-query.png` | Prometheus SLO query co gia tri |
| `docs/image/07-alert-firing.png` | Alert `W9ApiHighErrorRate` firing |
| `docs/image/08-alert-email.png` | Email alert da nhan |
| `docs/image/09-canary-analysis-failed.png` | Bad canary `AnalysisRun` failed |
| `docs/image/10-canary-auto-aborted.png` | Rollout auto-aborted, giu version tot |
| `docs/image/11-git-revert-rollback-time.png` | `git revert` rollback duoi 300 giay |
| `docs/image/12-final-healthy.png` | Final state healthy sau rollback |

## 1. Nguyen Tac An Toan

- Khong commit SMTP password vao Git.
- SMTP password chi tao bang Kubernetes Secret va xoa sau demo.
- Tat ca thay doi workload di qua Git: khong `kubectl edit`, khong `kubectl set image`.
- Bad canary commit phai duoc rollback bang `git revert`.
- Neu dung email ca nhan trong Git, reset ve placeholder sau demo.

## 2. Chuan Bi Terminal Va Bien Moi Truong

Mo PowerShell tai repo root:

```powershell
Set-Location E:\Xbrain\tf_learning
```

Tao bien dung chung:

```powershell
$Project = "cloud/w9/project-01-gitops-observability-canary"
$ProjectAbs = Join-Path (Get-Location) $Project
$AppPath = "$Project/apps/w9-api/base/rollout.yaml"
$AlertPath = "$Project/apps/w9-api/base/alertmanagerconfig.yaml"
$ImageDir = "$Project/docs/image"
New-Item -ItemType Directory -Force $ImageDir | Out-Null
```

Kiem tra tool:

```powershell
docker version
git --version
kubectl version --client
minikube version
helm version
python --version
```

Kiem tra Git:

```powershell
git branch --show-current
git status --short
git log --oneline -5
git remote -v
```

Expected:

- Branch demo la `main`.
- Khong co secret/staged file ngoai y muon.
- Remote tro toi GitHub repo ma ArgoCD dang doc.

## 3. Khoi Dong Kubernetes W9 Tu Dau

Start minikube profile `w9`:

```powershell
minikube start -p w9 --driver=docker --cpus=4 --memory=6144
kubectl config use-context w9
kubectl config current-context
kubectl get nodes -o wide
```

Expected:

```text
w9
```

Add/update Helm repos:

```powershell
helm repo add argo https://argoproj.github.io/argo-helm --force-update
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts --force-update
helm repo update
helm repo list
```

Build baseline image dang duoc Git khai bao trong `rollout.yaml`:

```powershell
Set-Location $ProjectAbs
minikube image build -p w9 -t w9-api:3 app
minikube image ls -p w9 | Select-String "w9-api"
Set-Location E:\Xbrain\tf_learning
```

Validate source va manifest truoc khi cho ArgoCD sync:

```powershell
python -m py_compile cloud\w9\project-01-gitops-observability-canary\app\app.py
kubectl kustomize $Project/apps/w9-api/overlays/dev |
  Select-String -Pattern "kind: Rollout|kind: AnalysisTemplate|kind: ServiceMonitor|kind: PrometheusRule|kind: AlertmanagerConfig|image: w9-api:3|value: v3"
```

Neu `py_compile` tao `__pycache__`, xoa file build local:

```powershell
Get-ChildItem -Path $Project -Recurse -Directory -Filter __pycache__ |
  Remove-Item -Recurse -Force
```

## 4. Dam Bao Desired State Da O Tren GitHub

ArgoCD khong doc file local. No doc `targetRevision: main` tu GitHub. Neu co thay doi W9 chua push, commit/push truoc khi cai root app.

Kiem tra:

```powershell
git status --short
```

Neu can push desired state hien tai:

```powershell
git add .github/workflows/w9-validate-on-pr.yml
git add .github/workflows/w9-gitops-on-merge.yml
git add cloud/w9/project-01-gitops-observability-canary/app
git add cloud/w9/project-01-gitops-observability-canary/apps/w9-api
git add cloud/w9/project-01-gitops-observability-canary/argocd
git add cloud/w9/project-01-gitops-observability-canary/ci/github-actions
git add cloud/w9/project-01-gitops-observability-canary/README.md
git add cloud/w9/project-01-gitops-observability-canary/EVIDENCE.md
git add cloud/w9/project-01-gitops-observability-canary/DEMO-TEST-RUNBOOK.md
git commit -m "prepare w9 demo desired state"
git push origin main
```

Neu khong co file staged thi `git commit` co the bao nothing to commit. Luc do bo qua va tiep tuc.

## 5. Cai ArgoCD Va App-Of-Apps

Tao namespace va cai ArgoCD:

```powershell
kubectl create namespace argocd --dry-run=client -o yaml | kubectl apply -f -
helm upgrade --install argocd argo/argo-cd -n argocd
kubectl rollout status deployment/argocd-server -n argocd --timeout=300s
kubectl get pods -n argocd
```

Apply root app duy nhat:

```powershell
kubectl apply -f $Project/argocd/app-of-apps.yaml
kubectl get applications -n argocd
```

Cho cac app sync/healthy:

```powershell
$Apps = @("w9-app-of-apps", "argo-rollouts", "kube-prometheus-stack", "w9-api")
foreach ($App in $Apps) {
  do {
    Start-Sleep -Seconds 15
    $Sync = kubectl get application $App -n argocd -o jsonpath='{.status.sync.status}' 2>$null
    $Health = kubectl get application $App -n argocd -o jsonpath='{.status.health.status}' 2>$null
    Write-Host "$App sync=$Sync health=$Health"
  } until ($Sync -eq "Synced" -and $Health -eq "Healthy")
}
```

Verify cluster state:

```powershell
kubectl get applications -n argocd
kubectl get ns
kubectl get pods -n argo-rollouts
kubectl get pods -n observability
kubectl get rollout,pods,svc -n demo
kubectl get analysistemplate,servicemonitor,prometheusrule,alertmanagerconfig -n demo
```

Chup evidence `docs/image/05-reproduce-from-git.png`:

- Terminal hien `git log --oneline -1`.
- Terminal hien `kubectl get applications -n argocd`.
- Terminal hien `kubectl get rollout,pods,svc -n demo`.

Mo ArgoCD UI de chup status:

```powershell
$EncodedPassword = kubectl get secret argocd-initial-admin-secret -n argocd -o jsonpath="{.data.password}"
$ArgoPassword = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($EncodedPassword))
Write-Host "ArgoCD user: admin"
Write-Host "ArgoCD password: $ArgoPassword"
kubectl port-forward svc/argocd-server -n argocd 8081:443
```

Mo browser:

```text
https://localhost:8081
```

Chup evidence `docs/image/03-argocd-synced-healthy.png` khi ArgoCD hien cac app `Synced/Healthy`.

Dung port-forward bang `Ctrl+C` neu khong can UI nua.

## 6. Smoke Test App Va Metrics

Terminal 1:

```powershell
kubectl port-forward svc/w9-api -n demo 8080:80
```

Terminal 2:

```powershell
Invoke-RestMethod http://localhost:8080/api/status
Invoke-WebRequest http://localhost:8080/metrics |
  Select-Object -ExpandProperty Content |
  Select-String "flask_http_request_total"
```

Expected API:

```text
version: v3
status: ok
frontend: healthy
backend: healthy
```

Tao baseline traffic:

```powershell
1..100 | ForEach-Object {
  Invoke-RestMethod http://localhost:8080/api/status | Out-Null
  Start-Sleep -Milliseconds 200
}
```

Dung port-forward bang `Ctrl+C` khi xong.

## 7. GitOps No Drift / Self-Heal

Tao drift truc tiep tren cluster:

```powershell
kubectl get rollout w9-api -n demo
kubectl scale rollout w9-api -n demo --replicas=1
kubectl get rollout w9-api -n demo
```

Ep ArgoCD refresh va doi self-heal:

```powershell
kubectl annotate application w9-api -n argocd argocd.argoproj.io/refresh=hard --overwrite

do {
  Start-Sleep -Seconds 10
  $Replicas = kubectl get rollout w9-api -n demo -o jsonpath='{.spec.replicas}'
  $Available = kubectl get rollout w9-api -n demo -o jsonpath='{.status.availableReplicas}'
  $Sync = kubectl get application w9-api -n argocd -o jsonpath='{.status.sync.status}'
  $Health = kubectl get application w9-api -n argocd -o jsonpath='{.status.health.status}'
  Write-Host "replicas=$Replicas available=$Available sync=$Sync health=$Health"
} until ($Replicas -eq "2" -and $Sync -eq "Synced" -and $Health -eq "Healthy")

kubectl get application w9-api -n argocd
kubectl get rollout w9-api -n demo
```

Chup evidence `docs/image/04-no-drift-self-heal.png` voi output co:

- Drift da scale xuong `1`.
- ArgoCD dua replicas ve `2`.
- `w9-api` ve `Synced/Healthy`.

## 8. SLO Query Va Observability

Port-forward app va tao traffic neu chua co:

```powershell
kubectl port-forward svc/w9-api -n demo 8080:80
```

Terminal khac:

```powershell
1..80 | ForEach-Object {
  Invoke-RestMethod http://localhost:8080/api/status | Out-Null
  Start-Sleep -Milliseconds 250
}
```

Port-forward Prometheus:

```powershell
kubectl port-forward svc/kube-prometheus-stack-prometheus -n observability 9090:9090
```

Mo browser:

```text
http://localhost:9090
```

Chay PromQL:

```promql
w9_api:slo_success_rate:2m
```

Expected:

- Khi app healthy, value gan `1`.
- Rule threshold alert la `< 0.98`.

Chup evidence `docs/image/06-slo-rule-query.png`.

Optional Grafana check:

```powershell
kubectl port-forward svc/kube-prometheus-stack-grafana -n observability 3000:80
```

Mo:

```text
http://localhost:3000
username: admin
password: admin
```

Dung cac port-forward bang `Ctrl+C` khi xong.

## 9. Cau Hinh Email Alert Qua Git

Dat email nhan/gui. Vi du Gmail thi dung App Password, khong dung password dang nhap Gmail.

```powershell
$AlertTo = "your-personal-email@gmail.com"
$AlertFrom = "your-sender-email@gmail.com"
```

Thay placeholder trong `AlertmanagerConfig`:

```powershell
(Get-Content $AlertPath) `
  -replace "CHANGE_ME_PERSONAL_EMAIL@example.com", $AlertTo `
  -replace "CHANGE_ME_SENDER_EMAIL@example.com", $AlertFrom |
  Set-Content -Path $AlertPath -Encoding utf8
```

Kiem tra diff:

```powershell
git diff -- $AlertPath
```

Commit va push email route:

```powershell
git add $AlertPath
git commit -m "configure w9 alert email"
git push origin main
```

Tao SMTP password secret tren cluster, khong ghi password vao Git:

```powershell
$SmtpPassword = Read-Host "SMTP app password" -AsSecureString
$Bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SmtpPassword)
$SmtpPasswordPlain = [Runtime.InteropServices.Marshal]::PtrToStringAuto($Bstr)
kubectl create secret generic alertmanager-smtp-auth `
  -n demo `
  --from-literal=password="$SmtpPasswordPlain" `
  --dry-run=client -o yaml | kubectl apply -f -
[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($Bstr)
Remove-Variable SmtpPasswordPlain
Remove-Variable SmtpPassword
```

Refresh va kiem tra config:

```powershell
kubectl annotate application w9-api -n argocd argocd.argoproj.io/refresh=hard --overwrite
kubectl get application w9-api -n argocd
kubectl get alertmanagerconfig w9-api-email-alerts -n demo -o yaml
kubectl get alertmanager kube-prometheus-stack-alertmanager -n observability -o yaml |
  Select-String -Pattern "alertmanagerConfigSelector|alertmanagerConfigNamespaceSelector" -Context 0,3
```

Expected:

```text
alertmanagerConfigNamespaceSelector: {}
alertmanagerConfigSelector: {}
```

## 10. Tao Bad Canary Commit Qua Git

Build image tag `v4` vao minikube:

```powershell
Set-Location $ProjectAbs
minikube image build -p w9 -t w9-api:4 app
minikube image ls -p w9 | Select-String "w9-api"
Set-Location E:\Xbrain\tf_learning
```

Doi desired state tu version tot `v3` sang bad canary `v4`:

```powershell
(Get-Content $AppPath) `
  -replace "image: w9-api:3", "image: w9-api:4" `
  -replace "value: v3", "value: v4" `
  -replace 'value: "0"', 'value: "1"' |
  Set-Content -Path $AppPath -Encoding utf8
```

Validate manifest:

```powershell
kubectl kustomize $Project/apps/w9-api/overlays/dev |
  Select-String -Pattern "image: w9-api:4|value: v4|value: `"1`"|kind: Rollout|kind: AnalysisTemplate"
git diff -- $AppPath
```

Commit va push:

```powershell
git add $AppPath
git commit -m "test bad w9 canary"
git push origin main
git show --stat --oneline --name-only HEAD
```

Chup evidence `docs/image/01-git-commit.png` voi `git show` va diff bad canary.

Mo GitHub Actions page, doi workflow W9 pass, roi chup evidence `docs/image/02-actions-pass.png`:

```powershell
Start-Process "https://github.com/G-03-XBrain-Phase-2/hoangson-aws-accelerator-p2/actions"
```

Refresh ArgoCD:

```powershell
kubectl annotate application w9-api -n argocd argocd.argoproj.io/refresh=hard --overwrite
kubectl get application w9-api -n argocd
```

## 11. Chay Canary, Traffic, Va Bat Loi

Terminal 1 - watch rollout:

```powershell
kubectl get rollout w9-api -n demo -w
```

Terminal 2 - watch AnalysisRun:

```powershell
kubectl get analysisrun -n demo -w
```

Terminal 3 - port-forward app:

```powershell
kubectl port-forward svc/w9-api -n demo 8080:80
```

Terminal 4 - generate traffic lien tuc:

```powershell
1..1200 | ForEach-Object {
  try {
    $Response = Invoke-RestMethod http://localhost:8080/api/status
    Write-Host "ok version=$($Response.version)"
  } catch {
    Write-Host "expected 500 from bad canary"
  }
  Start-Sleep -Milliseconds 150
}
```

Expected:

- Trong canary co request vao `v4` bi 500 vi `FAIL_RATE=1`.
- `AnalysisRun` fail do success rate < `0.98`.
- Rollout bi abort va traffic quay ve version tot.

Sau khi thay fail/abort, chay:

```powershell
kubectl get rollout w9-api -n demo
kubectl get analysisrun -n demo
kubectl describe analysisrun -n demo
kubectl describe rollout w9-api -n demo
```

Chup evidence:

- `docs/image/09-canary-analysis-failed.png`: terminal co `AnalysisRun` phase `Failed`.
- `docs/image/10-canary-auto-aborted.png`: terminal co rollout aborted/degraded va stable version van available.

## 12. Kiem Tra Alert Firing Va Email

Port-forward Alertmanager:

```powershell
kubectl port-forward svc/kube-prometheus-stack-alertmanager -n observability 9093:9093
```

Mo browser:

```text
http://localhost:9093
```

Expected:

- Alert `W9ApiHighErrorRate` xuat hien.
- Status la `Firing`.

Neu muon verify bang Prometheus API:

```powershell
kubectl port-forward svc/kube-prometheus-stack-prometheus -n observability 9090:9090
```

Terminal khac:

```powershell
Invoke-RestMethod "http://localhost:9090/api/v1/query?query=ALERTS%7Balertname%3D%22W9ApiHighErrorRate%22%7D" |
  ConvertTo-Json -Depth 10
```

Expected co:

```text
alertstate: firing
```

Kiem tra hop thu email ca nhan.

Chup evidence:

- `docs/image/07-alert-firing.png`: Alertmanager hoac Prometheus API hien firing.
- `docs/image/08-alert-email.png`: email alert da nhan, che password/token neu co.

## 13. Rollback Bang Git Revert Duoi 5 Phut

Quan trong: lenh nay gia dinh bad canary commit la commit moi nhat.

Chay rollback timer:

```powershell
$Start = Get-Date
git revert --no-edit HEAD
git push origin main
kubectl annotate application w9-api -n argocd argocd.argoproj.io/refresh=hard --overwrite

do {
  Start-Sleep -Seconds 10
  $Sync = kubectl get application w9-api -n argocd -o jsonpath='{.status.sync.status}'
  $Health = kubectl get application w9-api -n argocd -o jsonpath='{.status.health.status}'
  $Available = kubectl get rollout w9-api -n demo -o jsonpath='{.status.availableReplicas}'
  Write-Host "sync=$Sync health=$Health available=$Available"
} until ($Sync -eq "Synced" -and $Health -eq "Healthy" -and $Available -eq "2")

$Elapsed = [math]::Round(((Get-Date) - $Start).TotalSeconds, 2)
Write-Host "Rollback seconds: $Elapsed"
```

Expected:

```text
Rollback seconds: < 300
```

Kiem tra app da ve version tot:

```powershell
Invoke-RestMethod http://localhost:8080/api/status
kubectl get applications -n argocd
kubectl get rollout,pods -n demo
git log --oneline -5
```

Chup evidence:

- `docs/image/11-git-revert-rollback-time.png`: terminal co `Rollback seconds`.
- `docs/image/12-final-healthy.png`: ArgoCD/app/rollout final healthy, API `version: v3`.

## 14. Cleanup Bat Buoc Sau Demo

Tat tat ca watch/port-forward bang `Ctrl+C`.

Xoa SMTP secret khoi cluster:

```powershell
kubectl delete secret alertmanager-smtp-auth -n demo --ignore-not-found
```

Neu da commit email that, reset placeholder trong Git:

```powershell
(Get-Content $AlertPath) `
  -replace [regex]::Escape($AlertTo), "CHANGE_ME_PERSONAL_EMAIL@example.com" `
  -replace [regex]::Escape($AlertFrom), "CHANGE_ME_SENDER_EMAIL@example.com" |
  Set-Content -Path $AlertPath -Encoding utf8

git diff -- $AlertPath
git add $AlertPath
git commit -m "reset w9 demo email placeholders"
git push origin main
kubectl annotate application w9-api -n argocd argocd.argoproj.io/refresh=hard --overwrite
```

Kiem tra final:

```powershell
kubectl get applications -n argocd
kubectl get rollout,pods -n demo
kubectl get alertmanagerconfig w9-api-email-alerts -n demo -o yaml
git status --short
git log --oneline -5
```

Expected:

- `w9-api` `Synced/Healthy`.
- Rollout replicas ve `2`.
- `rollout.yaml` o Git ve `image: w9-api:3`, `APP_VERSION=v3`, `FAIL_RATE="0"`.
- SMTP secret da xoa.
- Email config da reset placeholder neu ban khong muon luu email that.

## 15. Optional Destroy Local Lab

Chi chay sau khi da chup het evidence:

```powershell
Set-Location $ProjectAbs
kubectl delete -f argocd/app-of-apps.yaml --ignore-not-found
helm uninstall argocd -n argocd
kubectl delete namespace argocd argo-rollouts observability demo --ignore-not-found
minikube delete -p w9
Set-Location E:\Xbrain\tf_learning
```

## 16. Bang Evidence Cuoi

Dung dung ten file nay trong `EVIDENCE.md`:

| Step | Screenshot |
| --- | --- |
| Bad canary Git commit | `docs/image/01-git-commit.png` |
| GitHub Actions pass | `docs/image/02-actions-pass.png` |
| ArgoCD synced healthy | `docs/image/03-argocd-synced-healthy.png` |
| No drift self-heal | `docs/image/04-no-drift-self-heal.png` |
| Reproduce from Git | `docs/image/05-reproduce-from-git.png` |
| SLO query | `docs/image/06-slo-rule-query.png` |
| Alert firing | `docs/image/07-alert-firing.png` |
| Alert email | `docs/image/08-alert-email.png` |
| Canary analysis failed | `docs/image/09-canary-analysis-failed.png` |
| Canary auto-aborted | `docs/image/10-canary-auto-aborted.png` |
| Git revert rollback time | `docs/image/11-git-revert-rollback-time.png` |
| Final healthy | `docs/image/12-final-healthy.png` |

Khong can va khong nop video.
