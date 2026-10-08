set pagination off
set confirm off
target extended-remote 127.0.0.1:3333
monitor reset halt
load
compare-sections
monitor reset halt
detach
quit 0
