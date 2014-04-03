mkdir -p build_lx
mkdir -p build_ws

ssh amsel 'cd cosmotica/tenstream/build_ws; cmake ..; make clean ; make ' &
ssh lx001 'cd cosmotica/tenstream/build_lx; cmake ..; make clean ; make ' &

wait