
undefined4 FUN_00001618(undefined4 *param_1,int *param_2,int param_3)

{
  int *piVar1;
  undefined4 uVar2;
  undefined4 uVar3;
  int iVar4;
  
  piVar1 = DAT_0000164c;
  while ((uVar2 = DAT_00001650, iVar4 = *piVar1, param_3 != 0 && (iVar4 == 0))) {
    FUN_000002b0(1);
    param_3 = param_3 + -1;
  }
  uVar3 = 0xfffffff9;
  if (param_3 != 0) {
    uVar3 = 0;
  }
  if ((iVar4 != 0) && (param_3 != 0)) {
    *param_2 = iVar4;
    *param_1 = uVar2;
    uVar3 = 0;
    *piVar1 = 0;
  }
  return uVar3;
}

