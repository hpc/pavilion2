#!/bin/bash

sig_dig_re='^[0-9]+.[0-9]{2}'

flops=$(bc -l <<< "${RANDOM}/32767 *10 + 30" | grep -Eo $sig_dig_re)
acc=$(bc -l <<< "${RANDOM}/32767 * 2 + 3" | grep -Eo $sig_dig_re)

if [[ $1 -eq 4 ]]; then 
    flops=$(bc -l <<< "${flops} + 100")
fi

echo "Node $1 reporting sir!"
echo "Parameters are optimal!"
echo "Firing on all cylinders!"

echo "accel: ${acc}s"
echo "Single node flops are ${flops} bunnies."

echo "Confusion is setting in."
echo "Good night!"
