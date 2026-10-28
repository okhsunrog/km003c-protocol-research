
undefined4 FUN_00000738(undefined4 param_1,undefined2 param_2,undefined4 param_3,undefined4 param_4)

{
  undefined1 uVar1;
  int *piVar2;
  undefined4 *puVar3;
  int iVar4;
  undefined4 uVar5;
  int iVar6;
  
  puVar3 = DAT_00001bc4;
  piVar2 = DAT_00001bc0;
  iVar6 = 1000;
  uVar1 = *(undefined1 *)(DAT_00001bc4 + 2);
  *DAT_00001bc0 = 0;
  iVar4 = FUN_00002320(*puVar3,uVar1,param_1,param_2,0x80,param_4);
  if (iVar4 != -1) {
    while ((iVar6 != 0 && (*piVar2 == 0))) {
      FUN_000002b0(1);
      iVar6 = iVar6 + -1;
    }
    uVar5 = 0;
    if (iVar6 == 0) {
      uVar5 = 0xfffffff9;
    }
    return uVar5;
  }
  return 0xffffffff;
}

