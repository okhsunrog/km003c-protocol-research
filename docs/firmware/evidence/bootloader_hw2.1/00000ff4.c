
int FUN_00000ff4(byte param_1,int param_2,uint param_3,int param_4,undefined4 param_5)

{
  undefined1 uVar1;
  byte *pbVar2;
  byte *pbVar3;
  undefined4 uVar4;
  int *piVar5;
  undefined4 *puVar6;
  int iVar7;
  uint uVar8;
  int iVar9;
  undefined4 unaff_r4;
  undefined4 unaff_r5;
  undefined4 unaff_r6;
  undefined4 unaff_lr;
  
  pbVar2 = DAT_000010c0;
  uVar8 = param_4 + 1U;
  if (((param_4 + 1U != 0) || (uVar8 = DAT_000010bc, DAT_000010bc < param_3)) ||
     (uVar8 = DAT_000010bc + param_2, 0x98000000 < uVar8)) {
    iVar7 = FUN_00000fc4(6,uVar8,param_3,param_4);
    return iVar7;
  }
  pbVar2[0xc] = 0xff;
  pbVar2[0xd] = 0xff;
  pbVar2[0xe] = 0xff;
  pbVar2[0xf] = 0xff;
  *(undefined4 *)(pbVar2 + 0x10) = param_5;
  *pbVar2 = param_1 | 0x80;
  *(int *)(pbVar2 + 4) = param_2;
  *(uint *)(pbVar2 + 8) = param_3;
  pbVar2[2] = 1;
  iVar7 = DAT_000012a4;
  pbVar2[3] = 1;
  iVar9 = *(int *)(DAT_000012a4 + 8);
  pbVar2[1] = (byte)iVar9;
  *(int *)(iVar7 + 8) = iVar9 + 1;
  iVar7 = FUN_00000738(pbVar2,0x14);
  if (param_3 != 0) {
    FUN_000002b0(10);
    uVar4 = DAT_000010c4;
    pbVar2 = DAT_000010c0;
    for (uVar8 = param_3 / 0xff0; pbVar3 = DAT_000010c0, uVar8 != 0; uVar8 = uVar8 - 1) {
      FUN_000001a4(param_2,0xff0,uVar4,pbVar2);
      FUN_00000738(pbVar2,0xff0);
      param_2 = param_2 + 0xff0;
    }
    iVar7 = (param_3 / 0xff0) * 0xff;
    uVar8 = param_3 % 0xff0;
    if (uVar8 != 0) {
      if ((param_3 & 0xf) != 0) {
        uVar8 = (uVar8 & 0xfffffff0) + 0x10;
      }
      FUN_000001a4(param_2,uVar8,DAT_000010c4,DAT_000010c0);
      puVar6 = DAT_00001bc4;
      piVar5 = DAT_00001bc0;
      iVar9 = 1000;
      uVar1 = *(undefined1 *)(DAT_00001bc4 + 2);
      *DAT_00001bc0 = 0;
      iVar7 = FUN_00002320(*puVar6,uVar1,pbVar3,uVar8,0x80,param_4,unaff_r4,unaff_r5,unaff_r6,
                           unaff_lr);
      if (iVar7 != -1) {
        while ((iVar9 != 0 && (*piVar5 == 0))) {
          FUN_000002b0(1);
          iVar9 = iVar9 + -1;
        }
        iVar7 = 0;
        if (iVar9 == 0) {
          iVar7 = -7;
        }
        return iVar7;
      }
      return -1;
    }
  }
  return iVar7;
}

