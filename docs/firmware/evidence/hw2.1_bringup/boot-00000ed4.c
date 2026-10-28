
/* WARNING: Globals starting with '_' overlap smaller symbols at the same address */

void FUN_00000ed4(uint param_1,byte *param_2,short param_3)

{
  uint *puVar1;
  undefined4 *puVar2;
  undefined2 *puVar3;
  
  puVar1 = DAT_00000fa8;
  do {
  } while ((DAT_00000fa8[1] & 1) != 0);
  FUN_000003fa();
  puVar2 = DAT_00000fb0;
  do {
  } while (*DAT_00000fac == 0);
  *DAT_00000fb0 = 0;
  puVar3 = DAT_00000fb4;
  *DAT_00000fb4 = (short)DAT_00000fb8;
  FUN_00000724();
  _DAT_9c000000 = _DAT_9c000000 & 0xffc0fff8 | 0x20000;
  *puVar1 = *puVar1 & 0xffffffbf;
  FUN_000003fa();
  _DAT_9c000000 = _DAT_9c000000 | 0x20;
  puVar1[2] = param_1;
  do {
  } while ((puVar1[1] & 1) != 0);
  FUN_000003fa();
  if (param_2 != (byte *)0x0) {
    *puVar1 = *puVar1 | 0x40;
    FUN_000003fa();
    for (; param_3 != 0; param_3 = param_3 + -1) {
      puVar1[2] = (uint)*param_2;
      param_2 = param_2 + 1;
    }
    do {
    } while ((puVar1[1] & 1) != 0);
  }
  _DAT_9c000000 = _DAT_9c000000 & 0xffffffdf;
  *puVar2 = 1;
  *puVar3 = 0xa501;
  puVar3[0x25] = puVar3[0x25] & 0xffc7 | 7;
  *puVar3 = 0xa500;
  _DAT_9c000000 = _DAT_9c000000 & 0xffc0ffff | 7;
  return;
}

