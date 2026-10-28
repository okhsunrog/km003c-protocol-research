
undefined4 FUN_00000278(uint param_1,int param_2)

{
  uint uVar1;
  undefined4 uVar2;
  
  if ((param_1 & 3) != 0) {
    return 2;
  }
  if ((0x1fff < param_1) && (uVar1 = param_1 + param_2 * 0x2000, uVar1 >> 0x13 == 0)) {
    uVar2 = 0;
    if (0x4000 < uVar1) {
      uVar2 = 3;
    }
    if (param_1 != 0x2000) {
      uVar2 = 0;
    }
    return uVar2;
  }
  return 3;
}

