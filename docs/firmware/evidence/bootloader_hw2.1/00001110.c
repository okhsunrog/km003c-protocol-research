
void FUN_00001110(void)

{
  DataSynchronizationBarrier(0xf);
  *DAT_0000112c = *DAT_0000112c & 0x700 | DAT_00001130;
  DataSynchronizationBarrier(0xf);
  do {
                    /* WARNING: Do nothing block with infinite loop */
  } while( true );
}

