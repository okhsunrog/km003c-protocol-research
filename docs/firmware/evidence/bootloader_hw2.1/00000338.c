
undefined4 FUN_00000338(undefined4 *param_1,undefined4 *param_2)

{
  int *piVar1;
  int iVar2;
  uint uVar3;
  undefined4 uVar4;
  
  iVar2 = FUN_00000278(param_1,(uint)((int)param_2 - (int)param_1) >> 0xd);
  piVar1 = DAT_000003c8;
  if (iVar2 == 0) {
    *DAT_000003c8 = 0x123;
    *piVar1 = (int)&DAT_00003210;
    if (*piVar1 != 0) {
      uVar3 = piVar1[2];
      piVar1[2] = piVar1[2] & 0xfffeffff;
      piVar1[3] = piVar1[3] | 1;
      piVar1[3] = piVar1[3] & 0xffffff8fU | 0x40;
      uVar4 = DAT_000003cc;
      do {
        if (param_2 <= param_1) {
          uVar4 = 0;
          goto LAB_000003a0;
        }
        *param_1 = uVar4;
        do {
        } while (-1 < piVar1[4] << 0x17);
        param_1 = param_1 + 0x800;
      } while ((piVar1[4] & 1U) == 0);
      uVar4 = 1;
LAB_000003a0:
      piVar1[5] = 0x10;
      piVar1[3] = piVar1[3] & 0xffffff8f;
      piVar1[3] = piVar1[3] & 0xfffffffe;
      piVar1[2] = uVar3 & 0x10000 | piVar1[2] & 0xfffeffffU;
      *piVar1 = (int)&DAT_00003210;
      *piVar1 = (int)&DAT_00003210;
      return uVar4;
    }
  }
  return 1;
}

