set pagination off
target extended-remote 127.0.0.1:3333
monitor halt
printf "FID_PC=0x%x\n", $pc
printf "FID_COMPLETE=0x%x\n", &fidelity_complete
dump binary memory /home/leonardo/projects/renode-stm32f103-fidelity/data/fidelity/v1/s2a/hw-free/run-002/snapshot.bin &fidelity_snapshot ((char*)&fidelity_snapshot)+sizeof(fidelity_snapshot)
monitor poll on
detach
quit 0
