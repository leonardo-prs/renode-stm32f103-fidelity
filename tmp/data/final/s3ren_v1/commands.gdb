set pagination off
set confirm off
set breakpoint pending off
set remotetimeout 5
set tcp connect-timeout 5
target remote 127.0.0.1:3336
if sizeof(fidelity_snapshot) != 10368
  echo FIDELITY_BAD_SIZE\n
  quit 21
end
printf "FIDELITY_SIZE=%u\n", (unsigned)sizeof(fidelity_snapshot)
if (unsigned long)&fidelity_snapshot < 0x20000000 || (unsigned long)&fidelity_snapshot + sizeof(fidelity_snapshot) > 0x20005000
  echo FIDELITY_BAD_ADDRESS\n
  quit 23
end
printf "FIDELITY_INITIAL_MAGIC=0x%x\n", fidelity_snapshot.header.magic
hbreak *fidelity_complete
continue
printf "FIDELITY_PC=0x%lx COMPLETE=0x%lx\n", (unsigned long)$pc, (unsigned long)&fidelity_complete
if ((unsigned long)$pc & ~1) != ((unsigned long)&fidelity_complete & ~1)
  echo FIDELITY_UNAUTHORIZED_HALT\n
  quit 22
end
printf "FIDELITY_TERMINAL=%u MAGIC=0x%x\n", fidelity_snapshot.header.state, fidelity_snapshot.header.magic
dump binary memory /home/leonardo/projects/renode-stm32f103-fidelity/data/final/s3ren_v1/snapshot.pending.bin &fidelity_snapshot ((char*)&fidelity_snapshot)+sizeof(fidelity_snapshot)
detach
quit 0
