
undefined4 flash_program_from_ram(int *param_1,int *param_2,int *param_3)

{
  undefined4 *puVar1;
  undefined4 uVar2;
  uint uVar3;
  int *piVar4;
  
  puVar1 = DAT_1fff808c;
  uVar2 = 1;
  if (*param_1 == -1) {
    *DAT_1fff808c = 0x123;
    *puVar1 = &DAT_00003210;
    uVar3 = puVar1[2];
    puVar1[2] = puVar1[2] & 0xfffeffff;
    puVar1[3] = puVar1[3] | 1;
    puVar1[3] = puVar1[3] & 0xffffff8f | 0x30;
    puVar1[5] = 0x20;
    puVar1[5] = 1;
    piVar4 = param_1;
    for (; param_1 < param_2; param_1 = param_1 + 1) {
      *piVar4 = *param_3;
      do {
      } while (-1 < (int)(puVar1[4] << 0x1b));
      puVar1[5] = 0x10;
      piVar4 = piVar4 + 1;
      param_3 = param_3 + 1;
    }
    puVar1[3] = puVar1[3] & 0xffffff8f;
    do {
    } while (-1 < (int)(puVar1[4] << 0x17));
    uVar2 = 0;
    puVar1[3] = puVar1[3] & 0xfffffffe;
    puVar1[2] = uVar3 & 0x10000 | puVar1[2] & 0xfffeffff;
    *puVar1 = &DAT_00003210;
    *puVar1 = &DAT_00003210;
  }
  return uVar2;
}

