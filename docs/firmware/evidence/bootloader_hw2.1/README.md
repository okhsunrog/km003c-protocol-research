# Bootloader Evidence

Selected analysis artifacts for
[Bootloader Logic](../../bootloader.md). The underlying
[binary](../../../../fw/bootloader_hw2.1_00000004-00003fff.bin) is a partial
acquisition mapped at `0x4`, not a complete flash backup.

| Artifact | Meaning |
|----------|---------|
| `acquisition.json` | Original dump extent, hash and repeat-read checks; device serial omitted on import |
| `import_provenance.json` | Source repository revision and SHA-256 of the copied updater documentation |
| `listing.asm` | Ghidra's exported instructions, including the statically mapped RAM writer |
| Address-named `.c` files | Selected Ghidra decompilations; inferred types/globals, not original firmware source |
| `AnalyzeBoot.java`, `MapBootData.java` | Original headless export and flash-backed RAM mapping scripts |
| `historical_update_capture.json` | Earlier master-dataset update analysis; its unresolved questions are historical |
| `metadata_patch_check.json` | Static commit prediction and the previous narrow live readback; later full readback supersedes its earlier limitation |
| `hardware_capture_summary.json` | Frame numbers/timings from the existing upgrade and downgrade captures |
| `hardware_cycle_summary.json` | Existing full-cycle and independent readback results; serial omitted on import |
| `verification.json` | This pass's binary/instruction/branch checks, historical capture recheck and offline comparison of old hardware readbacks |
| `SHA256SUMS` | Integrity manifest for copied evidence files and the partial binary |

The original acquisition/analysis took place on 2026-10-28, using Ghidra 12.1.4
with language `ARM:LE:32:Cortex:default`, raw load address `0x4`, Thumb mode,
and valid exception-vector seeds. The source analysis exported 118 functions;
this directory includes the selected functions relevant to the boot/update path.
The instruction listing is the full export, not only those selected functions.

The static RAM mapping copies original flash bytes at `0x2ab0`, length `0x140`,
to `0x1fff8000` according to the startup initialization table. It is not an
acquisition of live RAM. `MapBootData.java` calls `AnalyzeBoot.java`, which
exports its results into the directory passed as its first script argument.
Reproduction needs a Ghidra raw import at the real base address; loading this
binary at zero shifts every instruction and literal-pool address by four bytes.

Original diagnostic directories under
`/home/okhsunrog/tmp_zfs/codex_tmp/` are:

- `km003c-bootloader-dump-2026-10-28/`: repeated acquisitions.
- `km003c-bootloader-analysis-2026-10-28/`: original Ghidra project, logs and exports.
- `km003c-update-analysis-2026-10-28/`: historical master-dataset analysis.
- `km003c-flash-cycle-2026-10-28/`: raw upgrade/downgrade pcapng files, backups,
  verbose traces and final readbacks. Relative package paths in the copied
  cycle summary refer to this original diagnostic layout, not this directory.

No original serial-bearing device-info logs, credentials, large raw captures,
or application backups were copied here. The firmware's embedded protocol key
is present in the binary and already documented in the protocol research.

From the repository root, verify the manifest with:

```bash
sha256sum --check docs/firmware/evidence/bootloader_hw2.1/SHA256SUMS
```
