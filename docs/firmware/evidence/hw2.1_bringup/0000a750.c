
/* WARNING: Globals starting with '_' overlap smaller symbols at the same address */

undefined4 FUN_0000a750(int param_1,uint param_2,char *param_3)

{
  char cVar1;
  ushort *puVar2;
  uint uVar3;
  ushort uVar4;
  
  puVar2 = (ushort *)(param_1 * 0x40 + 0x40053c02);
  uVar3 = 0;
  do {
    if ((param_2 >> (uVar3 & 0xff) & 1) != 0) {
      puVar2[-1] = puVar2[-1] & 0xbfff | ((byte)param_3[1] & 1) << 0xe;
      puVar2[-1] = puVar2[-1] & 0xefff | ((byte)param_3[2] & 1) << 0xc;
      puVar2[-1] = puVar2[-1] & 0xfdff | ((byte)param_3[3] & 1) << 9;
      puVar2[-1] = puVar2[-1] & 0xffbf | ((byte)param_3[4] & 1) << 6;
      puVar2[-1] = puVar2[-1] & 0xfffb | ((byte)param_3[6] & 1) << 2;
      puVar2[-1] = puVar2[-1] & 0xffcf | ((byte)param_3[5] & 3) << 4;
      cVar1 = *param_3;
      if (cVar1 == '\x02') {
        uVar4 = puVar2[-1] | 0x8000;
LAB_0000a840:
        puVar2[-1] = uVar4;
      }
      else {
        if (cVar1 == '\x01') {
          puVar2[-1] = puVar2[-1] & 0x7fff;
          uVar4 = puVar2[-1] | 2;
          goto LAB_0000a840;
        }
        if (cVar1 == '\0') {
          puVar2[-1] = puVar2[-1] & 0x7fff;
          uVar4 = puVar2[-1] & 0xfffd;
          goto LAB_0000a840;
        }
      }
      *puVar2 = *puVar2 & 0xfeff | ((byte)param_3[7] & 1) << 8;
    }
    uVar3 = uVar3 + 1;
    puVar2 = puVar2 + 2;
    if (uVar3 == 0x10) {
      _DAT_40053bfc = 0xa500;
      return 0;
    }
  } while( true );
}

