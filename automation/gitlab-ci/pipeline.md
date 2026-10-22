# GitLab CI pipeline

Reference pipeline. Adapt the stage list to the environment; keep the ordering and the separation between validation and production execution.

## Structure

```
.gitlab-ci.yml              # top-level, includes the shared template
ci/
├── templates/
│   ├── validate.yml       # stages 1-8 (validation only)
│   ├── deploy-staging.yml # stage 9-10
│   └── deploy-prod.yml    # stage 11-13
└── scripts/
    ├── drift-report.sh
    └── post-deploy-check.sh
```

## Top-level pipeline

```yaml
include:
  - project: platform/gitlab-ci
    ref: v1.0.0
    file: /ci/templates/validate.yml

stages:
  - source
  - lint
  - validate
  - policy
  - security
  - artifact
  - staging
  - integration
  - approval
  - production
  - postcheck
  - drift

variables:
  HELM_VERSION: "3.22.0"
  KUBECONFORM_VERSION: "v0.7.0"
  TRIVY_VERSION: "0.76.1"
  COSIGN_VERSION: "v3.1.4"
  KUBE_VERSION_TARGET: "v1.36.5"
  HARBOR: harbor.internal
  # Secrets are NEVER in this file. They are protected, masked CI/CD variables
  # or Vault-issued short-lived credentials.

default:
  interruptible: true
  tags: [docker, linux]
```

## Stage 1-2: source and lint

```yaml
source:validate-branch:
  stage: source
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
    - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH
  script:
    - |
      if [ "$CI_PIPELINE_SOURCE" = "merge_request_event" ]; then
        git fetch origin "$CI_MERGE_REQUEST_TARGET_BRANCH_NAME"
        git diff --name-only origin/"$CI_MERGE_REQUEST_TARGET_BRANCH_NAME"...HEAD
      fi

lint:yaml:
  stage: lint
  image: registry.internal/tools/yamllint:1.35.1
  script:
    - yamllint -c .yamllint.yml .

lint:markdown:
  stage: lint
  image: registry.internal/tools/markdownlint:0.42.0
  script:
    - markdownlint -c .markdownlint.yml --ignore node_modules .
```

## Stage 3: Ansible validation

```yaml
validate:ansible-syntax:
  stage: validate
  image: registry.internal/tools/ansible:2.19.2
  script:
    - ansible-playbook --syntax-check -i ansible/inventory/staging/hosts.ini ansible/site.yml
    - ansible-lint -p ansible/
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"

validate:ansible-idempotency:
  stage: validate
  script:
    # Dry run against the staging inventory; catches task-level errors without touching prod
    - ansible-playbook -i ansible/inventory/staging/hosts.ini ansible/site.yml --check --diff
```

## Stage 4: Helm and manifest validation

```yaml
validate:helm:
  stage: validate
  image: registry.internal/tools/helm:3.22.0
  script:
    - |
      for chart in $(find . -name Chart.yaml -printf '%h\n'); do
        helm lint "$chart"
        helm template "$(basename "$chart")" "$chart" > /dev/null
      done

validate:manifests:
  stage: validate
  image: registry.internal/tools/kubeconform:v0.7.0
  script:
    - |
      find . -name '*.yaml' -not -path './.git/*' | while read -r f; do
        kubeconform -strict -summary -kubernetes-version "${KUBE_VERSION_TARGET}" "$f"
      done
```

## Stage 5: policy validation

```yaml
validate:policy:
  stage: policy
  image: registry.internal/tools/conftest:0.56.0
  script:
    - conftest test --policy .conftest/ .

validate:kyverno:
  stage: policy
  image: registry.internal/tools/kyverno:v1.19.2
  script:
    - |
      for p in security/kyverno/policies/*.yaml; do
        kyverno apply "$p" --resource security/kyverno/test-resources/ --policy-report
      done
```

Gatekeeper constraints are validated with `opa test` against their Rego unit tests, which live next to the constraint.

## Stage 6: security scanning

```yaml
security:secret-scan:
  stage: security
  image: registry.internal/tools/gitleaks:v8.28.0
  script:
    - gitleaks detect --source . --redact --report-format json --report-path gitleaks.json
  artifacts:
    when: always
    paths: [gitleaks.json]

security:dependency-scan:
  stage: security
  image: registry.internal/tools/trivy:0.76.1
  script:
    - trivy fs --scanners vuln,secret,license --severity HIGH,CRITICAL --exit-code 1 .

security:image-scan:
  stage: security
  image: registry.internal/tools/trivy:0.76.1
  script:
    - trivy image --severity HIGH,CRITICAL --exit-code 1 "$CI_REGISTRY_IMAGE:$CI_COMMIT_SHA"
  rules:
    - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH

security:sbom:
  stage: security
  image: registry.internal/tools/syft:v1.55.0
  script:
    - syft "$CI_REGISTRY_IMAGE:$CI_COMMIT_SHA" -o cyclonedx-json > sbom.json
  artifacts:
    paths: [sbom.json]
```

The Trivy vulnerability database is refreshed monthly in the connected staging environment and mirrored into the internal registry (`harbor.internal/security/trivy-db`). The scan runs with `--skip-db-update` so it never reaches out.

## Stage 7: artifact verification

```yaml
artifact:verify-signature:
  stage: artifact
  image: registry.internal/tools/cosign:v3.1.4
  script:
    - cosign verify --key security/cosign/cosign.pub "$CI_REGISTRY_IMAGE@$CI_IMAGE_DIGEST"
  rules:
    - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH
```

## Stage 8: deployment to staging

```yaml
deploy:staging:
  stage: staging
  environment:
    name: staging
    url: https://argocd.internal/applications
  script:
    - ansible-playbook -i ansible/inventory/staging/hosts.ini ansible/site.yml
    - |
      # Argo CD syncs the app; the pipeline only triggers and waits
      kubectl -n argocd annotate application "$APP_NAME" \
        argocd.argoproj.io/refresh=hard --overwrite
```

## Stage 9: integration tests

```yaml
integration:tests:
  stage: integration
  script:
    - bash tests/acceptance/run.sh --suite integration --env staging
  artifacts:
    when: always
    paths: [tests/results/]
```

## Stage 10: approval gate

```yaml
approval:production:
  stage: approval
  when: manual
  allow_failure: false
  environment:
    name: production
  rules:
    - if: $CI_COMMIT_TAG
```

`when: manual` on a protected environment is the approval gate. The environment is protected, so only the named approvers can trigger it.

## Stage 11-12: production execution

```yaml
deploy:production:
  stage: production
  environment:
    name: production
  resource_group: production-cluster   # prevents concurrent production runs
  script:
    - ansible-playbook -i ansible/inventory/production/hosts.ini ansible/site.yml
    - kubectl -n argocd annotate application "$APP_NAME" argocd.argoproj.io/refresh=hard --overwrite

postcheck:health:
  stage: postcheck
  script:
    - bash tests/acceptance/run.sh --suite smoke --env production
```

## Stage 13: drift detection

```yaml
drift:detect:
  stage: drift
  rules:
    - if: $CI_PIPELINE_SOURCE == "schedule"
  script:
    - bash ci/scripts/drift-report.sh
  artifacts:
    when: always
    paths: [drift-report.json]
```

The drift job reports; it never fixes. Automatic remediation belongs to Argo CD (`selfHeal`) for declared state, and to Ansible for node state.

## Vault integration in CI

Preferred: OIDC/JWT authentication from the GitLab job to Vault.

```yaml
variables:
  VAULT_ADDR: "https://vault.internal:8200"
  VAULT_AUTH_PATH: "jwt"
  VAULT_ROLE: "gitlab-ci"

vault:login:
  script:
    - export VAULT_TOKEN="$(vault write -field=token auth/jwt/login role="$VAULT_ROLE" jwt="$CI_JOB_JWT_V2")"
    - vault kv get -field=password secret/ci/deploy
```

`CI_JOB_JWT_V2` is the GitLab-provided job token. The Vault JWT auth method must trust GitLab's JWKS, which requires an outbound fetch from Vault to GitLab — in an air-gapped environment, configure the JWKS URL as the internal GitLab URL, or upload the JWKS to Vault.

Fallback: AppRole with a short TTL, where the runner holds the role id and retrieves the secret id from Vault using a bootstrapping credential. This reintroduces a long-lived credential on the runner and is the weaker option — use it only if OIDC cannot be made to work.

## Rules

1. Validation jobs never have production credentials.
2. Production jobs run from a protected tag, never from a branch.
3. `resource_group` serializes production deployments.
4. Every job's output is scanned; `set -x` is off in jobs that handle secrets.
5. Artifacts never contain secrets.
6. The pipeline is the only path to production. Manual `kubectl` changes are drift and are reverted by `selfHeal`.
