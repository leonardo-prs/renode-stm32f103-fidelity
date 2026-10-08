set pagination off
set confirm off
set remotetimeout 10
target extended-remote 127.0.0.1:3336
hbreak fidelity_complete
continue
printf "FID_PC=0x%x\n", $pc
printf "FID_COMPLETE=0x%x\n", &fidelity_complete
printf "FID_SIZE=%u\n", sizeof(fidelity_snapshot)
dump binary memory /home/leonardo/projects/renode-stm32f103-fidelity/data/fidelity/dev/s2a/rn-m8-q1us/run-001/snapshot.bin &fidelity_snapshot ((char*)&fidelity_snapshot)+sizeof(fidelity_snapshot)
monitor sysbus.cpu ExecutedInstructions
monitor machine GetTimeSourceInfo
detach
quit 0
