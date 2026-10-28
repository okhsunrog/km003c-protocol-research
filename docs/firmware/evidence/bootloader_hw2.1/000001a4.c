
undefined1 FUN_000001a4(uint param_1,uint param_2,uint param_3,uint param_4)

{
  uint *puVar1;
  undefined1 uVar2;
  uint uVar3;
  uint unaff_r8;
  uint unaff_r9;
  int unaff_r10;
  
  uVar2 = 4;
  if (((((param_2 & 0xf) == 0) && (param_1 != 0)) && (param_2 != 0)) &&
     ((param_3 != 0 && (param_4 != 0)))) {
    if (((param_1 & 3) == 0) && (((param_3 & 3) == 0 && ((param_4 & 3) == 0)))) {
      FUN_00000258(param_3);
      puVar1 = DAT_00000228;
      uVar2 = FUN_000006a4();
      for (; param_2 != 0; param_2 = param_2 - 0x10) {
        *puVar1 = unaff_r8;
        FUN_00000240(param_1 + unaff_r10 * 0x10);
        puVar1[1] = unaff_r8;
        *puVar1 = unaff_r9;
        uVar3 = unaff_r8;
        while( true ) {
          if (0x36 < uVar3 >> 3) {
            uVar2 = 9;
            goto LAB_00000222;
          }
          if (*puVar1 == 0) break;
          uVar3 = uVar3 + 1;
        }
        FUN_0000022c(unaff_r10 * 0x10 + param_4);
        unaff_r10 = unaff_r10 + 1;
        uVar2 = 0;
      }
LAB_00000222:
      *puVar1 = 0;
    }
    else {
      uVar2 = 4;
    }
  }
  return uVar2;
}

