# Lab 04 - Rotate Secret bằng AWS Secrets Manager + ESO, không restart pod

## 1. Mục tiêu lab

Lab này chuyển DB password từ cách quản lý thủ công trong Kubernetes Secret sang mô hình:

```text
AWS Secrets Manager
        ↓
External Secrets Operator
        ↓
Kubernetes Secret db-secret
        ↓
Pod mount Secret dạng volume
        ↓
App đọc password từ file khi cần
```

Kết quả cần chứng minh:

| Kiểm tra | Kỳ vọng |
|---|---|
| Đổi value trên AWS Secrets Manager | Kubernetes Secret `db-secret` đổi theo trong dưới 60 giây |
| Kiểm tra pod sau khi rotate | Pod name/UID/creationTimestamp/restartCount không đổi |
| App đọc secret | Endpoint trả hash mới sau khi secret volume cập nhật |
| Kiểm tra repo | Không commit AWS credentials hoặc password thật |

## 2. Vì sao không dùng env var cho password

Nếu pod đọc password bằng environment variable:

```yaml
env:
  - name: DB_PASSWORD
    valueFrom:
      secretKeyRef:
        name: db-secret
        key: password
```

thì khi Kubernetes Secret đổi, biến môi trường trong process đang chạy không đổi. Muốn app thấy password mới thường phải restart pod.

Trong lab này app dùng mounted Secret volume:

```yaml
volumeMounts:
  - name: db-secret
    mountPath: /var/run/secrets/w10-db
    readOnly: true
```

Kubernetes có thể cập nhật file trong mounted Secret volume mà không recreate pod. App đọc file `/var/run/secrets/w10-db/password` mỗi lần gọi endpoint, nên có thể thấy secret mới mà không restart.

## 3. File được cấu hình trong project

ESO config:

```text
eso/
├── README.md
├── secret-store.yaml
└── external-secret.yaml
```

ArgoCD Apps:

```text
argocd/apps/
├── eso.yaml
└── eso-config.yaml
```

App API:

```text
src/api/app.py
app-api/rollout.yaml
```

## 4. Thứ tự GitOps chuẩn

Thứ tự phải là:

```text
1. common namespace
2. ESO operator + CRD
3. SecretStore + ExternalSecret
4. App API mount db-secret
```

Trong project:

| File | ArgoCD App | Sync wave | Vai trò |
|---|---|---:|---|
| `argocd/apps/app-common.yaml` | `common` | `-1` | Tạo namespace `demo` |
| `argocd/apps/eso.yaml` | `external-secrets` | `0` | Cài ESO operator + CRD |
| `argocd/apps/eso-config.yaml` | `eso-config` | `1` | Sync `SecretStore` + `ExternalSecret` |
| `argocd/apps/app-api.yaml` | `api` | `2` | Deploy app đọc mounted secret |

Không sync `SecretStore` và `ExternalSecret` trước operator. Nếu làm vậy Kubernetes sẽ báo lỗi kiểu:

```text
no matches for kind "SecretStore"
no matches for kind "ExternalSecret"
```

## 5. Kiểm tra app đã dùng mounted Secret

Mở Rollout:

```powershell
Get-Content app-api\rollout.yaml
```

Cần thấy:

```yaml
env:
  - name: DB_PASSWORD_FILE
    value: /var/run/secrets/w10-db/password
volumeMounts:
  - name: db-secret
    mountPath: /var/run/secrets/w10-db
    readOnly: true
volumes:
  - name: db-secret
    secret:
      secretName: db-secret
      optional: true
```

`optional: true` giúp app vẫn start được trong lúc ESO chưa sync xong secret lần đầu. Khi `db-secret` xuất hiện, kubelet sẽ cập nhật mounted volume.

Mở source app:

```powershell
Get-Content src\api\app.py
```

Cần thấy endpoint:

```text
/db-password-status
```

Endpoint này không trả password thật. Nó chỉ trả:

- Secret đã mount hay chưa.
- Đường dẫn file secret.
- Độ dài password.
- Prefix hash SHA256 để chứng minh giá trị đã đổi.

## 6. Tạo secret nguồn trên AWS Secrets Manager

Phần này nên làm trên AWS Console để dễ quan sát và chụp evidence. CLI chỉ giữ lại như phương án dự phòng.

### Cách chính - thao tác trên AWS Console

1. Mở AWS Console.
2. Chọn region `ap-southeast-1` ở góc phải trên cùng.
3. Vào **Secrets Manager**.
4. Chọn **Store a new secret**.
5. Ở **Secret type**, chọn **Other type of secret**.
6. Ở phần key/value, nhập:

```text
key: password
value: lab4-v1-<chuoi-ngau-nhien>
```

Ví dụ value có thể là:

```text
lab4-v1-a1b2c3d4
```

Không dùng password thật của cá nhân/công ty cho lab.

7. Chọn encryption key mặc định `aws/secretsmanager`, trừ khi mentor yêu cầu KMS riêng.
8. Ở **Secret name**, nhập chính xác:

```text
w10/project02/db
```

9. Description có thể ghi:

```text
W10 Project 02 demo DB password synced by External Secrets Operator
```

10. Không bật automatic rotation ở lab này. Lab đang kiểm tra manual rotate và ESO sync.
11. Review rồi chọn **Store**.

Evidence nên chụp:

- Secret name `w10/project02/db`.
- Region `ap-southeast-1`.
- Không chụp giá trị password plaintext.

### Cách dự phòng - dùng AWS CLI

Đứng ở thư mục project:

```powershell
cd E:\Xbrain\tf_learning\cloud\w10\project-02-secure-operate-gitops-lab
```

Khai báo biến:

```powershell
$AwsRegion = "ap-southeast-1"
$AwsSecretName = "w10/project02/db"
```

Tạo password version 1 để demo:

```powershell
$DbPasswordV1 = "lab4-v1-$([guid]::NewGuid().ToString('N').Substring(0,8))"
$SecretJsonV1 = @{ password = $DbPasswordV1 } | ConvertTo-Json -Compress
```

Tạo secret trên AWS nếu chưa tồn tại:

```powershell
aws secretsmanager create-secret `
  --name $AwsSecretName `
  --secret-string $SecretJsonV1 `
  --region $AwsRegion
```

Nếu secret đã tồn tại, cập nhật value:

```powershell
aws secretsmanager put-secret-value `
  --secret-id $AwsSecretName `
  --secret-string $SecretJsonV1 `
  --region $AwsRegion
```

Kiểm tra secret tồn tại trên AWS:

```powershell
aws secretsmanager describe-secret `
  --secret-id $AwsSecretName `
  --region $AwsRegion
```

Không chụp password thật trong evidence. Chỉ chụp tên secret, region, version metadata.

## 7. Tạo IAM credentials cho ESO

Phần IAM nên tạo trên AWS Console. Sau đó chỉ đưa access key vào cluster bằng `kubectl create secret`. Tuyệt đối không commit access key vào Git.

### Tạo IAM policy trên AWS Console

1. Mở AWS Console.
2. Vào **IAM**.
3. Chọn **Policies**.
4. Chọn **Create policy**.
5. Chọn tab **JSON**.
6. Dán policy tối thiểu bên dưới, nhớ thay `<ACCOUNT_ID>` bằng AWS Account ID của bạn:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue",
        "secretsmanager:DescribeSecret"
      ],
      "Resource": "arn:aws:secretsmanager:ap-southeast-1:<ACCOUNT_ID>:secret:w10/project02/db-*"
    }
  ]
}
```

7. Đặt policy name:

```text
W10Project02ESOReadSecretPolicy
```

8. Chọn **Create policy**.

### Tạo IAM user/access key trên AWS Console

1. Trong **IAM**, chọn **Users**.
2. Chọn **Create user**.
3. User name:

```text
w10-project02-eso-reader
```

4. Không cần bật Console access.
5. Ở phần permission, chọn **Attach policies directly**.
6. Gắn policy `W10Project02ESOReadSecretPolicy`.
7. Tạo user.
8. Vào user vừa tạo, chọn tab **Security credentials**.
9. Chọn **Create access key**.
10. Use case chọn **Other** hoặc **Application running outside AWS**.
11. Description:

```text
w10-project02-eso-minikube
```

12. Lưu lại **Access key ID** và **Secret access key** tạm thời để tạo Kubernetes Secret ở bước dưới.

Evidence nên chụp:

- IAM user name.
- Policy được attach.
- Không chụp Secret access key.

### Đưa IAM credentials vào Kubernetes Secret

Credentials runtime này tạo bằng `kubectl create secret`, không commit vào Git.

Khai báo access key:

```powershell
$AwsAccessKeyId = Read-Host "Paste AWS access key id for ESO"
$AwsSecretAccessKeySecure = Read-Host "Paste AWS secret access key for ESO" -AsSecureString
$Bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($AwsSecretAccessKeySecure)
$AwsSecretAccessKey = [Runtime.InteropServices.Marshal]::PtrToStringAuto($Bstr)
```

Tạo Kubernetes Secret runtime-only:

```powershell
kubectl delete secret aws-credentials -n demo --ignore-not-found

kubectl create secret generic aws-credentials -n demo `
  --from-literal=access-key-id=$AwsAccessKeyId `
  --from-literal=secret-access-key=$AwsSecretAccessKey
```

Dọn biến trong terminal:

```powershell
[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($Bstr)
Remove-Variable AwsAccessKeyId
Remove-Variable AwsSecretAccessKey
Remove-Variable AwsSecretAccessKeySecure
Remove-Variable Bstr
```

Kiểm tra Secret runtime đã có:

```powershell
kubectl get secret aws-credentials -n demo
```

Không dùng lệnh `kubectl get secret aws-credentials -o yaml` để chụp evidence, vì output chứa base64 credentials.

## 8. Kiểm tra nhanh quyền IAM trên Console

Trên AWS Console, kiểm tra lại trước khi sync ESO:

1. Vào **IAM**.
2. Chọn **Users**.
3. Mở user `w10-project02-eso-reader`.
4. Vào tab **Permissions**.
5. Xác nhận user có policy `W10Project02ESOReadSecretPolicy`.
6. Mở policy và kiểm tra chỉ có quyền:

```text
secretsmanager:GetSecretValue
secretsmanager:DescribeSecret
```

7. Kiểm tra Resource trỏ đúng secret:

```text
arn:aws:secretsmanager:ap-southeast-1:<ACCOUNT_ID>:secret:w10/project02/db-*
```

Nếu AWS secret dùng KMS customer managed key, user cần thêm `kms:Decrypt` cho key đó. Nếu dùng key mặc định `aws/secretsmanager` cho lab thì thường không cần cấu hình KMS riêng.

## 9. Kiểm tra SecretStore và ExternalSecret manifest

Mở SecretStore:

```powershell
Get-Content eso\secret-store.yaml
```

Cần thấy:

```yaml
kind: SecretStore
metadata:
  name: aws-secrets-manager
  namespace: demo
spec:
  provider:
    aws:
      service: SecretsManager
      region: ap-southeast-1
```

Mở ExternalSecret:

```powershell
Get-Content eso\external-secret.yaml
```

Cần thấy:

```yaml
refreshInterval: 30s
target:
  name: db-secret
data:
  - secretKey: password
    remoteRef:
      key: w10/project02/db
      property: password
```

Giải thích:

- `refreshInterval: 30s` đủ ngắn để chứng minh rotate dưới 60 giây trong lab.
- Không nên đặt quá ngắn ở production vì sẽ tăng số lần gọi AWS Secrets Manager.
- `remoteRef.key` là secret name trên AWS.
- `remoteRef.property` lấy field `password` trong JSON secret.
- `target.name` là Kubernetes Secret ESO tạo ra trong namespace `demo`.

## 10. Commit và push code lên Git trước khi sync ArgoCD

Đây là bước bắt buộc trong GitOps.

ArgoCD không đọc file local trên máy. ArgoCD chỉ đọc manifest từ Git repository. Vì vậy nếu chỉ sửa file local rồi chạy `kubectl annotate application root ...`, root app vẫn không thấy thay đổi mới.

Thứ tự đúng là:

```text
Sửa code/config local
        ↓
git add
        ↓
git commit
        ↓
git push origin main
        ↓
ArgoCD refresh/sync root
        ↓
Cluster nhận cấu hình mới
```

Kiểm tra thay đổi trước khi commit:

```powershell
git status --short
```

Chỉ commit cấu hình và docs, không commit runtime secret:

```powershell
git add -A -- `
  src\api\app.py `
  app-api\rollout.yaml `
  eso `
  k8s-eso `
  argocd\apps\eso.yaml `
  argocd\apps\eso-config.yaml `
  argocd\apps\k8s-external-secrets.yaml `
  guides\labs\LAB-04-ESO-SECRET-ROTATION.md

git commit -m "feat(w10): add eso secret rotation lab"
git push origin main
```

Ghi chú:

- `argocd/apps/k8s-external-secrets.yaml` và `k8s-eso/` được remove khỏi Git vì đã chuẩn hóa sang `argocd/apps/eso.yaml`, `argocd/apps/eso-config.yaml`, và `eso/`.
- Vì có thay đổi `src/api/app.py`, workflow build image của project 02 sẽ build/push image mới và commit update `app-api/rollout.yaml`.
- Sau khi GitHub Actions commit image mới, cần `git pull` về local nếu muốn local khớp với remote.
- Bài test rotate secret bắt đầu sau khi ArgoCD đã deploy pod API với image mới có endpoint `/db-password-status`.

Kiểm tra trên GitHub Web UI:

1. Mở repository `Heaven229-c/w10-xbrain`.
2. Kiểm tra commit `feat(w10): add eso secret rotation lab` đã xuất hiện trên branch `main`.
3. Vào tab **Actions**.
4. Chờ workflow build image project 02 hoàn tất nếu workflow được trigger.
5. Kiểm tra commit tự động update `app-api/rollout.yaml` nếu có.

Sau khi code đã nằm trên GitHub, mới chuyển sang sync ArgoCD.

## 11. Sync bằng ArgoCD

Apply hoặc refresh root app:

```powershell
kubectl apply -f argocd\root.yaml
kubectl annotate application root -n argocd argocd.argoproj.io/refresh=hard --overwrite
```

Kiểm tra các ArgoCD Application:

```powershell
kubectl get applications -n argocd -o custom-columns=NAME:.metadata.name,SYNC:.status.sync.status,HEALTH:.status.health.status
```

Cần thấy:

```text
external-secrets
eso-config
api
```

Nếu muốn refresh riêng:

```powershell
kubectl annotate application external-secrets -n argocd argocd.argoproj.io/refresh=hard --overwrite
kubectl annotate application eso-config -n argocd argocd.argoproj.io/refresh=hard --overwrite
kubectl annotate application api -n argocd argocd.argoproj.io/refresh=hard --overwrite
```

## 12. Kiểm tra ESO operator

Kiểm tra pod operator:

```powershell
kubectl get pods -n external-secrets
```

Kỳ vọng các pod ESO ở trạng thái `Running`.

Kiểm tra CRD đã có:

```powershell
kubectl get crd secretstores.external-secrets.io
kubectl get crd externalsecrets.external-secrets.io
```

Nếu CRD chưa có, không sync `eso-config` vội. Cần xử lý operator trước.

## 13. Kiểm tra SecretStore và ExternalSecret

Kiểm tra resource:

```powershell
kubectl get secretstore aws-secrets-manager -n demo
kubectl get externalsecret db-password -n demo
```

Xem trạng thái chi tiết:

```powershell
kubectl describe secretstore aws-secrets-manager -n demo
kubectl describe externalsecret db-password -n demo
```

Kỳ vọng `ExternalSecret` có điều kiện Ready/Synced. Nếu lỗi thường gặp:

| Lỗi | Nguyên nhân |
|---|---|
| `SecretSyncedError` | Sai AWS credentials, thiếu IAM permission, sai region hoặc sai secret name |
| `AccessDeniedException` | IAM user/role thiếu `secretsmanager:GetSecretValue` |
| `ResourceNotFoundException` | AWS secret `w10/project02/db` chưa tồn tại hoặc sai region |
| `could not find secret aws-credentials` | Chưa tạo Kubernetes Secret runtime `aws-credentials` trong namespace `demo` |

## 14. Kiểm tra Kubernetes Secret được ESO tạo

Chạy:

```powershell
kubectl get secret db-secret -n demo
```

Không in password thật. Chỉ lấy fingerprint:

```powershell
$Encoded = kubectl get secret db-secret -n demo -o jsonpath="{.data.password}"
$Plain = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($Encoded))
$Sha = [Security.Cryptography.SHA256]::Create()
$HashBytes = $Sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($Plain))
$Hash = -join ($HashBytes | ForEach-Object { $_.ToString("x2") })
"length=$($Plain.Length) sha256_prefix=$($Hash.Substring(0,12))"
$SecretHashBefore = $Hash.Substring(0,12)
$Sha.Dispose()
Remove-Variable Encoded
Remove-Variable Plain
Remove-Variable HashBytes
Remove-Variable Hash
```

Evidence nên chụp dòng `length` và `sha256_prefix`, không chụp password gốc. Biến `$SecretHashBefore` được giữ lại để bước rotate có thể kiểm tra hash đã đổi mà không cần in plaintext.

## 15. Ghi lại trạng thái pod trước khi rotate

Chạy:

```powershell
$PodBefore = kubectl get pod -n demo -l app=api -o jsonpath="{range .items[*]}{.metadata.name}{' uid='}{.metadata.uid}{' restarts='}{.status.containerStatuses[0].restartCount}{' created='}{.metadata.creationTimestamp}{'\n'}{end}"
$PodBefore
```

Ý nghĩa:

- `name` và `uid` dùng để chứng minh pod không bị recreate.
- `restarts` dùng để chứng minh container không restart.
- `created` dùng để chứng minh AGE/creation time không đổi.

## 16. Rotate secret trên AWS

Phần này nên làm trên AWS Console để mentor thấy đúng thao tác rotate secret nguồn.

### Cách chính - rotate trên AWS Console

1. Mở AWS Console.
2. Chọn region `ap-southeast-1`.
3. Vào **Secrets Manager**.
4. Mở secret:

```text
w10/project02/db
```

5. Chọn tab hoặc khu vực **Secret value**.
6. Chọn **Retrieve secret value** để xác nhận secret đang tồn tại.
7. Chọn **Edit**.
8. Đổi value của key `password` sang giá trị version 2, ví dụ:

```text
lab4-v2-b2c3d4e5
```

9. Ngay trước hoặc ngay sau khi bấm **Save**, chạy lệnh này ở PowerShell để ghi mốc thời gian:

```powershell
$RotateStart = Get-Date
```

10. Bấm **Save** trên Console.

Evidence nên chụp:

- Secret `w10/project02/db`.
- Thời điểm vừa update secret.
- Không chụp password plaintext.

### Cách dự phòng - rotate bằng AWS CLI

Tạo password version 2:

```powershell
$DbPasswordV2 = "lab4-v2-$([guid]::NewGuid().ToString('N').Substring(0,8))"
$SecretJsonV2 = @{ password = $DbPasswordV2 } | ConvertTo-Json -Compress
```

Gửi version mới lên AWS Secrets Manager:

```powershell
$RotateStart = Get-Date

aws secretsmanager put-secret-value `
  --secret-id $AwsSecretName `
  --secret-string $SecretJsonV2 `
  --region $AwsRegion
```

Không chụp password value. Chụp command và metadata response là đủ.

## 17. Chờ K8s Secret sync dưới 60 giây

Chạy loop kiểm tra hash của Kubernetes Secret. Cách này không cần biết password plaintext, chỉ cần chứng minh fingerprint đã đổi so với `$SecretHashBefore`.

```powershell
do {
  Start-Sleep -Seconds 5
  $Encoded = kubectl get secret db-secret -n demo -o jsonpath="{.data.password}" 2>$null
  if ($Encoded) {
    $Current = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($Encoded))
    $Sha = [Security.Cryptography.SHA256]::Create()
    $HashBytes = $Sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($Current))
    $CurrentHash = (-join ($HashBytes | ForEach-Object { $_.ToString("x2") })).Substring(0,12)
    $Sha.Dispose()
  } else {
    $Current = ""
    $CurrentHash = ""
  }
  $Elapsed = [int]((Get-Date) - $RotateStart).TotalSeconds
  "elapsed=${Elapsed}s currentLength=$($Current.Length) sha256_prefix=$CurrentHash"
} while ($CurrentHash -eq $SecretHashBefore -and $Elapsed -lt 60)

if ($CurrentHash -ne $SecretHashBefore -and $CurrentHash -ne "") {
  "SYNCED_IN_${Elapsed}s"
} else {
  "NOT_SYNCED_WITHIN_60S"
}
```

Kỳ vọng:

```text
SYNCED_IN_<so_giay>s
```

Vì `refreshInterval` là `30s`, kết quả thường phải dưới 60 giây nếu AWS credentials, IAM permission và secret name đúng.

Sau khi kiểm xong, dọn biến tạm không cần dùng nữa. Nếu dùng CLI và có biến `$DbPasswordV1`, `$DbPasswordV2`, giữ lại tới bước kiểm tra repo để có thể scan chính xác giá trị runtime.

```powershell
Remove-Variable Current
Remove-Variable CurrentHash
Remove-Variable HashBytes -ErrorAction SilentlyContinue
Remove-Variable SecretJsonV2 -ErrorAction SilentlyContinue
```

## 18. Kiểm tra pod không restart

Chạy:

```powershell
$PodAfter = kubectl get pod -n demo -l app=api -o jsonpath="{range .items[*]}{.metadata.name}{' uid='}{.metadata.uid}{' restarts='}{.status.containerStatuses[0].restartCount}{' created='}{.metadata.creationTimestamp}{'\n'}{end}"
$PodAfter
```

So sánh:

```powershell
"BEFORE:"
$PodBefore
"AFTER:"
$PodAfter
```

Kỳ vọng:

- Pod name không đổi.
- UID không đổi.
- `created` không đổi.
- `restarts` không tăng.

Kiểm tra dạng bảng:

```powershell
kubectl get pods -n demo -l app=api
```

Nếu pod bị recreate hoặc restart count tăng, lab chưa đạt điều kiện “rotate secret không restart pod”.

## 19. Kiểm tra app đọc mounted secret

Mở terminal 1:

```powershell
kubectl port-forward -n demo svc/api 8080:80
```

Mở terminal 2:

```powershell
Invoke-RestMethod http://127.0.0.1:8080/db-password-status | ConvertTo-Json -Depth 5
```

Kỳ vọng:

```json
{
  "db_password": {
    "mounted": true,
    "path": "/var/run/secrets/w10-db/password",
    "length": 17,
    "sha256_prefix": "..."
  },
  "version": "..."
}
```

Endpoint này chỉ dùng hash để chứng minh app đọc được secret mới. Nó không expose password thật.

Lưu ý: Kubernetes Secret `db-secret` thường đổi trước. File mounted trong pod có thể cần thêm một chút thời gian do kubelet update volume. Không restart pod trong lúc chờ.

## 20. Kiểm tra repo không lộ credentials

Không dùng `grep -ri password` một cách máy móc vì project có nhiều key hợp lệ tên `password`. Thay vào đó kiểm access key format, secret access key assignment và chính giá trị password runtime nếu biến còn trong terminal.

```powershell
Get-ChildItem -Recurse -File | Where-Object {
  $_.FullName -notmatch "\\.git\\"
} | Select-String -Pattern "AKIA[0-9A-Z]{16}|ASIA[0-9A-Z]{16}|aws_secret_access_key\s*=|secret-access-key\s*[:=]\s*[A-Za-z0-9/+=]{20,}"
```

Nếu biến `$DbPasswordV1` hoặc `$DbPasswordV2` vẫn còn trong terminal, scan trực tiếp giá trị đó:

```powershell
$RuntimeSecrets = @()
if (Get-Variable DbPasswordV1 -ErrorAction SilentlyContinue) { $RuntimeSecrets += $DbPasswordV1 }
if (Get-Variable DbPasswordV2 -ErrorAction SilentlyContinue) { $RuntimeSecrets += $DbPasswordV2 }

if ($RuntimeSecrets.Count -gt 0) {
  Get-ChildItem -Recurse -File | Where-Object {
    $_.FullName -notmatch "\\.git\\"
  } | Select-String -SimpleMatch -Pattern $RuntimeSecrets
}
```

Kỳ vọng: không có secret thật xuất hiện trong repo.

Dọn biến runtime sau khi kiểm tra:

```powershell
Remove-Variable DbPasswordV1 -ErrorAction SilentlyContinue
Remove-Variable DbPasswordV2 -ErrorAction SilentlyContinue
Remove-Variable SecretJsonV1 -ErrorAction SilentlyContinue
```

Kiểm tra Git status:

```powershell
git status --short
```

Không được có file chứa credentials được stage/commit.

## 21. Nếu không có AWS

Đường chính của lab vẫn là AWS Secrets Manager. Nếu không có AWS, có thể mô phỏng pattern bằng provider fake của ESO hoặc Sealed Secrets, nhưng phần đó chỉ chứng minh được cơ chế sync secret, không chứng minh tích hợp AWS.

Khi dùng fallback, vẫn phải giữ 3 nguyên tắc:

- Secret source không commit plaintext vào Git.
- K8s Secret target tự cập nhật từ controller.
- Pod đọc secret qua mounted volume, không restart khi secret target đổi.

## 22. Tiêu chí đạt Lab 04

Lab đạt khi có đủ evidence:

| Evidence | Nội dung cần thấy |
|---|---|
| ArgoCD Apps | `external-secrets`, `eso-config`, `api` synced/healthy |
| ESO operator | Pod ESO Running, CRD `SecretStore` và `ExternalSecret` tồn tại |
| AWS credentials | Có Secret `aws-credentials` trong namespace `demo`, không in value |
| SecretStore/ExternalSecret | `Ready/Synced`, target là `db-secret` |
| Rotate AWS secret | `put-secret-value` thành công |
| Sync <60s | Loop in `SYNCED_IN_<so_giay>s` |
| Pod no restart | Pod name/UID/created/restartCount không đổi |
| App đọc secret | `/db-password-status` trả hash mới, không trả plaintext |
| Repo sạch | Không có AWS credentials/password thật trong Git |

## 23. Diễn giải evidence cho mentor

Lab này chứng minh secret rotation được triển khai theo mô hình production hơn so với việc commit hoặc tạo plaintext Kubernetes Secret thủ công. DB password được lưu trong AWS Secrets Manager, ESO operator đồng bộ về Kubernetes Secret `db-secret` theo `refreshInterval: 30s`. App không đọc password qua environment variable mà đọc từ mounted Secret volume, nên khi secret target đổi, pod không cần restart. Evidence quan trọng nhất là AWS value đổi, Kubernetes Secret cập nhật trong dưới 60 giây, còn pod name/UID/creationTimestamp/restartCount giữ nguyên.
