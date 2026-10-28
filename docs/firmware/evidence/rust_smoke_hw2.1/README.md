# Rust smoke test on HW2.1

The test flashed and executed a 1672-byte Rust application at `0x4000`,
verified its retention marker and automatic return to native DFU, then restored
the exact original 1.9.9 application. Full original readback passed. Loader
bytes `[4, 0x4000)` were compared before and after both operations and matched.
The unreadable initial four bytes are not included in that comparison.

- `rust-smoke.bin`: uncommitted application image.
- `rust-smoke.mencrypt`: validated package sent through the native loader.
- `smoke-readback.bin`: installed image, including the loader's metadata patch.
- `marker-before.bin`, `marker-after.bin`: retention words at `0x200f0fc0`.
- `hardware_test.rs`: exact test source using the local km003c Rust library;
  machine-local paths need adaptation before reuse. It performs flash writes.
- `smoke-run.log`, `restore-result.txt`: execution and restoration results.
- `verification.json`: hashes, dependency revisions and checks performed.

The standalone firmware project is maintained separately from this research
documentation. The archived binary and test source describe this specific run.
The device was left running stock 1.9.9, not the experimental image.
This verifies a normal update/run/restore cycle, not interrupted-power or
deliberately lost-ACK recovery. There is no custom USB driver in this image.

`SHA256SUMS` covers the files in this directory. Check it from repository root
with `sha256sum --check docs/firmware/evidence/rust_smoke_hw2.1/SHA256SUMS`.
