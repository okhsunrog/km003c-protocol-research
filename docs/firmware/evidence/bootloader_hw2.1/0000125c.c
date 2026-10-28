
undefined4 FUN_0000125c(undefined4 *param_1,uint param_2)

{
  undefined4 *puVar1;
  uint uVar2;
  undefined4 uVar3;
  
  puVar1 = DAT_0000128c;
  *DAT_0000128c = 0xffffffff;
  for (uVar2 = param_2 >> 2; uVar2 != 0; uVar2 = uVar2 - 1) {
    uVar3 = *param_1;
    param_1 = param_1 + 1;
    puVar1[0x1f] = uVar3;
  }
  for (uVar2 = 0; (param_2 & 3) != uVar2; uVar2 = uVar2 + 1) {
    *(undefined1 *)(puVar1 + 0x1f) = *(undefined1 *)((int)param_1 + uVar2);
  }
  return *puVar1;
}

