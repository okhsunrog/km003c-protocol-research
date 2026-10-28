
void FUN_000012a8(void)

{
  char cVar1;
  undefined2 uVar2;
  char *pcVar3;
  int *piVar4;
  uint *puVar5;
  int iVar6;
  undefined4 uVar7;
  byte bVar8;
  undefined4 uVar9;
  uint uVar10;
  uint uVar11;
  int extraout_r2;
  uint uVar12;
  int extraout_r3;
  uint uVar13;
  uint *puVar14;
  undefined8 uVar15;
  int local_6c;
  uint *local_68;
  uint local_64;
  uint local_60;
  undefined4 local_5c;
  int local_58;
  
  pcVar3 = DAT_000015e0;
  piVar4 = DAT_000015dc;
  iVar6 = *DAT_000015dc;
  bVar8 = *(byte *)(iVar6 + 0x9c);
  if ((bVar8 & 1) == 0) {
    uVar7 = 0x8430;
LAB_000012c8:
    uVar9 = 500;
LAB_000012cc:
    FUN_000017de(uVar7,uVar9);
    return;
  }
  if (-1 < (int)((uint)bVar8 << 0x1e)) {
    uVar7 = 0xf800;
    goto LAB_000012c8;
  }
  if (*DAT_0000164c == 0) {
    if ((int)((uint)bVar8 << 0x1d) < 0) {
      uVar10 = *(uint *)(DAT_000015e0 + 4);
      *(uint *)(DAT_000015e0 + 4) = uVar10 + 1;
      if (uVar10 < DAT_000015f8) {
        return;
      }
      *(byte *)(iVar6 + 0x9c) = bVar8 & 0xfb;
      return;
    }
    uVar7 = 0x7e0;
    goto LAB_000012c8;
  }
  *DAT_0000164c = 0;
  pcVar3[4] = '\0';
  puVar5 = DAT_000015e8;
  pcVar3[5] = '\0';
  pcVar3[6] = '\0';
  pcVar3[7] = '\0';
  uVar10 = *DAT_00001650;
  uVar13 = uVar10 & 0x7f;
  if ((bVar8 & 4) == 0 && uVar13 == 2) {
    *(byte *)(iVar6 + 0x9c) = bVar8 | 4;
    FUN_00000fc4(5);
    uVar9 = 5;
    pcVar3[8] = '\0';
    pcVar3[9] = '\0';
    pcVar3[10] = '\0';
    pcVar3[0xb] = '\0';
    uVar7 = 0x7e0;
    goto LAB_000012cc;
  }
  if ((bVar8 & 4) == 0) {
    uVar7 = 6;
    uVar10 = 4;
    goto LAB_0000136a;
  }
  local_68 = DAT_00001650 + 1;
  if ((int)(uVar10 << 0x18) < 0) {
    uVar7 = 6;
    uVar10 = 0;
    goto LAB_0000136a;
  }
  puVar14 = local_68;
  if (((int)(uVar10 << 0xf) < 0) &&
     (iVar6 = FUN_00000120(local_68,uVar10 >> 0x14 & 0xfffffffc,DAT_000015e4,DAT_000015e8),
     puVar14 = puVar5, iVar6 != 0)) {
    uVar7 = 6;
LAB_0000134a:
    uVar10 = 1;
    goto LAB_0000136a;
  }
  switch(uVar13) {
  case 0x40:
    uVar13 = 0;
    uVar11 = 0;
    uVar12 = 0xffffffff;
    uVar10 = 0;
    uVar7 = 0x40;
    goto LAB_000014fa;
  case 0x41:
  case 0x45:
  case 0x48:
  case 0x49:
switchD_00001378_caseD_41:
    uVar7 = 6;
    uVar10 = 3;
    goto LAB_0000136a;
  case 0x42:
    FUN_000000b4(&local_64,puVar14,0x40);
    uVar11 = local_60;
    uVar13 = local_64;
    uVar10 = FUN_00000338(local_64,local_60);
    if (uVar10 == 0) {
      FUN_00000fc4(5);
      FUN_00000c44(100,0xdd,0x8c,0x13,0x8430);
      FUN_00000c44(0x66,0xdf,0x88,0xf,0);
      puVar14 = DAT_00001650;
      puVar5 = DAT_000015e8;
      uVar7 = DAT_000015e4;
      while( true ) {
        if (uVar11 <= uVar13) {
          iVar6 = FUN_0000125c(local_64,local_5c);
          if (iVar6 == local_58) {
            thunk_EXT_FUN_1fff8000(local_64 + 0x428,local_64 + 0x436,&local_5c);
            FUN_00000fc4(7);
            uVar7 = 0x7e0;
          }
          else {
            FUN_00000fcc(0xb,0xc);
            uVar7 = 0xf800;
          }
          FUN_000017cc(uVar7);
          return;
        }
        iVar6 = FUN_00001618(&local_68,&local_6c,20000);
        if (iVar6 != 0) break;
        iVar6 = FUN_00000120(puVar14,local_6c,uVar7,puVar5);
        if (iVar6 != 0) {
          uVar7 = 0xb;
          goto LAB_0000134a;
        }
        thunk_EXT_FUN_1fff8000(uVar13,local_6c + uVar13,puVar5);
        FUN_00000fc4(1);
        uVar13 = uVar13 + local_6c;
        FUN_00000c44(0x66,0xdf,(((uVar13 * 100) / local_60) * 0x88) / 100,0xf,0x7fff);
        uVar11 = local_60;
      }
      uVar7 = 0xb;
      uVar10 = 9;
      goto LAB_0000136a;
    }
    goto LAB_00001528;
  case 0x43:
    uVar10 = *puVar14;
    if (uVar10 >> 0x10 < 7) {
      uVar7 = 6;
      uVar10 = 2;
      goto LAB_0000136a;
    }
    uVar10 = thunk_EXT_FUN_1fff8000(uVar10,puVar14[1] + uVar10,puVar14 + 2);
LAB_00001528:
    uVar10 = uVar10 & 0xffff;
    uVar7 = 0xb;
LAB_0000136a:
    FUN_00000fcc(uVar7,uVar10);
    return;
  case 0x44:
    uVar10 = puVar14[3];
    uVar13 = *puVar14;
    uVar11 = puVar14[1];
    uVar12 = puVar14[2];
    uVar7 = 0x44;
    goto LAB_000014fa;
  case 0x46:
    FUN_000006f4();
    FUN_00000b7c();
    break;
  case 0x47:
    FUN_000006f4();
    FUN_00000c44();
    break;
  case 0x4a:
    if ((((*pcVar3 != '\0') || (uVar10 = *puVar14, (uVar10 & 0xff) != 0)) ||
        (uVar13 = puVar14[1], 0x800 < uVar13)) ||
       ((DAT_000015f4 < uVar13 + uVar10 || (puVar14[2] != 0xffffffff)))) {
      uVar7 = 6;
      uVar10 = 5;
      goto LAB_0000136a;
    }
    if (uVar10 - 0x80000 >> 0x14 < 3) {
      if (0x100 < uVar13) {
        uVar7 = 6;
        uVar10 = 6;
        goto LAB_0000136a;
      }
      if ((uVar10 & 0xffff) == 0) {
        FUN_000007e8(uVar10);
        uVar10 = *puVar14;
        uVar13 = puVar14[1];
      }
      iVar6 = FUN_000009b0(puVar14 + 4,uVar10,uVar13 & 0xffff);
    }
    else {
      iVar6 = FUN_00000a08(puVar14 + 4,uVar10,uVar13 & 0xffff);
    }
    if (iVar6 != 0) {
      uVar7 = 6;
      uVar10 = 7;
      goto LAB_0000136a;
    }
    break;
  case 0x4b:
    if (*pcVar3 != '\0') {
      return;
    }
    uVar10 = puVar14[3];
    uVar11 = puVar14[1];
    uVar12 = puVar14[2];
    uVar13 = *puVar14 + 0x98000000;
    uVar7 = 0x4b;
LAB_000014fa:
    FUN_00000ff4(uVar7,uVar13,uVar11,uVar12,uVar10);
    return;
  default:
    switch(uVar13) {
    case 1:
      return;
    case 2:
      iVar6 = *piVar4;
      bVar8 = *(byte *)(iVar6 + 0x9c) | 4;
      break;
    case 3:
      iVar6 = *piVar4;
      bVar8 = *(byte *)(iVar6 + 0x9c) & 0xfb;
      break;
    case 4:
      FUN_000002b0(100);
      uVar7 = DAT_000015f0;
      goto LAB_000015d4;
    default:
      goto switchD_00001378_caseD_41;
    case 8:
      FUN_000002b0(10);
      uVar7 = 0;
LAB_000015d4:
      *DAT_000015ec = uVar7;
      uVar15 = FUN_00001110();
      iVar6 = (int)((ulonglong)uVar15 >> 0x20);
      uVar2 = (undefined2)uVar13;
      *(undefined2 *)(extraout_r3 + 8) = uVar2;
      *(undefined2 *)((int)uVar15 + 10) = uVar2;
      *(undefined2 *)(iVar6 + 8) = uVar2;
      *(undefined2 *)(extraout_r2 + 0x1a) = uVar2;
      cVar1 = pcVar3[iVar6 + -0x1c];
      *(undefined4 *)(((int)cVar1 & 0x3fU) + 0x10) = 0x10;
      do {
      } while (*(int *)(((int)cVar1 & 0x3fU) + 0x10) << 0x1b < 0);
      return;
    }
    *(byte *)(iVar6 + 0x9c) = bVar8;
    uVar7 = 5;
    goto LAB_00001516;
  }
  uVar7 = 7;
LAB_00001516:
  FUN_00000fc4(uVar7);
  return;
}

