
/* WARNING: Globals starting with '_' overlap smaller symbols at the same address */

void FUN_00043610(int param_1)

{
  undefined4 uVar1;
  
  if (param_1 == 3) {
    _DAT_42a70298 = 1;
    uVar1 = 2;
  }
  else {
    if (param_1 == 2) {
      FUN_0001a9c8(8,2);
      return;
    }
    if (param_1 == 1) {
      _DAT_42a70298 = 1;
      return;
    }
    _DAT_42a70298 = 0;
    uVar1 = 0;
  }
  FUN_0001a9c8(8,uVar1);
  return;
}

