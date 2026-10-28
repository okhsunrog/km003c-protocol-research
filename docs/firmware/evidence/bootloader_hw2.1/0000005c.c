
void vector_4(void)

{
  *DAT_000000a0 = 0x77;
  *DAT_000000a4 = 0x77;
  *DAT_000000a8 = &DAT_00001100;
  *DAT_000000a0 = 0x76;
  *DAT_000000a4 = 0x76;
  (*DAT_000000ac)();
                    /* WARNING: Could not recover jumptable at 0x0000008a. Too many branches */
                    /* WARNING: Treating indirect jump as call */
  (*DAT_000000b0)();
  return;
}

