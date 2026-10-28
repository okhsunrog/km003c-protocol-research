
void FUN_00000fcc(undefined1 param_1,short param_2,undefined4 param_3)

{
  int iVar1;
  int iVar2;
  undefined4 local_c;
  
  iVar1 = DAT_000012a4;
  local_c = (uint)(ushort)(param_2 << 6) << 0x10;
  local_c = CONCAT31(local_c._1_3_,param_1) & 0xffffff7f;
  iVar2 = *(int *)(DAT_000012a4 + 8);
  local_c._0_2_ = CONCAT11((char)iVar2,(undefined1)local_c);
  *(int *)(DAT_000012a4 + 8) = iVar2 + 1;
  FUN_00000738(&local_c,4,iVar1,iVar2,param_3);
  return;
}

