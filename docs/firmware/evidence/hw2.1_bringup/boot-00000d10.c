
void FUN_00000d10(void)

{
  code *pcVar1;
  undefined4 local_44;
  undefined4 local_40;
  undefined4 uStack_3c;
  undefined2 local_38;
  undefined4 local_34;
  undefined4 local_30;
  undefined4 uStack_2c;
  undefined2 local_28;
  undefined4 local_24;
  undefined1 local_20;
  undefined2 local_1e [7];
  
  FUN_00000e00();
  pcVar1 = DAT_00000dd8;
  (*DAT_00000dd8)(0x11,0,0);
  FUN_000002b0(0x32);
  (*pcVar1)(0x21,0,0);
  local_1e[0] = CONCAT11(local_1e[0]._1_1_,0xa0);
  (*pcVar1)(0x36,local_1e,1);
  FUN_00000758(5);
  (*pcVar1)(0x3a);
  local_20 = 0x33;
  local_24 = DAT_00000ddc;
  (*pcVar1)(0xb2,&local_24,5);
  FUN_00000758(0x75);
  (*pcVar1)(0xb7);
  FUN_00000758(0x3f);
  (*pcVar1)(0xbb);
  FUN_00000758(0x20);
  (*pcVar1)(0xc4);
  FUN_00000e20(0xf);
  local_1e[0] = 0xa4;
  (*pcVar1)(0xd0,local_1e,2);
  local_34 = DAT_00000de0;
  local_30 = DAT_00000de4;
  uStack_2c = DAT_00000de8;
  local_28 = DAT_00000dec;
  (*pcVar1)(0xe0,&local_34,0xe);
  local_44 = DAT_00000df0;
  local_40 = DAT_00000df4;
  uStack_3c = DAT_00000df8;
  local_38 = DAT_00000dfc;
  (*pcVar1)(0xe1,&local_44,0xe);
  FUN_00000e3c(1);
  FUN_00000b60();
  return;
}

