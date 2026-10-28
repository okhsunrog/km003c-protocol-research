
undefined1 FUN_000000fc(void)

{
  undefined4 *puVar1;
  uint *puVar2;
  undefined1 uVar3;
  uint uVar4;
  uint extraout_r2;
  uint extraout_r3;
  undefined4 *puVar5;
  int iVar6;
  uint unaff_r8;
  uint unaff_r9;
  int unaff_r10;
  ulonglong uVar7;
  
  puVar1 = puRam0000011c;
  for (puVar5 = puRam00000118; puVar5 < puVar1; puVar5 = puVar5 + 4) {
    (*(code *)puVar5[3])(*puVar5,puVar5[1],puVar5[2]);
  }
  uVar7 = thunk_FUN_000019d0();
  iVar6 = (int)(uVar7 >> 0x20);
  uVar3 = 4;
  if (((((uVar7 & 0xf00000000) == 0) && ((int)uVar7 != 0)) && (iVar6 != 0)) &&
     ((extraout_r2 != 0 && (extraout_r3 != 0)))) {
    if (((uVar7 & 3) == 0) && (((extraout_r2 & 3) == 0 && ((extraout_r3 & 3) == 0)))) {
      FUN_00000258(extraout_r2);
      puVar2 = DAT_00000228;
      uVar3 = FUN_000006a4();
      for (; iVar6 != 0; iVar6 = iVar6 + -0x10) {
        *puVar2 = unaff_r8;
        FUN_00000240((int)uVar7 + unaff_r10 * 0x10);
        puVar2[1] = unaff_r9;
        *puVar2 = unaff_r9;
        uVar4 = unaff_r8;
        while( true ) {
          if (0x90 < uVar4 >> 2) {
            uVar3 = 9;
            goto LAB_0000019e;
          }
          if (*puVar2 == 0) break;
          uVar4 = uVar4 + 1;
        }
        FUN_0000022c(unaff_r10 * 0x10 + extraout_r3);
        unaff_r10 = unaff_r10 + 1;
        uVar3 = 0;
      }
LAB_0000019e:
      *puVar2 = 0;
    }
    else {
      uVar3 = 4;
    }
  }
  return uVar3;
}

