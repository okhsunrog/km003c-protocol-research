
void FUN_0001a9c8(byte param_1,int param_2)

{
  byte *pbVar1;
  byte local_c;
  byte local_b;
  byte local_a;
  byte local_9;
  
  if (param_2 == 1) {
    DAT_20003f74 = DAT_20003f74 | param_1;
    pbVar1 = &local_b;
    local_b = DAT_20003f74;
  }
  else {
    if (param_2 == 0) {
      DAT_20003574 = DAT_20003574 | param_1;
      DAT_20003f74 = DAT_20003f74 & ~param_1;
      pbVar1 = &local_c;
      local_c = DAT_20003574;
      goto LAB_0001aa4a;
    }
    DAT_20003f74 = DAT_20003f74 & ~param_1;
    pbVar1 = &local_a;
    local_a = DAT_20003f74;
  }
  FUN_0001ab28(2,pbVar1,1);
  if ((DAT_20003574 & param_1) == 0) {
    return;
  }
  DAT_20003574 = DAT_20003574 & ~param_1;
  pbVar1 = &local_9;
  local_9 = DAT_20003574;
LAB_0001aa4a:
  FUN_0001ab28(4,pbVar1,1);
  return;
}

