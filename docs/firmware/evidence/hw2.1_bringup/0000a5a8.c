
void FUN_0000a5a8(int param_1)

{
  uint uVar1;
  
  uVar1 = 0;
  if (param_1 != 0) {
    uVar1 = 4;
  }
  DAT_20004045 = DAT_20004045 & 0xfb | (byte)uVar1;
  FUN_00043610(uVar1 >> 2);
  FUN_0004d580(0x20003b1c,0);
  FUN_0004dc6c(0x20005400,s_PD_TASK_0000a60c,&LAB_0001e950_1,0,3,0x20004838,0x400,0);
  return;
}

