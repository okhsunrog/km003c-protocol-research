
/* WARNING: Globals starting with '_' overlap smaller symbols at the same address */

void vector_c(void)

{
  int iVar1;
  
  for (iVar1 = 0; iVar1 != 0x2a; iVar1 = iVar1 + 1) {
    _DAT_0000047c[1] = (uint)*(byte *)(iVar1 + 0x480);
    do {
    } while (-1 < *_DAT_0000047c << 0x19);
  }
  do {
                    /* WARNING: Do nothing block with infinite loop */
  } while( true );
}

