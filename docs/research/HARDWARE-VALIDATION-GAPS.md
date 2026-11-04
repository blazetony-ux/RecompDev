# Hardware capture and validation gaps

**Status:** Open engineering risks confirmed by v0.4.3 review of owner-supplied evidence.

## Video and assets

VDP writes and final-frame PNGs exist, but the inspected run lacks per-frame framebuffer images and raw VRAM/CRAM hardware buffers. The SMS tile decoder in `modular/asset_decoders/sms.py` can export authentic tiles only when input buffers are available. Do not infer original sprite/tile data from a screenshot or frame hash.

## Audio

All seven captured WAV files in the reviewed Shinobi run were silent even though the guest issued 11 PSG writes. The precise cause is unestablished. Before changing synthesis, capture timestamped PSG writes, latch/channel state, volume and sample generation at the same frame/cycle coordinates.

## Timing and IRQ

120 VBlank events with 34 accepted maskable IRQs is not automatically a bug: the guest may disable interrupts. Need independently aligned CPU cycles, interrupt enable state, status reads and frame boundaries before concluding parity or defect.

## Reference qualification

Capture a reference trace from an independent emulator/hardware for the same ROM hash, region, input script, reset state and frame alignment. Compare actual frames and device state; avoid pixel comparisons to unrelated screenshots. The offline reviewer supports optional reference images and timing sessions but does not itself provide independent truth.
