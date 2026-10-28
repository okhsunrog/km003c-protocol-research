
/* WARNING: Globals starting with '_' overlap smaller symbols at the same address */

void FUN_000019d0(void)

{
  bool bVar1;
  undefined2 *puVar2;
  undefined4 *puVar3;
  int *piVar4;
  undefined2 *puVar5;
  undefined4 *puVar6;
  int iVar7;
  code *pcVar8;
  undefined4 uVar9;
  
  FUN_00000784(0x1c,0);
  puVar2 = DAT_00001b24;
  *DAT_00001b24 = (short)DAT_00001b28;
  puVar3 = DAT_00001b2c;
  *DAT_00001b2c = 1;
  *puVar2 = 0xa500;
  pcVar8 = _DAT_00004004;
  piVar4 = DAT_00001b30;
  if (puVar3[2] != 0) {
    if ((((*DAT_00001b30 != DAT_00001b34) && (_DAT_00004420 == 0x4000)) &&
        (_DAT_00004428 <= DAT_00001b38)) &&
       ((DAT_00001b3c < _DAT_00004000 && (_DAT_00004000 < DAT_00001b3c + 0x28000)))) {
      *DAT_00001b40 = 0x4000;
      bVar1 = (bool)isCurrentModePrivileged();
      if (bVar1) {
        setMainStackPointer(_DAT_00004000);
      }
      (*pcVar8)(pcVar8,_DAT_00004000);
    }
    *piVar4 = 0;
  }
  uVar9 = DAT_00001b4c;
  puVar3 = DAT_00001b48;
  puVar5 = DAT_00001b44;
  *DAT_00001b44 = 0xa501;
  *puVar3 = uVar9;
  puVar3[0x38] = DAT_00001b50;
  FUN_00000328();
  puVar6 = DAT_00001b54;
  DAT_00001b54[2] = DAT_00001b54[2] & 0xffffff0f | 0x50;
  *puVar6 = &DAT_00003210;
  *puVar6 = &DAT_00003210;
  *(byte *)(puVar3 + 1) = *(byte *)(puVar3 + 1) & 0xf | 0xa0;
  *(byte *)(puVar5 + 0x11) = *(byte *)(puVar5 + 0x11) | 1;
  *(byte *)((int)puVar5 + 0x2d) = *(byte *)((int)puVar5 + 0x2d) | 0x80;
  *(byte *)((int)puVar3 + 10) = *(byte *)((int)puVar3 + 10) & 0xfe;
  puVar6 = DAT_00001b6c;
  piVar4 = DAT_00001b64;
  uVar9 = DAT_00001b5c;
  do {
  } while (-1 < (int)((uint)*(byte *)(puVar3 + 7) << 0x1a));
  *(byte *)((int)puVar3 + 6) = (*(byte *)((int)puVar3 + 6) & 0xf8) + 5;
  puVar3 = DAT_00001b58;
  *puVar5 = 0xa500;
  *puVar3 = uVar9;
  iVar7 = DAT_00001b60;
  *piVar4 = DAT_00001b60 + 1;
  puVar3 = DAT_00001b68;
  *DAT_00001b68 = 0;
  puVar3[3] = 0;
  *puVar6 = 0x1e;
  *piVar4 = iVar7;
  puVar6 = DAT_00001b70;
  puVar3[0x1d] = 0;
  *puVar2 = 0xa501;
  *puVar6 = 0;
  puVar3 = DAT_00001b74;
  DAT_00001b74[0x10] = 1;
  *puVar3 = 1;
  FUN_0000060c();
  FUN_00001134();
  FUN_00000b00();
  FUN_00000d10();
  FUN_00000c44(0,0,0xf0,0xf0,0);
  FUN_000011be(0x1e);
  FUN_00001290();
  *puVar2 = 0xa500;
  uVar9 = FUN_00001d04(0);
  FUN_000024c0(uVar9,DAT_00001b78);
  FUN_00001d5c(uVar9);
  do {
    FUN_000012a8();
  } while( true );
}

