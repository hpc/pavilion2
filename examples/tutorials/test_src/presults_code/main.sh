#!/bin/bash

case "$((${RANDOM} % 4))" in 
    "0")
    result="terribly."
    ;;
    "1")
    result="ok"
    ;;
    "2")
    result="great!"
    ;;
    "3")
    result="sufficently"
    ;;
esac

echo "Welcome to our contrived example!"
echo "- - - - - - - - - - - - - - - - - - - - -"
echo 
echo "Ran for: 32.5s"
echo "GFlops: ${RANDOM}"
echo 
echo "Settings (weebles, wobbles, marks, conflagurated?)"
echo "- - - - - - - - - - - - - - - - - - - - -"
echo "32, 98.5, 18.5, True"
echo 
echo 
echo
echo "N-dim     |   Elasticity   |  Cubism"
echo "-----------------------------------------"
echo "1         | 45.234           | 16"
echo "2         | 25.9           | 121"
echo "4         | 35.11           | 144"
echo 
echo "That went ${result}"
