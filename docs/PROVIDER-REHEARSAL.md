# From static findings to a provider-sandbox rehearsal

Everything in `examples/` and `benchmarks/corpus/` is hand-authored synthetic source. It is not an anonymized merchant log, an official provider fixture or a real integration. The project does not currently execute the provider checks below. They are the next manual validation layer, not completed evidence.

## What a webhook match does not prove

An `X-Signature` or event-name match only points to a file worth reading. It does **not** demonstrate correct signature verification, webhook identity, idempotency, correct entitlement state or absence of duplicate billing.

For a Lemon Squeezy source integration, consult:

- [Signing requests](https://docs.lemonsqueezy.com/help/webhooks/signing-requests): compare the HMAC-SHA256 over the original request body with `X-Signature`, following the official procedure. In your own sandbox, verify a legitimate request succeeds and a changed body/signature is rejected. Never put the signing secret in a fixture or report.
- [Webhook developer guide](https://docs.lemonsqueezy.com/guides/developer-guide/webhooks): delivery can be retried. Replay an authorized synthetic/test event and verify that side effects are not duplicated; test out-of-order delivery separately. A token search cannot verify either property.
- [Testing and going live](https://docs.lemonsqueezy.com/guides/developer-guide/testing-going-live): copied test products get different identifiers and URLs. Treat test/live mappings as separate records and verify that a successful sandbox test did not accidentally reference live resources.

These references are test-design anchors, not permission to call an account. Destination providers use their own event shapes, signing algorithms and test procedures. Recheck their current official guidance before implementing or testing them. No source-provider event should be relabeled as a verified destination event without a tested translation.

## Documentation-only negative control

The regression suite writes a synthetic `docs/README.md` containing checkout/webhook/license identifiers and verifies **zero findings**, one unsupported-file count and a manual-review verdict. Markdown is outside the default scan extensions. This prevents treating prose alone as discovered integration code, but it also means executable snippets embedded only in Markdown are not inventoried. Comments inside supported code files may still match; the benchmark preserves such a negative example.
