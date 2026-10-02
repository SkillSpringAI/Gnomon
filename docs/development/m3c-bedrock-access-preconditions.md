# M3c Bedrock live characterization: access preconditions (Pass 1F)

**Status:** design characterization only. No additional Bedrock request, account
change, provider-attempt mutation, or production classification change was made.

The isolated live operation `02096537-288c-4cfd-97d9-2bf7d8b16f80` called
`Converse` with source region `ap-southeast-2` and
`modelId=au.anthropic.claude-opus-4-6-v1`. Bedrock returned a parsed
`AccessDeniedException`, HTTP 403, request ID
`0c40f2a0-1fd6-4e15-b1c7-9d89f8b3802e`, and zero SDK retries. Gnomon
recorded `PENDING -> DISPATCHED -> UNKNOWN` with
`provider_outcome_unknown`. This response proves the observed HTTP attempt
was rejected, but does not identify which access prerequisite failed. The
earlier operation `46c8bb57-6b53-4dbb-b3dd-24ba419b9322` lacked provider
diagnostics; its cause remains unknown. Neither operation should be replayed
or retroactively changed.

## Required for this configuration

- Keep `au.anthropic.claude-opus-4-6-v1` as the system-defined AU geographic
  inference profile passed as `modelId` to `bedrock-runtime.Converse` from
  Sydney. Its candidate destinations from Sydney are Sydney and Melbourne.
  It is neither the base model ID nor an application inference profile.
- The key must be a usable Amazon Bedrock API key for the Sydney endpoint.
  Short-term keys inherit their issuing principal's permissions, expire with
  the session or within 12 hours, and work only in their generation region.
  Long-term keys have an associated IAM user and policy. Effective policy must
  permit bearer-token use and `bedrock:InvokeModel` for this non-streaming
  `Converse` call.
- For the geographic profile, effective IAM permission must cover the profile
  in `ap-southeast-2` and Claude Opus 4.6 foundation-model resources in both
  `ap-southeast-2` and `ap-southeast-4`. Organizational SCPs must not block the
  originating call or either candidate destination, unless an appropriately
  scoped inference-profile exception permits routing.
- Anthropic first-time-use details must be submitted once for the account or
  organization. The account must meet the third-party model access
  prerequisites: applicable AWS Marketplace subscription permissions and a
  valid payment method. Automatic subscription can fail and later invocations
  can return `AccessDeniedException` until the prerequisite is corrected and
  access propagates.

These are requirements, **not diagnoses**. The observed 403 does not reveal
which one is missing. The first checks should be the key's actual principal,
`bedrock:InvokeModel` on the AU profile and both model regions, and any SCP
region deny. Anthropic onboarding, Marketplace subscription/payment, key
expiry/region, and a bearer-token-use deny are additional plausible causes.
No model or region substitution is justified.

## Safe checks before another inference

The existing opt-in harness can check configured region/model and whether a
non-placeholder bearer key is present without printing the key. It cannot
infer key type, issuing principal, effective IAM policy, SCPs, billing state,
or model subscription from key presence alone. Do not parse the key to guess
its type or print the local secret file.

With suitable **existing** permissions, an authenticated Amazon Bedrock
control-plane client could use `GetInferenceProfile` to inspect the profile's
ID, `ACTIVE` status, type, and destination model regions;
`GetFoundationModelAvailability` for the base model to inspect reported
agreement, authorization, entitlement, and region availability; and
`GetUseCaseForModelAccess` to check whether Anthropic use-case details exist.
Display only selected status/region fields, not complete responses or
use-case text. These read APIs may themselves be denied and none proves this
key can invoke this profile under all effective policies. The bearer key is
limited to Bedrock/Bedrock Runtime actions and cannot be assumed to provide
IAM, Organizations, Marketplace, or Billing diagnostics. Do not add separate
IAM credentials to Gnomon's bearer execution path for this review.

In the AWS Console, with a separately authorized account administrator:

1. Select **Sydney (`ap-southeast-2`)** in Amazon Bedrock. Under **API keys**,
   identify the existing key's type, expiration, generation region (for a
   short-term key), and issuing principal or associated IAM user. Do not copy
   or display the secret. Check that bearer-token use is not denied for that
   principal/key type.
2. In **Bedrock > Inference profiles**, inspect the AU Claude Opus 4.6 system
   profile and its destination regions. In **Model catalog**, inspect Claude
   Opus 4.6 and complete the Anthropic first-time-use form if prompted.
3. Inspect the key principal's effective policies for
   `bedrock:InvokeModel` on the AU profile in Sydney and the foundation model
   in Sydney and Melbourne. Have the organization administrator inspect SCP
   region restrictions or an inference-profile exception for both regions.
4. If model access is not available, check the account's applicable AWS
   Marketplace subscription permissions/status and valid payment method.
   Allow documented access propagation after correcting a prerequisite.

Change only the prerequisite actually found missing. An independent single
live generation with a **new** operation ID is justified after these checks;
it should use the same isolated bearer harness and observation wrapper.

**Subsequent Pass 1G evidence:** That new generation succeeded after the
local bearer-key dotenv value was corrected to the plain long-term key value.
The Pass 1F cause ranking above was a pre-success diagnostic checklist, not
a finding that an IAM, SCP, subscription, or billing prerequisite was absent.
The success does not prove the exact cause of either earlier failure. See
the [successful baseline record](m3c-bedrock-successful-baseline.md).

## Later M3c design constraints recorded in Pass 1F

Pass 3A subsequently implemented only the exact non-retried boto3
`AccessDeniedException`/integer 403/integer zero-retry rule at
`0bcbc479876903d2382ebbedda50339c5918f1d5`. The bullets below preserve
the Pass 1F design constraints; see the
[Pass 3A closure](m3c-pass3a-provider-rejection-closure.md) for shipped behavior.

- An explicit non-retried service rejection is not the same as an unknown
  provider outcome. Keep `UNKNOWN` for genuinely ambiguous execution.
- A future mapping of proven rejection to existing `FAILED` with a fixed
  reason such as `provider_request_rejected` must account for SDK retry
  history, including uncertain prior HTTP attempts.
- `FAILED` releases report-draft budget while `UNKNOWN` retains it. Test that
  consequence before reclassification. Existing `FAILED` also covers local
  validation failure, so it must not be described as proof of zero provider
  work or charges.
- Raw AWS error messages, credential material, prompts, and arbitrary
  provider responses must not become durable diagnostic data. Keep any future
  diagnostic metadata typed and allowlisted.
- The optional `boto3>=1.35` floor does not guarantee Bedrock bearer support.
  boto3/botocore 1.39.0 is the candidate floor from the tagged Bedrock Runtime
  auth model; verify construction at that floor separately before packaging
  changes.

## References

- [Claude Opus 4.6 model card](https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-anthropic-claude-opus-4-6.html)
- [Geographic cross-Region inference permissions](https://docs.aws.amazon.com/bedrock/latest/userguide/geographic-cross-region-inference.html)
- [Converse permission](https://docs.aws.amazon.com/cli/latest/reference/bedrock-runtime/converse.html)
- [Bedrock API key types and region restriction](https://docs.aws.amazon.com/bedrock/latest/userguide/api-keys-reference.html)
- [API-key bearer-use policy](https://docs.aws.amazon.com/bedrock/latest/userguide/api-keys-permissions.html)
- [Model-access prerequisites](https://docs.aws.amazon.com/bedrock/latest/userguide/model-access.html)
- [GetInferenceProfile](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_GetInferenceProfile.html)
- [GetFoundationModelAvailability](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_GetFoundationModelAvailability.html)
- [GetUseCaseForModelAccess](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_GetUseCaseForModelAccess.html)
