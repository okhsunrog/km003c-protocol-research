
/* WARNING: Globals starting with '_' overlap smaller symbols at the same address */

void FUN_0001b2fc(void)

{
  int iVar1;
  int iVar2;
  undefined4 local_10;
  undefined4 local_c;
  
  _DAT_20004796 = 0;
  DAT_20004798 = 0;
  iVar1 = 0;
  do {
    iVar2 = iVar1 + 0x10;
    *(undefined4 *)(iVar1 + 0x20004734) = 200;
    *(undefined1 *)(iVar1 + 0x20004730) = 2;
    *(undefined1 *)(iVar1 + 0x20004738) = 0;
    iVar1 = iVar2;
  } while (iVar2 != 0x60);
  _DAT_20004754 = 0x32;
  _DAT_20004764 = 0x32;
  _DAT_2000472c = 0x92b1;
  _DAT_2000473c = 0x92c3;
  _DAT_2000474c = 0x92d5;
  _DAT_2000475c = 0x92e7;
  _DAT_2000476c = 0x92f9;
  _DAT_2000477c = 0x9311;
  local_c = 1;
  DAT_20004757 = 0x14;
  DAT_20004767 = 0x14;
  local_10 = 0;
  FUN_0000a750(1,0xb80,&local_10);
  return;
}

